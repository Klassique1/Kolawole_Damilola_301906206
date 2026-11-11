# Portfolio 3: Transactions and Concurrency

> **Case Study:** NovaPay Fintech Ltd (`novapay_core`)
> **Engine:** PostgreSQL 17.11 (MVCC, Row-Level Locks, Serializable Snapshot Isolation)

---

## 1. Objectives & Fintech Reliability Requirements

In payment systems, partial writes, dirty/stale reads, lost updates (double-spending), and deadlocks cause real financial losses. Portfolio 3 demonstrates:
1. **Atomicity (`COMMIT` & `ROLLBACK`)** across multi-table balance updates and double-entry ledger postings.
2. **Concurrency Hazard Reproduction** (Lost Update / Double-Spend under `READ COMMITTED`).
3. **Pessimistic Concurrency Control** (`SELECT ... FOR UPDATE`) and **Deadlock Prevention** via deterministic resource lock ordering.
4. **Optimistic Concurrency Control** (`SERIALIZABLE` isolation / SSI with `SQLSTATE 40001` retry backoff).

---

## 2. Scenarios Implemented & Verified

- Standalone SQL script: [sql/001_atomic_commit_rollback.sql](sql/001_atomic_commit_rollback.sql)
- Automated barrier-synchronized concurrency suite: [scenarios/run_portfolio_3.py](scenarios/run_portfolio_3.py)
- Reusable multi-thread harness: [core/concurrency_runner.py](../core/concurrency_runner.py)
- Captured evidence report: [evidence/portfolio_3_concurrency_report.md](evidence/portfolio_3_concurrency_report.md)

### Summary of Observed Outcomes

| Scenario | Isolation & Control | What Happened | Invariant Verified? |
| :--- | :--- | :--- | :---: |
| **1. Atomic `COMMIT` & `ROLLBACK`** | `READ COMMITTED` + `CHECK` constraint | 25,000 NGN transfer committed atomically; subsequent 999,999 NGN overdraft failed `SQLSTATE 23514` (`accounts_check`) and rolled back the preceding credit completely. | **Yes** |
| **2. Unlocked Lost Update (Buggy Baseline)** | `READ COMMITTED`, no row lock | Two concurrent 40,000 NGN transfers both read stale `50,000.00 NGN` simultaneously and committed, disbursing 80,000 NGN (`stored_balance = 10,000` vs. `ledger_computed_balance = -30,000`, `variance = 40,000`). | **No** *(Anomaly reproduced)* |
| **3. Pessimistic Row Locking** | `READ COMMITTED` + `SELECT ... FOR UPDATE` | First session acquired exclusive row lock and debited 40,000; second session blocked until commit, observed `10,000 < 40,000`, and aborted cleanly. | **Yes** (`0.0000` variance) |
| **4A. Unordered Bidirectional Locks** | `READ COMMITTED` (X→Y vs. Y→X) | Circular lock wait detected by PostgreSQL deadlock detector (`SQLSTATE 40P01: deadlock detected`). | **Yes** *(Victim aborted)* |
| **4B. Ordered Resource Locking** | `ORDER BY account_id ASC FOR UPDATE` | Both concurrent bidirectional transfers (15,000 and 10,000) acquired locks in canonical UUID order and committed with **zero deadlocks**. | **Yes** (`0.0000` variance) |
| **5. `SERIALIZABLE` (SSI + Retry)** | `SERIALIZABLE` + retry backoff | SSI detected concurrent write conflict (`SQLSTATE 40001`), rolled back one worker, and automatic retry observed `10,000 < 40,000` and rejected safely. | **Yes** (`0.0000` variance) |

---

## 3. Architectural Comparison: Pessimistic vs. Optimistic Control

- **`SELECT ... FOR UPDATE` with Canonical Ordering:** Best for hot-wallet / high-contention payment accounts where serialization retries would waste CPU; prevents deadlocks mathematically by enforcing a global lock acquisition order (`account_id ASC`).
- **`SERIALIZABLE` (SSI):** Best when business invariants span dynamic multi-row predicates (preventing phantom/write-skew anomalies) without manually locking every row upfront—requires an application retry loop for `SQLSTATE 40001`.

---

## 4. How to Reproduce

```powershell
python portfolio-3-transactions-concurrency/scenarios/run_portfolio_3.py
```
