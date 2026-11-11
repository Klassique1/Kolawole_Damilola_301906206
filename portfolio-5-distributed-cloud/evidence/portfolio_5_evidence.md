# Portfolio 5: Partitioning & Streaming Replication Evidence

## 1. Declarative Monthly Range Partitions (`core.ledger_entries_partitioned`)
| Partition | Range Bounds | Live Rows | Total Size |
| :--- | :--- | ---: | ---: |
| `ledger_entries_p_2026_05` | `FOR VALUES FROM ('2026-05-01 01:00:00+01') TO ('2026-06-01 01:00:00+01')` | 19,882 | 4552 kB |
| `ledger_entries_p_2026_06` | `FOR VALUES FROM ('2026-06-01 01:00:00+01') TO ('2026-07-01 01:00:00+01')` | 31,210 | 6928 kB |
| `ledger_entries_p_2026_07` | `FOR VALUES FROM ('2026-07-01 01:00:00+01') TO ('2026-08-01 01:00:00+01')` | 32,244 | 7168 kB |
| `ledger_entries_p_2026_08` | `FOR VALUES FROM ('2026-08-01 01:00:00+01') TO ('2026-09-01 01:00:00+01')` | 32,244 | 7176 kB |
| `ledger_entries_p_2026_09` | `FOR VALUES FROM ('2026-09-01 01:00:00+01') TO ('2026-10-01 01:00:00+01')` | 31,210 | 6928 kB |
| `ledger_entries_p_2026_10` | `FOR VALUES FROM ('2026-10-01 01:00:00+01') TO ('2026-11-01 01:00:00+01')` | 32,244 | 7168 kB |
| `ledger_entries_p_2026_11` | `FOR VALUES FROM ('2026-11-01 01:00:00+01') TO ('2026-12-01 01:00:00+01')` | 11,204 | 2528 kB |
| `ledger_entries_p_2026_12` | `FOR VALUES FROM ('2026-12-01 01:00:00+01') TO ('2027-01-01 01:00:00+01')` | 0 | 16 kB |
| `ledger_entries_p_default` | `DEFAULT` | 0 | 16 kB |

## 2. Partition Pruning Execution Plan (October 2026 Filter Only)
```text
Limit  (cost=1077.50..1077.55 rows=20 width=41) (actual time=6.098..6.101 rows=20 loops=1)
  Buffers: shared hit=500
  ->  Sort  (cost=1077.50..1079.03 rows=610 width=41) (actual time=6.088..6.090 rows=20 loops=1)
        Sort Key: ledger_entries_partitioned.posted_at DESC
        Sort Method: top-N heapsort  Memory: 27kB
        Buffers: shared hit=500
        ->  Seq Scan on ledger_entries_p_2026_10 ledger_entries_partitioned  (cost=0.00..1061.27 rows=610 width=41) (actual time=0.019..5.967 rows=610 loops=1)
              Filter: ((posted_at >= '2026-10-01 01:00:00+01'::timestamp with time zone) AND (posted_at < '2026-11-01 01:00:00+01'::timestamp with time zone) AND (amount >= 250000.0000))
              Rows Removed by Filter: 31634
              Buffers: shared hit=497
Planning:
  Buffers: shared hit=183
Planning Time: 2.329 ms
Execution Time: 6.130 ms
```

## 3. Live Physical Streaming Replication Verification
- **Standby `pg_is_in_recovery()`:** `True` (port `5433`)
- **Primary-to-Standby WAL Marker Propagated (`repl-probe-cee426c704`):** `True`
- **Standby Read-Only Guardrail:** `PASS (SQLSTATE 25006: cannot execute INSERT in a read-only transaction)`

### `pg_stat_replication` on Primary
| PID | User | App | Client | State | Sync | Sent LSN | Replay LSN |
| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 14236 | postgres | walreceiver | 127.0.0.1/32 | `streaming` | `async` | `0/2B0B0770` | `0/2B0B0770` |
