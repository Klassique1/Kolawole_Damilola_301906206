# Portfolio 3: Transactions & Concurrency Verification Report

## Scenario 1: Atomic `COMMIT` & `ROLLBACK`
- **Accounts:** `5288303692` -> `5628448696`
- **COMMIT Outcome:** Locked transfer 25000.0000 succeeded (100000.0000 -> 75000.0000)
- **ROLLBACK Outcome:** Rolled back cleanly on SQLSTATE 23514: new row for relation "accounts" violates check constraint "accounts_check"
- **Final Balances (After Both Operations):** `{'5288303692': '75000.0000', '5628448696': '45000.0000'}`
- **Atomicity Verified:** `True`

## Scenario 2: Unlocked READ COMMITTED (Lost Update / Double-Spend)
- **Isolation Level:** `READ_COMMITTED`
- **Invariant Passed:** `False` (`stored_balance=10000.0000, ledger_computed_balance=-30000.0000, variance=40000.0000`)

| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |
| :--- | :---: | ---: | ---: | :--- | :--- |
| Worker-A | True | 1 | 201.00 | `00000` | Debited 40000.0000 from stale read 50000.0000 -> 10000.0000 |
| Worker-B | True | 1 | 185.45 | `00000` | Debited 40000.0000 from stale read 50000.0000 -> 10000.0000 |

## Scenario 3: Pessimistic Row Locking (SELECT ... FOR UPDATE)
- **Isolation Level:** `READ_COMMITTED`
- **Invariant Passed:** `True` (`stored_balance=10000.0000, ledger_computed_balance=10000.0000, variance=0.0000`)

| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |
| :--- | :---: | ---: | ---: | :--- | :--- |
| Worker-A | False | 1 | 106.66 | `N/A` | Insufficient balance (10000.0000 < 40000.0000); cleanly rejected |
| Worker-B | True | 1 | 105.28 | `00000` | Locked transfer 40000.0000 succeeded (50000.0000 -> 10000.0000) |

## Scenario 4A: Unordered Bidirectional Locking (Deadlock Triggered)
- **Isolation Level:** `READ_COMMITTED`
- **Invariant Passed:** `True` (`stored_balance=100000.0000, ledger_computed_balance=100000.0000, variance=0.0000`)

| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |
| :--- | :---: | ---: | ---: | :--- | :--- |
| Session-X-then-Y | False | 1 | 1078.37 | `40P01` | deadlock detected |
| Session-Y-then-X | True | 1 | 1076.90 | `00000` | Acquired both locks |

## Scenario 4B: Deterministic Ordered Locking (Zero Deadlocks)
- **Isolation Level:** `READ_COMMITTED`
- **Invariant Passed:** `True` (`stored_balance=95000.0000, ledger_computed_balance=95000.0000, variance=0.0000`)

| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |
| :--- | :---: | ---: | ---: | :--- | :--- |
| Session-X-to-Y | True | 1 | 75.85 | `00000` | Locked transfer 15000.0000 succeeded (100000.0000 -> 85000.0000) |
| Session-Y-to-X | True | 1 | 91.84 | `00000` | Locked transfer 10000.0000 succeeded (115000.0000 -> 105000.0000) |

## Scenario 5: SERIALIZABLE Isolation (SSI + Retry Backoff)
- **Isolation Level:** `SERIALIZABLE`
- **Invariant Passed:** `True` (`stored_balance=10000.0000, ledger_computed_balance=10000.0000, variance=0.0000`)

| Worker | Succeeded | Attempts | Elapsed (ms) | SQLSTATE | Outcome |
| :--- | :---: | ---: | ---: | :--- | :--- |
| Worker-A | True | 1 | 89.45 | `00000` | Debited 40000.0000 from stale read 50000.0000 -> 10000.0000 |
| Worker-B | False | 2 | 193.63 | `N/A` | Insufficient balance (10000.0000 < 40000.0000) (after retry from SQLSTATE 40001) |
