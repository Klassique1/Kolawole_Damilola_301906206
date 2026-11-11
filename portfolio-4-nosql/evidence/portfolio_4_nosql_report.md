# Portfolio 4: MongoDB Verification & Benchmark Evidence

- **Database / Collection:** `novapay_telemetry.fraud_risk_events`
- **Total Documents:** `25,000`
- **JSON Schema Validation Guardrail:** `PASS (MongoDB rejected invalid doc with code 121: Document failed validation)`

## Index Performance (`decision = 'BLOCK' AND channel = 'MOBILE_APP' ORDER BY created_at DESC`)
| Phase | Winning Plan | Exec Time (ms) | Docs Examined | Keys Examined | Returned |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Baseline (No Index) | `SORT -> COLLSCAN` | 24 | 25,000 | 0 | 625 |
| Optimised (ESR Compound) | `FETCH -> IXSCAN (idx_decision_channel_created)` | 8 | 625 | 625 | 625 |

## Aggregation 1: Top Triggered Fraud Rules (`$unwind` + `$group`)
| Rule Code | Trigger Count | Avg Weight |
| :--- | ---: | ---: |
| `BENEFICIARY_FAN_IN` | 562 | 40.0 |
| `GEO_MISMATCH` | 556 | 35.0 |
| `VEL_1H_SPIKE` | 555 | 30.0 |
| `NEW_DEVICE_LOGIN` | 518 | 25.0 |
| `NIGHT_HIGH_VALUE` | 517 | 20.0 |

## Aggregation 2: Suspected Mule Device Fingerprint Clusters (`risk_score >= 70`)
| Device Fingerprint | Blocked Events | Distinct Customers | Flagged Amount (NGN) |
| :--- | ---: | ---: | ---: |
| `dev_mule_03` | 117 | 10 | 30,420,000.00 |
| `dev_mule_01` | 116 | 10 | 30,160,000.00 |
| `dev_mule_05` | 114 | 10 | 29,640,000.00 |
| `dev_mule_04` | 111 | 10 | 28,860,000.00 |
| `dev_mule_02` | 107 | 10 | 27,820,000.00 |
