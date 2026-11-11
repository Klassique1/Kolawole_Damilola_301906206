"""Portfolio 5 runner: verifies PostgreSQL range partition pruning and streaming replication."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid

import psycopg

from core.config import load_config
from core.postgres_client import PostgresClient


def main() -> None:
    portfolio_dir = Path(__file__).resolve().parent
    sql_path = portfolio_dir / "sql" / "001_partitioned_ledger.sql"
    evidence_dir = portfolio_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    client = PostgresClient(cfg)

    print("1/4 Applying declarative monthly range partitioning on ledger_entries_partitioned...")
    with client.connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(sql_path.read_text(encoding="utf-8"))

    print("2/4 Inspecting partition distribution and EXPLAIN partition pruning...")
    with client.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.relname AS partition_name,
                    pg_get_expr(c.relpartbound, c.oid) AS partition_range,
                    COALESCE(s.n_live_tup, 0) AS live_rows,
                    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
                FROM pg_inherits i
                JOIN pg_class parent ON parent.oid = i.inhparent
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_namespace n ON n.oid = parent.relnamespace
                LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                WHERE n.nspname = 'core'
                  AND parent.relname = 'ledger_entries_partitioned'
                ORDER BY c.relname;
                """
            )
            partition_stats = cur.fetchall()

            pruning_sql = """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
            SELECT entry_id, account_id, direction, amount, posted_at
            FROM core.ledger_entries_partitioned
            WHERE posted_at >= '2026-10-01 00:00:00+00'
              AND posted_at <  '2026-11-01 00:00:00+00'
              AND amount >= 250000.0000
            ORDER BY posted_at DESC
            LIMIT 20;
            """
            cur.execute(pruning_sql)
            pruning_plan = "\n".join(row[0] for row in cur.fetchall())

    print("3/4 Verifying live PostgreSQL streaming physical replication (Primary 5432 -> Replica 5433)...")
    replica_port = int(os.getenv("PGREPLICA_PORT", "5433"))
    replica_dsn = cfg.postgres.dsn(port_override=replica_port)

    marker_id = f"repl-probe-{uuid.uuid4().hex[:10]}"
    replication_evidence: dict = {"replica_tested": False}

    try:
        with client.connect(database="postgres", use_admin=True) as primary_admin:
            with primary_admin.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        pid,
                        usename,
                        application_name,
                        client_addr::text,
                        state,
                        sync_state,
                        sent_lsn::text,
                        write_lsn::text,
                        flush_lsn::text,
                        replay_lsn::text
                    FROM pg_stat_replication;
                    """
                )
                repl_rows = cur.fetchall()

        with client.connect() as primary_conn:
            with primary_conn.transaction():
                with primary_conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO core.audit_logs (entity_name, entity_id, action, new_state)
                        VALUES ('replication_probe', %s, 'INSERT', %s::jsonb)
                        """,
                        (marker_id, json.dumps({"probe": marker_id, "source_port": cfg.postgres.port})),
                    )

        # Connect to standby replica and verify hot standby + propagated row + read-only block
        with psycopg.connect(replica_dsn, connect_timeout=5) as standby_conn:
            with standby_conn.cursor() as cur:
                cur.execute("SELECT pg_is_in_recovery(), inet_server_port()")
                in_recovery, srv_port = cur.fetchone()

            found_on_replica = False
            for _ in range(20):
                with standby_conn.cursor() as cur:
                    cur.execute(
                        "SELECT entity_id, recorded_at::text FROM core.audit_logs WHERE entity_id = %s",
                        (marker_id,),
                    )
                    hit = cur.fetchone()
                if hit is not None:
                    found_on_replica = True
                    break
                time.sleep(0.1)

            readonly_guard = "FAILED"
            try:
                with standby_conn.transaction():
                    with standby_conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO core.audit_logs (entity_name, entity_id, action, new_state)
                            VALUES ('readonly_test', 'blocked', 'INSERT', '{}'::jsonb)
                            """
                        )
            except psycopg.Error as exc:
                readonly_guard = f"PASS (SQLSTATE {exc.sqlstate}: {str(exc).splitlines()[0]})"

        replication_evidence = {
            "replica_tested": True,
            "pg_stat_replication": [
                {
                    "pid": r[0],
                    "usename": r[1],
                    "application_name": r[2],
                    "client_addr": r[3],
                    "state": r[4],
                    "sync_state": r[5],
                    "sent_lsn": r[6],
                    "write_lsn": r[7],
                    "flush_lsn": r[8],
                    "replay_lsn": r[9],
                }
                for r in repl_rows
            ],
            "standby_in_recovery": bool(in_recovery),
            "standby_port": srv_port,
            "marker_propagated": found_on_replica,
            "marker_id": marker_id,
            "standby_readonly_guard": readonly_guard,
        }
    except Exception as exc:  # noqa: BLE001
        replication_evidence = {
            "replica_tested": False,
            "note": f"Standby on port {replica_port} not active: {exc}",
        }

    print("4/4 Exporting Portfolio 5 evidence...")
    md_lines = [
        "# Portfolio 5: Partitioning & Streaming Replication Evidence",
        "",
        "## 1. Declarative Monthly Range Partitions (`core.ledger_entries_partitioned`)",
        "| Partition | Range Bounds | Live Rows | Total Size |",
        "| :--- | :--- | ---: | ---: |",
    ]
    for p_name, p_range, p_rows, p_size in partition_stats:
        md_lines.append(f"| `{p_name}` | `{p_range}` | {p_rows:,} | {p_size} |")

    md_lines.extend(
        [
            "",
            "## 2. Partition Pruning Execution Plan (October 2026 Filter Only)",
            "```text",
            pruning_plan,
            "```",
            "",
            "## 3. Live Physical Streaming Replication Verification",
        ]
    )

    if replication_evidence.get("replica_tested"):
        md_lines.extend(
            [
                f"- **Standby `pg_is_in_recovery()`:** `{replication_evidence['standby_in_recovery']}` (port `{replication_evidence['standby_port']}`)",
                f"- **Primary-to-Standby WAL Marker Propagated (`{marker_id}`):** `{replication_evidence['marker_propagated']}`",
                f"- **Standby Read-Only Guardrail:** `{replication_evidence['standby_readonly_guard']}`",
                "",
                "### `pg_stat_replication` on Primary",
                "| PID | User | App | Client | State | Sync | Sent LSN | Replay LSN |",
                "| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for rep in replication_evidence["pg_stat_replication"]:
            md_lines.append(
                f"| {rep['pid']} | {rep['usename']} | {rep['application_name']} | {rep['client_addr']} | "
                f"`{rep['state']}` | `{rep['sync_state']}` | `{rep['sent_lsn']}` | `{rep['replay_lsn']}` |"
            )
    else:
        md_lines.append(f"- **Replication Status:** {replication_evidence.get('note')}")

    (evidence_dir / "portfolio_5_evidence.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (evidence_dir / "portfolio_5_evidence.json").write_text(
        json.dumps(
            {
                "partitions": partition_stats,
                "pruning_plan": pruning_plan,
                "replication": replication_evidence,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Portfolio 5 evidence exported to {evidence_dir}")


if __name__ == "__main__":
    main()
