"""Portfolio 1 runner: applies core schema migrations and exports verification evidence."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path

import psycopg

from core.config import load_config
from core.postgres_client import PostgresClient

_P1_SEED_REFS = (
    "NP-INIT-0001",
    "NP-TXN-1001",
    "NP-TXN-1002",
    "NP-TXN-1003",
    "NP-REV-1003",
)
_P1_SEED_ACCOUNTS = (
    "9000000000",
    "9000000001",
    "3010000001",
    "3010000002",
    "3010000003",
)
_P1_CORE_TABLES = (
    "currencies",
    "kyc_tiers",
    "account_types",
    "customers",
    "accounts",
    "transactions",
    "ledger_entries",
    "audit_logs",
)


def _reset_relational_schema(client: PostgresClient) -> None:
    """Drop and cleanly reset the core schema and migration ledger for full E2E runs."""
    with client.connect(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS core CASCADE;")
            cur.execute("DROP TABLE IF EXISTS public.schema_migrations CASCADE;")


def _verify_guardrails(client: PostgresClient) -> dict[str, str]:
    """Confirm database-layer immutability and CHECK constraints reject invalid writes."""
    checks: dict[str, str] = {}
    with client.connect() as conn:
        # 1. Verify append-only ledger_entries rejects UPDATE
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("UPDATE core.ledger_entries SET amount = 1.00 WHERE entry_id = 1")
            checks["ledger_update_blocked"] = "FAILED (unexpectedly allowed)"
        except psycopg.Error as exc:
            checks["ledger_update_blocked"] = f"PASS (SQLSTATE {exc.sqlstate}: {str(exc).splitlines()[0]})"

        # 2. Verify negative wallet balance is rejected by CHECK constraint
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE core.accounts SET balance = -10.00 WHERE account_number = '3010000001'"
                    )
            checks["negative_wallet_blocked"] = "FAILED (unexpectedly allowed)"
        except psycopg.Error as exc:
            checks["negative_wallet_blocked"] = f"PASS (SQLSTATE {exc.sqlstate}: {str(exc).splitlines()[0]})"

        # 3. Verify closed-loop global balance sum = 0.0000 (excluding P3 intentional anomaly if present)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(variance), 0)
                FROM core.v_account_reconciliation r
                JOIN core.accounts a ON a.account_id = r.account_id
                LEFT JOIN core.customers c ON c.customer_id = a.customer_id
                WHERE COALESCE(c.full_name, '') NOT LIKE 'P3 LostUpdate%'
                  AND r.variance <> 0
                """
            )
            bad_recon_count, bad_recon_sum = cur.fetchone()
            assert bad_recon_count == 0, (
                f"Found {bad_recon_count} unreconciled accounts (variance sum {bad_recon_sum})"
            )

            cur.execute(
                """
                SELECT COALESCE(SUM(a.balance), 0),
                       EXISTS(
                           SELECT 1 FROM core.customers WHERE full_name LIKE 'P3 LostUpdate%'
                       )
                FROM core.accounts a
                """
            )
            total_system_balance, has_p3_anomaly = cur.fetchone()
            total_system_balance = Decimal(total_system_balance)
            if has_p3_anomaly:
                checks["closed_loop_system_sum"] = (
                    f"PASS (0 non-anomaly account variance; raw SUM={total_system_balance} reflects P3 LostUpdate demo)"
                )
            else:
                assert total_system_balance == Decimal("0.0000"), f"System imbalance: {total_system_balance}"
                checks["closed_loop_system_sum"] = f"PASS (SUM(balance) = {total_system_balance})"

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and verify Portfolio 1 schema and invariants.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop core schema and public.schema_migrations before re-applying from scratch.",
    )
    args = parser.parse_args()

    portfolio_dir = Path(__file__).resolve().parent
    sql_dir = portfolio_dir / "sql"
    evidence_dir = portfolio_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    client = PostgresClient(cfg)
    client.ensure_database()
    if args.reset:
        _reset_relational_schema(client)

    migration_files = [
        sql_dir / "001_init_schema.sql",
        sql_dir / "002_core_tables.sql",
        sql_dir / "003_triggers_and_invariants.sql",
        sql_dir / "004_seed_sample_data.sql",
    ]
    applied = client.apply_migrations(sql_dir, files=migration_files)

    report_lines = [
        "# Portfolio 1 Verification Output",
        "",
        f"Applied migrations in this run: {[m.filename for m in applied]}",
        "",
    ]

    with client.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM core.v_transaction_trial_balance
                WHERE net_imbalance <> 0
                """
            )
            imbalanced_txns = cur.fetchone()[0]
            assert imbalanced_txns == 0, f"Found {imbalanced_txns} transactions with non-zero imbalance"

            cur.execute(
                """
                SELECT reference_code, transaction_type::text, status::text,
                       total_debits::text, total_credits::text, net_imbalance::text
                FROM core.v_transaction_trial_balance
                WHERE reference_code = ANY(%s)
                ORDER BY reference_code
                """,
                (list(_P1_SEED_REFS),),
            )
            trial_rows = cur.fetchall()

            cur.execute(
                """
                SELECT account_number, account_type_code, stored_balance::text,
                       ledger_computed_balance::text, variance::text
                FROM core.v_account_reconciliation
                WHERE account_number = ANY(%s)
                ORDER BY account_number
                """,
                (list(_P1_SEED_ACCOUNTS),),
            )
            recon_rows = cur.fetchall()

            cur.execute(
                """
                SELECT tc.table_name, tc.constraint_name, tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_schema = 'core'
                  AND tc.table_name = ANY(%s)
                ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
                """,
                (list(_P1_CORE_TABLES),),
            )
            constraint_rows = cur.fetchall()

    report_lines.append("## Double-Entry Trial Balance (`core.v_transaction_trial_balance`)")
    report_lines.append("| Reference | Type | Status | Debits | Credits | Net Imbalance |")
    report_lines.append("| :--- | :--- | :--- | ---: | ---: | ---: |")
    for row in trial_rows:
        report_lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")

    report_lines.append("\n## Account Ledger Reconciliation (`core.v_account_reconciliation`)")
    report_lines.append("| Account Number | Type | Stored Balance | Ledger Computed | Variance |")
    report_lines.append("| :--- | :--- | ---: | ---: | ---: |")
    for row in recon_rows:
        report_lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")

    report_lines.append(f"\nTotal active constraints verified in `core`: **{len(constraint_rows)}**")

    guardrail_results = _verify_guardrails(client)
    report_lines.append("\n## Engine-Level Guardrail Verification")
    for check_name, outcome in guardrail_results.items():
        report_lines.append(f"- **{check_name}:** {outcome}")

    assert all(Decimal(row[5]) == Decimal("0") for row in trial_rows), "Found non-zero transaction imbalance"
    assert all(Decimal(row[4]) == Decimal("0") for row in recon_rows), "Found account ledger variance"

    (evidence_dir / "portfolio_1_verification.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    (evidence_dir / "portfolio_1_verification.json").write_text(
        json.dumps(
            {
                "trial_balance": trial_rows,
                "account_reconciliation": recon_rows,
                "constraint_count": len(constraint_rows),
                "guardrails": guardrail_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Portfolio 1 verified and exported to {evidence_dir}")


if __name__ == "__main__":
    main()
