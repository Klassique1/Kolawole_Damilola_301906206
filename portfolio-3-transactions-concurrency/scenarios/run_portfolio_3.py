"""Portfolio 3 runner: deterministic COMMIT/ROLLBACK, Lost Update, Deadlock, Locking & SSI tests."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import random
import threading
import uuid

import psycopg

from core.concurrency_runner import ConcurrencyScenarioReport, run_concurrent_scenario
from core.config import load_config
from core.postgres_client import PostgresClient


def _next_account_number() -> str:
    return "5" + f"{random.randint(100000000, 999999999)}"


def _provision_test_wallet(
    client: PostgresClient,
    *,
    label: str,
    opening_balance: Decimal,
) -> tuple[str, str]:
    """Create a fresh customer + funded wallet using balanced double-entry against EXTERNAL_CONTRA."""
    acct_num = _next_account_number()
    cust_id = str(uuid.uuid4())
    acct_id = str(uuid.uuid4())
    txn_id = str(uuid.uuid4())
    contra_id = "22222222-2222-4222-8222-222222222000"
    tag = uuid.uuid4().hex[:8]

    with client.connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.customers (customer_id, full_name, email, phone_number, kyc_tier_code)
                    VALUES (%s, %s, %s, %s, 'TIER_2')
                    """,
                    (
                        cust_id,
                        f"P3 {label}",
                        f"p3_{label.lower()}_{tag}@novapay-demo.ng",
                        f"+23481{random.randint(10000000, 99999999)}",
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO core.accounts (
                        account_id, account_number, customer_id,
                        account_type_code, currency_code, balance, available_balance
                    )
                    VALUES (%s, %s, %s, 'SAVINGS_WALLET', 'NGN', %s, %s)
                    """,
                    (acct_id, acct_num, cust_id, opening_balance, opening_balance),
                )
                if opening_balance > 0:
                    cur.execute(
                        """
                        UPDATE core.accounts
                        SET balance = balance - %s,
                            available_balance = available_balance - %s,
                            version = version + 1
                        WHERE account_id = %s
                        RETURNING balance
                        """,
                        (opening_balance, opening_balance, contra_id),
                    )
                    contra_after = cur.fetchone()[0]
                    ref = f"NP-P3-SEED-{tag}"
                    cur.execute(
                        """
                        INSERT INTO core.transactions (
                            transaction_id, reference_code, idempotency_key, transaction_type,
                            source_account_id, destination_account_id, currency_code, amount,
                            status, narration, initiated_by_customer_id, completed_at
                        )
                        VALUES (%s, %s, %s, 'DEPOSIT', %s, %s, 'NGN', %s, 'COMPLETED', %s, %s, now())
                        """,
                        (
                            txn_id,
                            ref,
                            f"idem-{ref}",
                            contra_id,
                            acct_id,
                            opening_balance,
                            f"P3 test wallet funding ({label})",
                            cust_id,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO core.ledger_entries
                            (transaction_id, account_id, direction, amount, balance_after, narration)
                        VALUES
                            (%s, %s, 'DEBIT',  %s, %s, 'P3 test funding debit'),
                            (%s, %s, 'CREDIT', %s, %s, 'P3 test funding credit')
                        """,
                        (
                            txn_id, contra_id, opening_balance, contra_after,
                            txn_id, acct_id, opening_balance, opening_balance,
                        ),
                    )
    return acct_id, acct_num


