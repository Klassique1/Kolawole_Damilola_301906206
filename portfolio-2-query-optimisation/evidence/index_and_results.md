# Portfolio 2: Index Footprint & Sample Query Outputs

## Table & Storage Overview
| Table | Live Rows | Heap Size | Indexes Size | Total Size |
| :--- | ---: | ---: | ---: | ---: |
| `core.ledger_entries` | 190,210 | 23 MB | 37 MB | 60 MB |
| `core.transactions` | 100,005 | 20 MB | 22 MB | 41 MB |
| `core.audit_logs` | 2,003 | 896 kB | 64 kB | 992 kB |
| `core.accounts` | 2,005 | 512 kB | 368 kB | 912 kB |
| `core.customers` | 2,003 | 296 kB | 400 kB | 728 kB |
| `core.account_types` | 5 | 8192 bytes | 32 kB | 40 kB |
| `core.kyc_tiers` | 3 | 8192 bytes | 32 kB | 40 kB |
| `core.currencies` | 3 | 8192 bytes | 16 kB | 24 kB |

## Portfolio 2 Optimisation Indexes
| Table | Index Name | Size | Unique | Partial Predicate |
| :--- | :--- | ---: | :---: | :--- |
| `ledger_entries` | `idx_ledger_account_posted_desc` | 19 MB | False | *(full table)* |
| `transactions` | `idx_txn_status_created_cover` | 4864 kB | False | *(full table)* |
| `transactions` | `idx_txn_non_completed_recent` | 168 kB | False | `(status = ANY (ARRAY['FAILED'::core.transaction_status_enum, 'PENDING'::core.transaction_status_enum]))` |
| `customers` | `idx_customers_lower_email` | 120 kB | False | *(full table)* |
| `accounts` | `idx_accounts_customer_id` | 80 kB | False | `(customer_id IS NOT NULL)` |

## Sample Query Result Rows

### Q1: Paginated Wallet Statement (Last 25 Ledger Postings)
| entry_id | direction | amount | balance_after | narration | posted_at |
| --- | --- | --- | --- | --- | --- |
| 41820 | DEBIT | 3500.0000 | 4752400.0000 | Benchmark P2P transfer #96420 | 2026-11-08 21:24:06.977567+01:00 |
| 41819 | CREDIT | 1800.0000 | 4755900.0000 | Benchmark P2P transfer #96403 | 2026-11-08 20:39:24.169404+01:00 |
| 41818 | DEBIT | 1500.0000 | 4754100.0000 | Benchmark P2P transfer #94420 | 2026-11-05 05:43:42.487771+01:00 |
| 41817 | CREDIT | 1000.0000 | 4755600.0000 | Benchmark P2P transfer #94415 | 2026-11-05 05:30:33.426547+01:00 |
| 41816 | DEBIT | 4000.0000 | 4754600.0000 | Benchmark P2P transfer #92420 | 2026-11-01 14:03:17.997975+01:00 |

### Q2: High-Value Failed & Pending Settlements (Last 30 Days)
| transaction_id | reference_code | status | amount | failure_reason | created_at |
| --- | --- | --- | --- | --- | --- |
| ab57b7ed-02ff-4bca-a900-e0c6ebda1c6e | NP-BTXN-097997 | FAILED | 430000.0000 | Upstream NIP switch timeout | 2026-11-11 18:31:54.887771+01:00 |
| 517378b1-fede-40e3-a6d0-32b3eb35a6e8 | NP-BTXN-097096 | FAILED | 420000.0000 | Upstream NIP switch timeout | 2026-11-10 03:02:06.055118+01:00 |
| 3923cbc1-6bb0-433e-881d-2f89a150b822 | NP-BTXN-096195 | FAILED | 410000.0000 | Upstream NIP switch timeout | 2026-11-08 11:32:17.222465+01:00 |
| ca1fb0bc-c37f-4969-9b1f-887a7a9ecc64 | NP-BTXN-094499 | PENDING | 450000.0000 | None | 2026-11-05 09:11:27.655118+01:00 |
| 39a3ca15-3b77-4dca-8b82-6fb09086fcf1 | NP-BTXN-093598 | PENDING | 440000.0000 | None | 2026-11-03 17:41:38.822465+01:00 |

### Q3: 14-Day Completed Settlement & Fee Reconciliation
| transaction_type | txn_count | gross_volume | total_fees |
| --- | --- | --- | --- |
| TRANSFER | 7282 | 68103800.0000 | 72800.0000 |
| DEPOSIT | 1 | 10000000.0000 | 0.0000 |
| REVERSAL | 1 | 25000.0000 | 0.0000 |

### Q4: Case-Insensitive Customer KYC & Wallet Exposure Lookup
| customer_id | full_name | email | tier_name | daily_txn_limit | account_number | account_type_code | balance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2e9d925e-2e8d-47b3-91fb-b1c9abb0a8aa | Benchmark Customer 0420 | bench_cust_0420@novapay-demo.ng | Premium / Merchant (Full KYC) | 50000000.0000 | 4000000420 | CURRENT_WALLET | 4752400.0000 |
