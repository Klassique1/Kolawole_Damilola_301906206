# Portfolio 2: Query Processing and Optimisation

> **Case Study:** NovaPay Fintech Ltd (`novapay_core`)
> **Engine:** PostgreSQL 17.11
> **Dataset Scale:** `100,005` transactions, `190,210` double-entry ledger postings, `2,005` accounts, `2,003` customers

---

## 1. Analytical & Operational Query Workload

Four production-representative queries ([queries.py](queries.py)) were evaluated before and after index design using `EXPLAIN (ANALYZE, BUFFERS)` via [core/benchmark_runner.py](../core/benchmark_runner.py):

1. **Q1 — Paginated Wallet Statement:** Retrieves the 25 most recent ledger postings for a customer wallet sorted by `(posted_at DESC, entry_id DESC)`.
2. **Q2 — High-Value Failed & Pending Settlement Screening:** Scans for `FAILED` or `PENDING` transfers `>= 250,000 NGN` in the last 30 days (~5% row skew).
3. **Q3 — 14-Day Completed Settlement & Fee Reconciliation:** Aggregates completed transaction count, gross volume, and fee revenue grouped by `transaction_type`.
4. **Q4 — Case-Insensitive Customer KYC & Wallet Exposure Lookup:** Joins `customers`, `kyc_tiers`, and `accounts` filtering on `lower(c.email)`.

---

## 2. Indexing Strategy & Trade-Offs

Defined in [sql/003_optimisation_indexes.sql](sql/003_optimisation_indexes.sql):

| Index Name | Technique | Size | Why It Works & Trade-Off |
| :--- | :--- | ---: | :--- |
| `idx_ledger_account_posted_desc` | Composite + `INCLUDE` Covering Index | 19 MB | Matches `WHERE account_id = ? ORDER BY posted_at DESC, entry_id DESC` and includes display columns so PostgreSQL performs an **`Index Only Scan`** (`Heap Fetches: 0`) with zero `Sort` node. Trade-off: adds B-Tree maintenance overhead on ledger inserts. |
| `idx_txn_non_completed_recent` | Partial Composite Index (`WHERE status IN ('FAILED', 'PENDING')`) | **168 kB** | Excludes ~95% `COMPLETED` transactions, shrinking index footprint dramatically and eliminating write amplification on normal completed transfers. |
| `idx_txn_status_created_cover` | Composite + `INCLUDE` Covering Index | 4,864 kB | Covers `(status, created_at)` range filters and includes `(transaction_type, amount, fee_amount)` for fast `Index Only Scan` aggregations. |
| `idx_customers_lower_email` | Functional Expression Index (`lower(email)`) | 120 kB | A standard `UNIQUE (email)` index cannot satisfy `WHERE lower(email) = ...`; indexing the expression enables direct `Index Scan`. |
| `idx_accounts_customer_id` | Partial FK B-Tree Index (`WHERE customer_id IS NOT NULL`) | 80 kB | PostgreSQL does not automatically index foreign keys; this eliminates sequential scans on `core.accounts` during customer joins while skipping internal clearing accounts. |

---

## 3. Observed Performance Results (Before vs. After)

Full raw plans and sample outputs:
- [evidence/benchmark_comparison.md](evidence/benchmark_comparison.md)
- [evidence/benchmark_comparison.json](evidence/benchmark_comparison.json)
- [evidence/index_and_results.md](evidence/index_and_results.md)

| Query | Baseline Exec (ms) | Optimised Exec (ms) | Speedup | Scan Transition | Shared Buffers (Before → After) |
| :--- | ---: | ---: | ---: | :--- | :--- |
| **Q1:** Paginated Wallet Statement | 9.691 | 0.038 | **255.03x** | `Seq Scan` → `Index Only Scan` | 2,928 → 4 |
| **Q2:** High-Value Failed/Pending | 13.394 | 0.116 | **115.47x** | `Seq Scan` → `Bitmap Heap/Index Scan` | 2,509 → 21 |
| **Q3:** 14-Day Reconciliation | 27.509 | 2.825 | **9.74x** | `Seq Scan` → `Index Only Scan` | 2,509 → 48 |
| **Q4:** Case-Insensitive KYC Lookup | 0.824 | 0.045 | **18.31x** | `Seq Scan + Index Scan` → `Index Scan` | 103 → 8 |

---

## 4. How to Reproduce

```powershell
python portfolio-2-query-optimisation/run_portfolio_2.py
```

The script idempotently seeds the 100k dataset, drops Portfolio 2 indexes to capture a fresh baseline after `VACUUM ANALYZE`, reapplies the indexes, captures optimised `EXPLAIN (ANALYZE, BUFFERS)` plans, and regenerates all evidence files.
