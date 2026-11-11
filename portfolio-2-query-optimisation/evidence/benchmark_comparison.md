# Query Performance Comparison (Before vs. After Optimisation)

| Query | Baseline Exec (ms) | Optimised Exec (ms) | Speedup | Baseline Scan | Optimised Scan | Buffers (Before Hit/Read -> After Hit/Read) |
| :--- | ---: | ---: | ---: | :--- | :--- | :--- |
| Q1: Paginated Wallet Statement (Last 25 Ledger Postings) | 9.691 | 0.038 | 255.03x | Seq Scan | Index Only Scan | 2928/0 -> 4/0 |
| Q2: High-Value Failed & Pending Settlements (Last 30 Days) | 13.394 | 0.116 | 115.47x | Seq Scan | Bitmap Heap Scan + Bitmap Index Scan | 2509/0 -> 21/0 |
| Q3: 14-Day Completed Settlement & Fee Reconciliation | 27.509 | 2.825 | 9.74x | Seq Scan | Index Only Scan | 2509/0 -> 48/0 |
| Q4: Case-Insensitive Customer KYC & Wallet Exposure Lookup | 0.824 | 0.045 | 18.31x | Seq Scan + Index Scan | Index Scan | 103/0 -> 8/0 |

## Detailed Execution Plans

### Q1: Paginated Wallet Statement (Last 25 Ledger Postings)

#### Baseline Plan
```text
Limit  (cost=5308.25..5308.31 rows=25 width=60) (actual time=9.652..9.655 rows=25 loops=1)
  Buffers: shared hit=2928
  ->  Sort  (cost=5308.25..5308.48 rows=93 width=60) (actual time=9.650..9.652 rows=25 loops=1)
        Sort Key: posted_at DESC, entry_id DESC
        Sort Method: top-N heapsort  Memory: 31kB
        Buffers: shared hit=2928
        ->  Seq Scan on ledger_entries  (cost=0.00..5305.62 rows=93 width=60) (actual time=2.182..9.618 rows=99 loops=1)
              Filter: (account_id = '36c27cba-fdda-439e-b0d8-67d90e26f1a0'::uuid)
              Rows Removed by Filter: 190111
              Buffers: shared hit=2928
Planning Time: 0.211 ms
Execution Time: 9.691 ms
```
#### Optimised Plan
```text
Limit  (cost=0.42..3.01 rows=25 width=60) (actual time=0.015..0.019 rows=25 loops=1)
  Buffers: shared hit=4
  ->  Index Only Scan using idx_ledger_account_posted_desc on ledger_entries  (cost=0.42..10.05 rows=93 width=60) (actual time=0.014..0.017 rows=25 loops=1)
        Index Cond: (account_id = '36c27cba-fdda-439e-b0d8-67d90e26f1a0'::uuid)
        Heap Fetches: 0
        Buffers: shared hit=4
Planning Time: 0.088 ms
Execution Time: 0.038 ms
```

### Q2: High-Value Failed & Pending Settlements (Last 30 Days)

#### Baseline Plan
```text
Limit  (cost=4759.82..4759.89 rows=29 width=75) (actual time=13.366..13.369 rows=16 loops=1)
  Buffers: shared hit=2509
  ->  Sort  (cost=4759.82..4759.89 rows=29 width=75) (actual time=13.364..13.366 rows=16 loops=1)
        Sort Key: created_at DESC
        Sort Method: quicksort  Memory: 27kB
        Buffers: shared hit=2509
        ->  Seq Scan on transactions  (cost=0.00..4759.11 rows=29 width=75) (actual time=1.075..13.343 rows=16 loops=1)
              Filter: ((status = ANY ('{FAILED,PENDING}'::core.transaction_status_enum[])) AND (amount >= 250000.0000) AND (created_at >= (now() - '30 days'::interval)))
              Rows Removed by Filter: 99989
              Buffers: shared hit=2509
Planning Time: 0.177 ms
Execution Time: 13.394 ms
```
#### Optimised Plan
```text
Limit  (cost=139.21..139.29 rows=31 width=76) (actual time=0.092..0.095 rows=16 loops=1)
  Buffers: shared hit=21
  ->  Sort  (cost=139.21..139.29 rows=31 width=76) (actual time=0.092..0.093 rows=16 loops=1)
        Sort Key: created_at DESC
        Sort Method: quicksort  Memory: 27kB
        Buffers: shared hit=21
        ->  Bitmap Heap Scan on transactions  (cost=24.09..138.45 rows=31 width=76) (actual time=0.065..0.082 rows=16 loops=1)
              Recheck Cond: ((created_at >= (now() - '30 days'::interval)) AND (amount >= 250000.0000) AND (status = ANY ('{FAILED,PENDING}'::core.transaction_status_enum[])))
              Heap Blocks: exact=16
              Buffers: shared hit=21
              ->  Bitmap Index Scan on idx_txn_non_completed_recent  (cost=0.00..24.08 rows=31 width=0) (actual time=0.057..0.057 rows=16 loops=1)
                    Index Cond: ((created_at >= (now() - '30 days'::interval)) AND (amount >= 250000.0000))
                    Buffers: shared hit=5
Planning Time: 0.128 ms
Execution Time: 0.116 ms
```

