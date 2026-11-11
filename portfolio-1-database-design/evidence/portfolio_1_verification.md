# Portfolio 1 Verification Output

Applied migrations in this run: ['001_init_schema.sql', '002_core_tables.sql', '003_triggers_and_invariants.sql', '004_seed_sample_data.sql']

## Double-Entry Trial Balance (`core.v_transaction_trial_balance`)
| Reference | Type | Status | Debits | Credits | Net Imbalance |
| :--- | :--- | :--- | ---: | ---: | ---: |
| NP-INIT-0001 | DEPOSIT | COMPLETED | 10000000.0000 | 10000000.0000 | 0.0000 |
| NP-REV-1003 | REVERSAL | COMPLETED | 25000.0000 | 25000.0000 | 0.0000 |
| NP-TXN-1001 | TRANSFER | COMPLETED | 500000.0000 | 500000.0000 | 0.0000 |
| NP-TXN-1002 | TRANSFER | COMPLETED | 150000.0000 | 150000.0000 | 0.0000 |
| NP-TXN-1003 | TRANSFER | REVERSED | 25000.0000 | 25000.0000 | 0.0000 |

## Account Ledger Reconciliation (`core.v_account_reconciliation`)
| Account Number | Type | Stored Balance | Ledger Computed | Variance |
| :--- | :--- | ---: | ---: | ---: |
| 3010000001 | SAVINGS_WALLET | 350000.0000 | 350000.0000 | 0.0000 |
| 3010000002 | CURRENT_WALLET | 150000.0000 | 150000.0000 | 0.0000 |
| 3010000003 | SAVINGS_WALLET | 0.0000 | 0.0000 | 0.0000 |
| 9000000000 | EXTERNAL_CONTRA | -10000000.0000 | -10000000.0000 | 0.0000 |
| 9000000001 | SETTLEMENT_POOL | 9500000.0000 | 9500000.0000 | 0.0000 |

Total active constraints verified in `core`: **104**

## Engine-Level Guardrail Verification
- **ledger_update_blocked:** PASS (SQLSTATE 42501: core.ledger_entries is append-only; UPDATE operations are prohibited)
- **negative_wallet_blocked:** PASS (SQLSTATE 23514: new row for relation "accounts" violates check constraint "accounts_check")
- **closed_loop_system_sum:** PASS (SUM(balance) = 0.0000)