def _transfer_unlocked_buggy(
    conn: psycopg.Connection,
    barrier: threading.Barrier,
    *,
    src_id: str,
    dst_id: str,
    amount: Decimal,
    tag: str,
) -> str:
    """Deliberately unsafe Read-Modify-Write without FOR UPDATE (demonstrates Lost Update)."""
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM core.accounts WHERE account_id = %s", (src_id,))
        src_bal = Decimal(cur.fetchone()[0])

    # Align both concurrent sessions so both observe the same stale balance
    barrier.wait()

    if src_bal < amount:
        raise ValueError(f"Insufficient balance ({src_bal} < {amount})")

    new_src_bal = src_bal - amount
    txn_id = str(uuid.uuid4())
    ref = f"NP-P3-LU-{tag}-{uuid.uuid4().hex[:6]}"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE core.accounts
            SET balance = %s, available_balance = %s, version = version + 1
            WHERE account_id = %s
            """,
            (new_src_bal, new_src_bal, src_id),
        )
        cur.execute(
            """
            UPDATE core.accounts
            SET balance = balance + %s, available_balance = available_balance + %s, version = version + 1
            WHERE account_id = %s
            RETURNING balance
            """,
            (amount, amount, dst_id),
        )
        dst_after = Decimal(cur.fetchone()[0])
        cur.execute(
            """
            INSERT INTO core.transactions (
                transaction_id, reference_code, idempotency_key, transaction_type,
                source_account_id, destination_account_id, currency_code, amount,
                status, narration, completed_at
            )
            VALUES (%s, %s, %s, 'TRANSFER', %s, %s, 'NGN', %s, 'COMPLETED', %s, now())
            """,
            (txn_id, ref, f"idem-{ref}", src_id, dst_id, amount, f"Concurrent transfer ({tag})"),
        )
        cur.execute(
            """
            INSERT INTO core.ledger_entries
                (transaction_id, account_id, direction, amount, balance_after, narration)
            VALUES
                (%s, %s, 'DEBIT',  %s, %s, 'Concurrent debit'),
                (%s, %s, 'CREDIT', %s, %s, 'Concurrent credit')
            """,
            (txn_id, src_id, amount, new_src_bal, txn_id, dst_id, amount, dst_after),
        )
    return f"Debited {amount} from stale read {src_bal} -> {new_src_bal}"


def _transfer_locked_safe(
    conn: psycopg.Connection,
    barrier: threading.Barrier,
    *,
    src_id: str,
    dst_id: str,
    amount: Decimal,
    tag: str,
    wait_before_lock: bool = True,
) -> str:
    """Safe atomic transfer using deterministic ordered SELECT ... FOR UPDATE."""
    if wait_before_lock:
        barrier.wait()

    with conn.cursor() as cur:
        # Lock both accounts in deterministic UUID order to prevent deadlocks
        cur.execute(
            """
            SELECT account_id, balance
            FROM core.accounts
            WHERE account_id IN (%s, %s)
            ORDER BY account_id ASC
            FOR UPDATE
            """,
            (src_id, dst_id),
        )
        locked = {str(row[0]): Decimal(row[1]) for row in cur.fetchall()}

    src_bal = locked[src_id]
    dst_bal = locked[dst_id]
    if src_bal < amount:
        raise ValueError(f"Insufficient balance ({src_bal} < {amount}); cleanly rejected")

    new_src_bal = src_bal - amount
    new_dst_bal = dst_bal + amount
    txn_id = str(uuid.uuid4())
    ref = f"NP-P3-SAFE-{tag}-{uuid.uuid4().hex[:6]}"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE core.accounts
            SET balance = balance - %s, available_balance = available_balance - %s, version = version + 1
            WHERE account_id = %s
            """,
            (amount, amount, src_id),
        )
        cur.execute(
            """
            UPDATE core.accounts
            SET balance = balance + %s, available_balance = available_balance + %s, version = version + 1
            WHERE account_id = %s
            """,
            (amount, amount, dst_id),
        )
        cur.execute(
            """
            INSERT INTO core.transactions (
                transaction_id, reference_code, idempotency_key, transaction_type,
                source_account_id, destination_account_id, currency_code, amount,
                status, narration, completed_at
            )
            VALUES (%s, %s, %s, 'TRANSFER', %s, %s, 'NGN', %s, 'COMPLETED', %s, now())
            """,
            (txn_id, ref, f"idem-{ref}", src_id, dst_id, amount, f"Locked transfer ({tag})"),
        )
        cur.execute(
            """
            INSERT INTO core.ledger_entries
                (transaction_id, account_id, direction, amount, balance_after, narration)
            VALUES
                (%s, %s, 'DEBIT',  %s, %s, 'Safe locked debit'),
                (%s, %s, 'CREDIT', %s, %s, 'Safe locked credit')
            """,
            (txn_id, src_id, amount, new_src_bal, txn_id, dst_id, amount, new_dst_bal),
        )
    return f"Locked transfer {amount} succeeded ({src_bal} -> {new_src_bal})"


