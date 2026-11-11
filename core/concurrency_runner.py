"""Deterministic multi-session concurrency harness for Portfolio 3 demonstrations."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

import psycopg

from core.postgres_client import PostgresClient


@dataclass(frozen=True)
class WorkerOutcome:
    """Execution outcome of one concurrent database session."""

    worker_name: str
    succeeded: bool
    attempts: int
    elapsed_ms: float
    sqlstate: str | None
    message: str


@dataclass(frozen=True)
class ConcurrencyScenarioReport:
    """Aggregated outcome across concurrent workers and post-run invariant check."""

    scenario_name: str
    isolation_level: str
    outcomes: list[WorkerOutcome]
    invariant_passed: bool
    invariant_details: str

    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "isolation_level": self.isolation_level,
            "outcomes": [asdict(o) for o in self.outcomes],
            "invariant_passed": self.invariant_passed,
            "invariant_details": self.invariant_details,
        }


WorkerAction = Callable[[psycopg.Connection, threading.Barrier], str]
InvariantCheck = Callable[[psycopg.Connection], tuple[bool, str]]


def run_concurrent_scenario(
    client: PostgresClient,
    *,
    scenario_name: str,
    isolation_level: psycopg.IsolationLevel,
    workers: list[tuple[str, WorkerAction]],
    invariant_check: InvariantCheck,
    max_serialization_retries: int = 0,
) -> ConcurrencyScenarioReport:
    """Run multiple database sessions aligned on a barrier to surface or verify concurrency controls."""
    barrier = threading.Barrier(len(workers), timeout=15.0)
    results: list[WorkerOutcome] = []
    lock = threading.Lock()

    def _run_worker(name: str, action: WorkerAction) -> None:
        started = time.perf_counter()
        attempts = 0
        last_sqlstate: str | None = None
        last_message = ""
        succeeded = False

        retry_sqlstates: list[str] = []

        while attempts <= max_serialization_retries:
            attempts += 1
            last_sqlstate = None
            active_barrier = barrier if attempts == 1 else threading.Barrier(1)
            try:
                with client.connect(isolation_level=isolation_level) as conn:
                    with conn.transaction():
                        last_message = action(conn, active_barrier)
                succeeded = True
                last_sqlstate = "00000"
                break
            except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected) as exc:
                last_sqlstate = exc.sqlstate
                if last_sqlstate:
                    retry_sqlstates.append(last_sqlstate)
                last_message = str(exc).strip().splitlines()[0]
                if attempts <= max_serialization_retries:
                    time.sleep(0.05 * attempts)
                    continue
                break
            except psycopg.Error as exc:
                last_sqlstate = exc.sqlstate
                last_message = str(exc).strip().splitlines()[0]
                break
            except Exception as exc:  # noqa: BLE001 - capture deterministic error summary for report
                last_message = str(exc)
                if retry_sqlstates:
                    last_message = f"{last_message} (after retry from SQLSTATE {','.join(retry_sqlstates)})"
                break

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        with lock:
            results.append(
                WorkerOutcome(
                    worker_name=name,
                    succeeded=succeeded,
                    attempts=attempts,
                    elapsed_ms=elapsed_ms,
                    sqlstate=last_sqlstate,
                    message=last_message,
                )
            )

    threads = [
        threading.Thread(target=_run_worker, args=(worker_name, action), daemon=True)
        for worker_name, action in workers
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)

    with client.connect() as verify_conn:
        passed, details = invariant_check(verify_conn)

    results.sort(key=lambda item: item.worker_name)
    return ConcurrencyScenarioReport(
        scenario_name=scenario_name,
        isolation_level=isolation_level.name,
        outcomes=results,
        invariant_passed=passed,
        invariant_details=details,
    )