### Q3: 14-Day Completed Settlement & Fee Reconciliation

#### Baseline Plan
```text
Sort  (cost=4580.81..4580.82 rows=2 width=76) (actual time=27.482..27.483 rows=3 loops=1)
  Sort Key: (sum(amount)) DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=2509
  ->  HashAggregate  (cost=4580.77..4580.80 rows=2 width=76) (actual time=27.470..27.473 rows=3 loops=1)
        Group Key: transaction_type
        Batches: 1  Memory Usage: 24kB
        Buffers: shared hit=2509
        ->  Seq Scan on transactions  (cost=0.00..4509.10 rows=7167 width=13) (actual time=0.008..25.783 rows=7284 loops=1)
              Filter: ((status = 'COMPLETED'::core.transaction_status_enum) AND (created_at >= (now() - '14 days'::interval)))
              Rows Removed by Filter: 92721
              Buffers: shared hit=2509
Planning Time: 0.107 ms
Execution Time: 27.509 ms
```
#### Optimised Plan
```text
Sort  (cost=388.95..388.96 rows=2 width=76) (actual time=2.778..2.778 rows=3 loops=1)
  Sort Key: (sum(amount)) DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=48
  ->  HashAggregate  (cost=388.91..388.94 rows=2 width=76) (actual time=2.768..2.770 rows=3 loops=1)
        Group Key: transaction_type
        Batches: 1  Memory Usage: 24kB
        Buffers: shared hit=48
        ->  Index Only Scan using idx_txn_status_created_cover on transactions  (cost=0.42..318.08 rows=7083 width=13) (actual time=0.027..1.061 rows=7284 loops=1)
              Index Cond: ((status = 'COMPLETED'::core.transaction_status_enum) AND (created_at >= (now() - '14 days'::interval)))
              Heap Fetches: 0
              Buffers: shared hit=48
Planning Time: 0.194 ms
Execution Time: 2.825 ms
```

### Q4: Case-Insensitive Customer KYC & Wallet Exposure Lookup

#### Baseline Plan
```text
Nested Loop  (cost=67.33..170.67 rows=10 width=268) (actual time=0.769..0.789 rows=1 loops=1)
  Buffers: shared hit=103
  ->  Hash Join  (cost=67.17..156.49 rows=10 width=109) (actual time=0.757..0.777 rows=1 loops=1)
        Hash Cond: (a.customer_id = c.customer_id)
        Buffers: shared hit=101
        ->  Seq Scan on accounts a  (cost=0.00..84.05 rows=2005 width=48) (actual time=0.020..0.129 rows=2005 loops=1)
              Buffers: shared hit=64
        ->  Hash  (cost=67.05..67.05 rows=10 width=77) (actual time=0.481..0.481 rows=1 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 9kB
              Buffers: shared hit=37
              ->  Seq Scan on customers c  (cost=0.00..67.05 rows=10 width=77) (actual time=0.137..0.476 rows=1 loops=1)
                    Filter: (lower((email)::text) = 'bench_cust_0420@novapay-demo.ng'::text)
                    Rows Removed by Filter: 2002
                    Buffers: shared hit=37
  ->  Memoize  (cost=0.16..3.77 rows=1 width=216) (actual time=0.011..0.011 rows=1 loops=1)
        Cache Key: c.kyc_tier_code
        Cache Mode: logical
        Hits: 0  Misses: 1  Evictions: 0  Overflows: 0  Memory Usage: 1kB
        Buffers: shared hit=2
        ->  Index Scan using kyc_tiers_pkey on kyc_tiers k  (cost=0.15..3.76 rows=1 width=216) (actual time=0.009..0.009 rows=1 loops=1)
              Index Cond: ((tier_code)::text = (c.kyc_tier_code)::text)
              Buffers: shared hit=2
Planning:
  Buffers: shared hit=6
Planning Time: 0.392 ms
Execution Time: 0.824 ms
```
#### Optimised Plan
```text
Nested Loop  (cost=0.70..24.82 rows=1 width=268) (actual time=0.022..0.024 rows=1 loops=1)
  Buffers: shared hit=8
  ->  Nested Loop  (cost=0.43..16.52 rows=1 width=236) (actual time=0.016..0.017 rows=1 loops=1)
        Buffers: shared hit=5
        ->  Index Scan using idx_customers_lower_email on customers c  (cost=0.28..8.29 rows=1 width=77) (actual time=0.009..0.009 rows=1 loops=1)
              Index Cond: (lower((email)::text) = 'bench_cust_0420@novapay-demo.ng'::text)
              Buffers: shared hit=3
        ->  Index Scan using kyc_tiers_pkey on kyc_tiers k  (cost=0.15..8.17 rows=1 width=216) (actual time=0.005..0.005 rows=1 loops=1)
              Index Cond: ((tier_code)::text = (c.kyc_tier_code)::text)
              Buffers: shared hit=2
  ->  Index Scan using idx_accounts_customer_id on accounts a  (cost=0.28..8.29 rows=1 width=48) (actual time=0.006..0.006 rows=1 loops=1)
        Index Cond: (customer_id = c.customer_id)
        Buffers: shared hit=3
Planning:
  Buffers: shared hit=6
Planning Time: 0.222 ms
Execution Time: 0.045 ms
```