def _run_commit_rollback_demo(client: PostgresClient) -> dict:
    """Scenario 1: Demonstrate atomic COMMIT and full ROLLBACK on constraint breach."""
    acct_a, num_a = _provision_test_wallet(client, label="CommitA", opening_balance=Decimal("100000.0000"))
    acct_b, num_b = _provision_test_wallet(client, label="CommitB", opening_balance=Decimal("20000.0000"))

    # 1A: Successful atomic COMMIT of 25,000 NGN
    dummy_barrier = threading.Barrier(1)
    with client.connect() as conn:
        with conn.transaction():
            commit_msg = _transfer_locked_safe(
                conn,
                dummy_barrier,
                src_id=acct_a,
                dst_id=acct_b,
                amount=Decimal("25000.0000"),
                tag="commit",
                wait_before_lock=False,
            )

    # 1B: Intentional mid-transaction failure -> full ROLLBACK
    rollback_msg = ""
    try:
        with client.connect() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # Step 1 credits destination first
                    cur.execute(
                        "UPDATE core.accounts SET balance = balance + 999999, available_balance = available_balance + 999999 WHERE account_id = %s",
                        (acct_b,),
                    )
                    # Step 2 attempts illegal overdraft -> triggers CHECK constraint (23514) -> auto ROLLBACK
                    cur.execute(
                        "UPDATE core.accounts SET balance = balance - 999999, available_balance = available_balance - 999999 WHERE account_id = %s",
                        (acct_a,),
                    )
    except psycopg.Error as exc:
        rollback_msg = f"Rolled back cleanly on SQLSTATE {exc.sqlstate}: {str(exc).splitlines()[0]}"

    with client.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM core.accounts WHERE account_id = %s", (acct_a,))
            final_a = Decimal(cur.fetchone()[0])
            cur.execute("SELECT balance FROM core.accounts WHERE account_id = %s", (acct_b,))
            final_b = Decimal(cur.fetchone()[0])

    assert final_a == Decimal("75000.0000")
    assert final_b == Decimal("45000.0000")

    return {
        "accounts": {"source": num_a, "destination": num_b},
        "commit_result": commit_msg,
        "rollback_result": rollback_msg,
        "final_balances": {num_a: str(final_a), num_b: str(final_b)},
        "atomicity_verified": True,
    }


