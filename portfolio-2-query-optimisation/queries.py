"""Production Fintech SQL queries benchmarked in Portfolio 2."""

from __future__ import annotations


def build_benchmark_queries(sample_account_id: str) -> list[tuple[str, str]]:
    """Return the 4 representative NovaPay analytical & operational SQL queries."""
    return [
        (
            "Q1: Paginated Wallet Statement (Last 25 Ledger Postings)",
            f"""
            SELECT
                entry_id,
                direction,
                amount,
                balance_after,
                narration,
                posted_at
            FROM core.ledger_entries
            WHERE account_id = '{sample_account_id}'::uuid
            ORDER BY posted_at DESC, entry_id DESC
            LIMIT 25;
            """,
        ),
        (
            "Q2: High-Value Failed & Pending Settlements (Last 30 Days)",
            """
            SELECT
                transaction_id,
                reference_code,
                status,
                amount,
                failure_reason,
                created_at
            FROM core.transactions
            WHERE status IN ('FAILED', 'PENDING')
              AND created_at >= now() - INTERVAL '30 days'
              AND amount >= 250000.0000
            ORDER BY created_at DESC
            LIMIT 50;
            """,
        ),
        (
            "Q3: 14-Day Completed Settlement & Fee Reconciliation",
            """
            SELECT
                transaction_type,
                COUNT(*)        AS txn_count,
                SUM(amount)     AS gross_volume,
                SUM(fee_amount) AS total_fees
            FROM core.transactions
            WHERE status = 'COMPLETED'
              AND created_at >= now() - INTERVAL '14 days'
            GROUP BY transaction_type
            ORDER BY gross_volume DESC;
            """,
        ),
        (
            "Q4: Case-Insensitive Customer KYC & Wallet Exposure Lookup",
            """
            SELECT
                c.customer_id,
                c.full_name,
                c.email,
                k.tier_name,
                k.daily_txn_limit,
                a.account_number,
                a.account_type_code,
                a.balance
            FROM core.customers c
            JOIN core.kyc_tiers k ON k.tier_code = c.kyc_tier_code
            JOIN core.accounts a  ON a.customer_id = c.customer_id
            WHERE lower(c.email) = lower('BENCH_CUST_0420@novapay-demo.ng');
            """,
        ),
    ]
