# Advanced Database Systems Portfolio — NovaPay Fintech Ltd

> **Course:** MIT 8103 Advanced Database Systems (2026/2027 First Semester CA)
> **Assessment:** Individual Practical Database Portfolio (40 Marks)
> **Student Name:** Kolawole Damilola Ayodeji
> **Matriculation Number:** `301906206`
> **Repository:** `https://github.com/Klassique1/Kolawole_Damilola_301906206`
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
├── core/                                 # Shared DB runners, CLI & project utilities
├── docs/                                 # Setup runbook, modular architecture guide, LMS blueprint, AI log
├── templates/                            # Schema manifest template for case_study.json
├── tests/                                # Automated unit tests for core tooling
├── case_study.json                       # Single source of truth for case study metadata
└── README.md
```

---

## 3. Documentation Index

- **[Final LMS Portfolio Report (Markdown)](docs/LMS_FINAL_REPORT_DRAFT.md)** & **[Submission PDF](docs/Kolawole_Damilola_Ayodeji_301906206_MIT8103_Portfolio.pdf)** — Complete 3-page summary across Portfolios 1–5, ER diagram, evidence outputs, reflection, references, and AI declaration.
- **[Setup, GitHub & Operations Runbook](docs/SETUP_AND_RUNBOOK.md)** — Local database stack installation, GitHub SSH/HTTPS configuration, database initialisation, and progressive run workflow.
- **[Modular Architecture & Extensibility Guide](docs/REUSABILITY_GUIDE.md)** — How shared database tooling in `core/` separates engine execution from case-study configuration in `case_study.json`.
- **[LMS Final Documentation Blueprint](docs/LMS_SUBMISSION_GUIDE.md)** — Structure and pre-submission checklist for the LMS report.
- **[Academic Integrity & AI Use Declaration](docs/AI_USE_DECLARATION.md)** — Audit log of AI assistance, human review, and verification steps.

---

## 4. Portfolio Progress Tracker

- [x] Foundation, reusable `core/` framework, documentation, and local toolchain
- [x] Portfolio 1: Database Design and Modelling
- [x] Portfolio 2: Query Processing and Optimisation
- [x] Portfolio 3: Transactions and Concurrency
- [x] Portfolio 4: NoSQL and Advanced Data Models
- [x] Portfolio 5: Distributed and Cloud Database Exercise
- [x] Final Documentation & LMS Submission (PDF Exported & Ready)