def _check_wallet_invariant(
    conn: psycopg.Connection,
    src_id: str,
    expected_non_negative: bool = True,
) -> tuple[bool, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT stored_balance, ledger_computed_balance, variance
            FROM core.v_account_reconciliation
            WHERE account_id = %s
            """,
            (src_id,),
        )
        stored, computed, variance = [Decimal(v) for v in cur.fetchone()]

    passed = variance == Decimal("0") and (not expected_non_negative or computed >= Decimal("0"))
    return (
        passed,
        f"stored_balance={stored}, ledger_computed_balance={computed}, variance={variance}",
    )


def main() -> None:
    portfolio_dir = Path(__file__).resolve().parent.parent
    evidence_dir = portfolio_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    client = PostgresClient(cfg)

    print("1/5 Running Scenario 1: Atomic COMMIT & ROLLBACK...")
    s1 = _run_commit_rollback_demo(client)

    print("2/5 Running Scenario 2: Unsafe READ COMMITTED Lost Update / Double-Spend...")
    lu_src, lu_src_num = _provision_test_wallet(client, label="LostUpdateSrc", opening_balance=Decimal("50000.0000"))
    lu_dst, _ = _provision_test_wallet(client, label="LostUpdateDst", opening_balance=Decimal("0.0000"))
    s2 = run_concurrent_scenario(
        client,
        scenario_name="Scenario 2: Unlocked READ COMMITTED (Lost Update / Double-Spend)",
        isolation_level=psycopg.IsolationLevel.READ_COMMITTED,
        workers=[
            ("Worker-A", lambda conn, bar: _transfer_unlocked_buggy(conn, bar, src_id=lu_src, dst_id=lu_dst, amount=Decimal("40000.0000"), tag="A")),
            ("Worker-B", lambda conn, bar: _transfer_unlocked_buggy(conn, bar, src_id=lu_src, dst_id=lu_dst, amount=Decimal("40000.0000"), tag="B")),
        ],
        invariant_check=lambda conn: _check_wallet_invariant(conn, lu_src),
    )

    print("3/5 Running Scenario 3: Safe Pessimistic Locking (SELECT ... FOR UPDATE)...")
    fk_src, _ = _provision_test_wallet(client, label="ForUpdateSrc", opening_balance=Decimal("50000.0000"))
    fk_dst, _ = _provision_test_wallet(client, label="ForUpdateDst", opening_balance=Decimal("0.0000"))
    s3 = run_concurrent_scenario(
        client,
        scenario_name="Scenario 3: Pessimistic Row Locking (SELECT ... FOR UPDATE)",
        isolation_level=psycopg.IsolationLevel.READ_COMMITTED,
        workers=[
            ("Worker-A", lambda conn, bar: _transfer_locked_safe(conn, bar, src_id=fk_src, dst_id=fk_dst, amount=Decimal("40000.0000"), tag="FU-A")),
            ("Worker-B", lambda conn, bar: _transfer_locked_safe(conn, bar, src_id=fk_src, dst_id=fk_dst, amount=Decimal("40000.0000"), tag="FU-B")),
        ],
        invariant_check=lambda conn: _check_wallet_invariant(conn, fk_src),
    )

    print("4/5 Running Scenario 4: Deadlock Reproduction vs. Ordered Resource Locking...")
    dl_x, _ = _provision_test_wallet(client, label="DeadlockX", opening_balance=Decimal("100000.0000"))
    dl_y, _ = _provision_test_wallet(client, label="DeadlockY", opening_balance=Decimal("100000.0000"))

    def _unordered_lock_pair(conn: psycopg.Connection, bar: threading.Barrier, first: str, second: str) -> str:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM core.accounts WHERE account_id = %s FOR UPDATE", (first,))
        bar.wait()
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM core.accounts WHERE account_id = %s FOR UPDATE", (second,))
        return "Acquired both locks"

    s4a = run_concurrent_scenario(
        client,
        scenario_name="Scenario 4A: Unordered Bidirectional Locking (Deadlock Triggered)",
        isolation_level=psycopg.IsolationLevel.READ_COMMITTED,
        workers=[
            ("Session-X-then-Y", lambda conn, bar: _unordered_lock_pair(conn, bar, dl_x, dl_y)),
            ("Session-Y-then-X", lambda conn, bar: _unordered_lock_pair(conn, bar, dl_y, dl_x)),
        ],
        invariant_check=lambda conn: _check_wallet_invariant(conn, dl_x),
    )

    s4b = run_concurrent_scenario(
        client,
        scenario_name="Scenario 4B: Deterministic Ordered Locking (Zero Deadlocks)",
        isolation_level=psycopg.IsolationLevel.READ_COMMITTED,
        workers=[
            ("Session-X-to-Y", lambda conn, bar: _transfer_locked_safe(conn, bar, src_id=dl_x, dst_id=dl_y, amount=Decimal("15000.0000"), tag="ORD-XY")),
            ("Session-Y-to-X", lambda conn, bar: _transfer_locked_safe(conn, bar, src_id=dl_y, dst_id=dl_x, amount=Decimal("10000.0000"), tag="ORD-YX")),
        ],
        invariant_check=lambda conn: _check_wallet_invariant(conn, dl_x),
    )

    print("5/5 Running Scenario 5: Optimistic SERIALIZABLE (SSI) with Automatic Retry...")
    ssi_src, _ = _provision_test_wallet(client, label="SSISrc", opening_balance=Decimal("50000.0000"))
    ssi_dst, _ = _provision_test_wallet(client, label="SSIDst", opening_balance=Decimal("0.0000"))
    s5 = run_concurrent_scenario(
        client,
        scenario_name="Scenario 5: SERIALIZABLE Isolation (SSI + Retry Backoff)",
        isolation_level=psycopg.IsolationLevel.SERIALIZABLE,
        workers=[
            ("Worker-A", lambda conn, bar: _transfer_unlocked_buggy(conn, bar, src_id=ssi_src, dst_id=ssi_dst, amount=Decimal("40000.0000"), tag="SSI-A")),
            ("Worker-B", lambda conn, bar: _transfer_unlocked_buggy(conn, bar, src_id=ssi_src, dst_id=ssi_dst, amount=Decimal("40000.0000"), tag="SSI-B")),
        ],
        invariant_check=lambda conn: _check_wallet_invariant(conn, ssi_src),
        max_serialization_retries=2,
    )

    reports: list[ConcurrencyScenarioReport] = [s2, s3, s4a, s4b, s5]

    lines = [
        "# Portfolio 3: Transactions & Concurrency Verification Report",
        "",
        "## Scenario 1: Atomic `COMMIT` & `ROLLBACK`",
        f"- **Accounts:** `{s1['accounts']['source']}` -> `{s1['accounts']['destination']}`",
        f"- **COMMIT Outcome:** {s1['commit_result']}",
        f"- **ROLLBACK Outcome:** {s1['rollback_result']}",
        f"- **Final Balances (After Both Operations):** `{s1['final_balances']}`",
        f"- **Atomicity Verified:** `{s1['atomicity_verified']}`",
        "",
    ]

    for rep in reports:
        lines.append(f"## {rep.scenario_name}")
        lines.append(f"- **Isolation Level:** `{rep.isolation_level}`")
        lines.append(f"- **Invariant Passed:** `{rep.invariant_passed}` (`{rep.invariant_details}`)")
        lines.append("")
        lines.append("| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |")
        lines.append("| :--- | :---: | ---: | ---: | :--- | :--- |")
        for o in rep.outcomes:
            lines.append(
                f"| {o.worker_name} | {o.succeeded} | {o.attempts} | {o.elapsed_ms:.2f} | "
                f"`{o.sqlstate or 'N/A'}` | {o.message} |"
            )
        lines.append("")

    md_path = evidence_dir / "portfolio_3_concurrency_report.md"
    json_path = evidence_dir / "portfolio_3_concurrency_report.json"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "scenario_1_atomicity": s1,
                "concurrent_scenarios": [r.to_dict() for r in reports],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Portfolio 3 report exported to {md_path}")


if __name__ == "__main__":
    main()
