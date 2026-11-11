# Portfolio 4: NoSQL and Advanced Data Models

> **Case Study:** NovaPay Fintech Ltd (`novapay_telemetry`)
> **Engine:** MongoDB 9.0.4 + `mongosh` 2.14.1
> **Data Model:** Schema-Validated Document Model (`fraud_risk_events`)

---

## 1. Why Polyglot Persistence? (PostgreSQL + MongoDB)

NovaPay pairs **PostgreSQL** (for strict ACID double-entry balances and relational customer/account entities) with **MongoDB** (for high-velocity, semi-structured fraud risk telemetry and device event streams):

| Concern | Relational Core (`novapay_core` in PostgreSQL) | Document Telemetry (`novapay_telemetry` in MongoDB) |
| :--- | :--- | :--- |
| **Workload Pattern** | Strict ACID P2P transfers, reversals, trial balances | High-throughput append-mostly event ingestion & ad-hoc rule analytics |
| **Schema Characteristics** | Fixed, normalised 3NF/BCNF financial columns | Polymorphic per-channel attributes (`os`/`app_version` on mobile vs. `cell_tower_id` on USSD) and variable-length `rule_hits[]` arrays |
| **Join / Read Pattern** | Multi-table foreign key integrity | Single-document atomic fetch containing event, device context, and triggered fraud rules without multi-table joins |
| **Retention & Lifecycle** | Permanent immutable audit ledger | Automated 90-day hot expiry via MongoDB **TTL Index** (`expireAfterSeconds: 7776000`) |

---

## 2. Document Model & `$jsonSchema` Validation

Defined in [schemas/fraud_event_schema.json](schemas/fraud_event_schema.json) and enforced at the database engine layer (`validationLevel: "strict"`, `validationAction: "error"`):

```json
{
  "event_id": "evt_00000040",
  "transaction_ref": "NP-BTXN-000040",
  "customer_id": "cust-0040",
  "channel": "MOBILE_APP",
  "amount_ngn": 260000.0,
  "risk_score": 85,
  "decision": "BLOCK",
  "device": {
    "fingerprint_hash": "dev_mule_01",
    "ip_country": "NG",
    "os": "Android 15",
    "app_version": "4.12.0"
  },
  "rule_hits": [
    { "rule_code": "VEL_1H_SPIKE", "weight": 30, "detail": "High transfer count within 60 minutes" },
    { "rule_code": "GEO_MISMATCH", "weight": 35, "detail": "IP country differs from KYC profile" }
  ],
  "created_at": "2026-11-11T16:40:00Z"
}
```

### Guardrail Verification
Attempting to insert a malformed document (`risk_score: 150`, invalid `transaction_ref`) was rejected by MongoDB (`code 121: Document failed validation`).

---

## 3. Indexing Strategy & Observed Performance

- **`uq_event_id`:** Unique index on `event_id` for idempotent telemetry ingestion.
- **`idx_decision_channel_created`:** Compound **ESR (Equality → Sort → Range)** index `{ decision: 1, channel: 1, created_at: -1 }` eliminating blocking in-memory sorts.
- **`idx_rule_hits_code`:** Multikey index on embedded array `rule_hits.rule_code`.
- **`idx_ttl_90d_created_at`:** TTL index (`expireAfterSeconds: 7776000`) automatically purging stale telemetry after 90 days.

| Query (`decision = 'BLOCK' AND channel = 'MOBILE_APP' ORDER BY created_at DESC`) | Winning Plan | Exec Time (ms) | Docs Examined | Returned |
| :--- | :--- | ---: | ---: | ---: |
| Baseline (No Index) | `SORT -> COLLSCAN` | 24 | 25,000 | 625 |
| Optimised (ESR Compound Index) | `FETCH -> IXSCAN (idx_decision_channel_created)` | **8** | **625** | 625 |

---

## 4. Aggregation Pipelines & Verification Evidence

- Python automation runner: [scripts/run_portfolio_4.py](scripts/run_portfolio_4.py)
- Native `mongosh` script: [scripts/mongosh_verify.js](scripts/mongosh_verify.js)
- Captured evidence: [evidence/portfolio_4_nosql_report.md](evidence/portfolio_4_nosql_report.md), [evidence/portfolio_4_nosql_report.json](evidence/portfolio_4_nosql_report.json), and [evidence/mongosh_output.txt](evidence/mongosh_output.txt)

### How to Reproduce
```powershell
python portfolio-4-nosql/scripts/run_portfolio_4.py
mongosh "mongodb://localhost:27017/novapay_telemetry" --quiet --norc --file portfolio-4-nosql/scripts/mongosh_verify.js
```
