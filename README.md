# Advanced Database Systems Portfolio — NovaPay Fintech Ltd

> **Course:** MIT 8103 Advanced Database Systems (2026/2027 First Semester CA)
> **Assessment:** Individual Practical Database Portfolio (40 Marks)
> **Case Study Domain:** Bank / Fintech Platform
> **Relational Stack:** PostgreSQL 17 (`novapay_core`)
> **NoSQL Stack:** MongoDB 9 (`novapay_telemetry`)

---

## 1. Selected Organisation / Case Study Statement

- **Organisation / Scenario:** **NovaPay Fintech Ltd** (Simulated Digital Banking & Instant Payment Platform)
- **Nature of Business / System:** A multi-account digital wallet and payment platform supporting customer onboarding (tiered KYC), peer-to-peer (P2P) instant transfers, deposits, withdrawals, failed transaction reversals, double-entry ledger reconciliation, and real-time compliance/fraud auditing.

### Database Users
- **Retail & Business Customers:** View balances, initiate P2P transfers, fund wallets, withdraw funds, and inspect receipts.
- **Operations & Settlement Officers:** Monitor failed settlements, execute authorised reversals, and reconcile daily ledger totals.
- **Compliance & Fraud Analysts:** Audit immutable journal entries, inspect high-risk transfer alerts, and correlate device/session telemetry.
- **Database Administrators & Platform Engineers:** Manage normalised schemas, tune query plans and indexes, enforce concurrency controls, and architect partitioning, replication, and cloud failover.

### Major Data Stored
- Customer profiles, authentication identities, and KYC verification tiers
- Typed financial accounts, current balances, currency codes, and lifecycle statuses
- Transfers, deposits, withdrawals, and reversal linkage references
- Immutable double-entry ledger postings (`DEBIT` / `CREDIT` journal lines)
- Idempotency keys and semi-structured fraud/audit event payloads (MongoDB)

### Key Operations Supported
- Onboard customers and provision typed financial accounts subject to KYC tier limits
- Execute atomic P2P fund transfers with double-entry ledger postings and idempotency protection
- Process deposits, withdrawals, and controlled reversals of failed transactions
- Generate paginated customer account statements and reconciliation summaries
- Audit flagged transactions and eliminate concurrent double-spend race conditions

---

## 2. Portfolio Structure & Deliverables

```text
advanced-database-portfolio/
├── portfolio-1-database-design/          # ER diagram, 3NF/BCNF schema, keys, constraints
├── portfolio-2-query-optimisation/       # Analytical SQL, EXPLAIN (ANALYZE, BUFFERS), indexing
├── portfolio-3-transactions-concurrency/ # COMMIT/ROLLBACK, isolation, locking, concurrency tests
├── portfolio-4-nosql/                    # MongoDB JSON Schema model, indexes, aggregations
├── portfolio-5-distributed-cloud/        # Partitioning, replication, sharding, CAP/cloud architecture
├── core/                                 # Reusable, domain-agnostic DB runners & scaffolder
├── docs/                                 # Setup runbook, reusability guide, LMS blueprint, AI log
├── templates/                            # Blank manifest template for cloning to new domains
├── tests/                                # Automated unit tests for core tooling
├── case_study.json                       # Single source of truth for case study metadata
└── README.md
```

---

## 3. Documentation Index

- **[Setup, Isolated GitHub & Operations Runbook](docs/SETUP_AND_RUNBOOK.md)** — Local software install, isolated secondary GitHub setup, DB init, and progressive run workflow.
- **[Reusability & Multi-Case-Study Guide](docs/REUSABILITY_GUIDE.md)** — How to clone and adapt this production architecture for any other case study.
- **[LMS Final Documentation Blueprint](docs/LMS_SUBMISSION_GUIDE.md)** — Structure and 11-point pre-submission checklist for the 2–3 page LMS report.
- **[Academic Integrity & AI Use Declaration](docs/AI_USE_DECLARATION.md)** — Audit log of AI assistance, human review, and verification steps.

---

## 4. Portfolio Progress Tracker

- [x] Foundation, reusable `core/` framework, documentation, and local toolchain
- [x] Portfolio 1: Database Design and Modelling
- [x] Portfolio 2: Query Processing and Optimisation
- [x] Portfolio 3: Transactions and Concurrency
- [x] Portfolio 4: NoSQL and Advanced Data Models
- [x] Portfolio 5: Distributed and Cloud Database Exercise
- [ ] Final Documentation & LMS Submission
