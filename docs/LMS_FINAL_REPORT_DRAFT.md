# MIT 8103 Advanced Database Systems — Final Portfolio Documentation (LMS Submission)

> **Instructions:** Review every section personally, verify your name/matriculation number formatting and screenshots, export to **PDF (2–3 pages)**, and confirm the private GitHub repository (`https://github.com/Klassique1/Kolawole_Damilola_301906206`) is shared with your assessor **before** submitting on the LMS.

---

## 1. Student & Repository Details
- **Course:** MIT 8103 Advanced Database Systems (2026/2027 First Semester Continuous Assessment)
- **Student Name:** Kolawole Damilola
- **Matriculation Number:** `301906206`
- **Private GitHub Repository:** `https://github.com/Klassique1/Kolawole_Damilola_301906206`
- **Selected Organisation / Case Study:** **NovaPay Fintech Ltd** (Simulated Digital Banking & Instant Payment Platform)

---

## 2. Case Study Statement
**NovaPay Fintech Ltd** is a digital wallet and instant payment platform supporting tiered KYC customer onboarding, multi-currency wallet accounts, peer-to-peer (P2P) transfers, external clearing deposits/withdrawals, authorised transaction reversals, immutable double-entry ledger reconciliation, and real-time fraud risk monitoring.
- **Database Users:** Retail/Business Customers, Operations & Settlement Officers, Compliance & Fraud Analysts, and Database Administrators.
- **Major Data Stored:** Customer profiles & KYC tiers (`novapay_core`), accounts & balances, transactions & reversal links, immutable ledger postings, and semi-structured fraud/device telemetry (`novapay_telemetry`).
- **Key Operations:** Atomic P2P transfers, reversals, paginated account statements, reconciliation reporting, concurrent double-spend prevention, and fraud rule evaluation.

---

## 3. Summary of Practical Portfolio Activities (1–5)

### Portfolio 1: Database Design and Modelling
Designed a normalised **3NF/BCNF** schema (`core` schema on PostgreSQL 17.11) separating reference data (`currencies`, `kyc_tiers`, `account_types`) from transactional entities (`customers`, `accounts`, `transactions`, `ledger_entries`, `audit_logs`). Enforced `NUMERIC(19, 4)` decimal precision, 104 engine constraints (`CHECK`, `UNIQUE`, `ON DELETE RESTRICT`), a self-referencing `UNIQUE (reversed_transaction_id)` reversal guard, and an append-only immutability trigger (`trg_ledger_immutable` raising `SQLSTATE 42501`). Closed-loop double-entry accounting against `EXTERNAL_CONTRA` passed verification with `0.0000` imbalance and `0.0000` balance variance across all accounts. *(Attach screenshot of `novapay_erd.mmd` rendered ER diagram and `portfolio_1_verification.md` output.)*

### Portfolio 2: Query Processing and Optimisation
Scaled the database to **100,005 transactions** and **190,210 ledger entries** and benchmarked four production queries using `EXPLAIN (ANALYZE, BUFFERS)`:
- **Q1 (Paginated Statement):** Covering composite index `idx_ledger_account_posted_desc` converted `Seq Scan + Sort` (`9.691 ms`, `2,928` buffers) into **`Index Only Scan`** (`0.038 ms`, `4` buffers — **255.03x faster**).
- **Q2 (High-Value Failed/Pending Filter):** Partial index `idx_txn_non_completed_recent` (`168 kB`) converted `Seq Scan` (`13.394 ms`, `2,509` buffers) into `Bitmap Heap/Index Scan` (`0.116 ms`, `21` buffers — **115.47x faster**).
- **Q3 (14-Day Reconciliation):** Covering index `idx_txn_status_created_cover` accelerated aggregation from `27.509 ms` (`2,509` buffers) to `2.825 ms` (`48` buffers — **9.74x faster**).
- **Q4 (Case-Insensitive KYC Lookup):** Functional index `lower(email)` + partial FK index on `accounts(customer_id)` reduced execution time from `0.824 ms` (`103` buffers) to `0.045 ms` (`8` buffers — **18.31x faster**).
*(Attach screenshot of `benchmark_comparison.md` / pgAdmin `EXPLAIN` output.)*

### Portfolio 3: Transactions and Concurrency
Built a barrier-synchronized multi-session test harness verifying atomicity, concurrency anomalies, and lock/isolation controls:
- **Atomicity (`COMMIT` & `ROLLBACK`):** Committed a `25,000 NGN` P2P transfer atomically and proved an invalid `999,999 NGN` overdraft hit `SQLSTATE 23514` (`accounts_check`), rolling back the preceding credit cleanly.
- **Lost Update Reproduction:** Two unlocked `READ COMMITTED` workers reading stale `50,000 NGN` simultaneously both committed `40,000 NGN` transfers (`variance = 40,000.0000`).
- **Pessimistic Locking (`SELECT ... FOR UPDATE`) & Ordered Deadlock Prevention:** Row locking serialized the race cleanly (`0.0000` variance); unordered bidirectional locking triggered `SQLSTATE 40P01` deadlock detection, while canonical `ORDER BY account_id ASC FOR UPDATE` eliminated deadlocks completely.
- **`SERIALIZABLE` (SSI) + Retry:** SSI caught the concurrent conflict (`SQLSTATE 40001`), rolled back one worker, and automatic retry rejected the second transfer cleanly (`0.0000` variance).

### Portfolio 4: NoSQL and Advanced Data Models
Implemented a polyglot document store (`novapay_telemetry.fraud_risk_events` on **MongoDB 9.0.4**) for polymorphic channel telemetry (`MOBILE_APP`, `WEB`, `USSD`, `API`) and variable-length `rule_hits[]` arrays. Enforced strict `$jsonSchema` validation (rejecting invalid `risk_score: 150` with MongoDB error code `121`), seeded **25,000 documents**, and built an ESR compound index `{ decision: 1, channel: 1, created_at: -1 }` plus a 90-day TTL index. Query execution improved from `SORT -> COLLSCAN` (`24 ms`, `25,000` docs examined) to `FETCH -> IXSCAN` (`8 ms`, `625` docs examined). Aggregation pipelines identified top fraud rules (`$unwind`) and multi-customer mule device clusters (`dev_mule_01..05`).

### Portfolio 5: Distributed and Cloud Database Exercise
Implemented **declarative monthly range partitioning** on `core.ledger_entries_partitioned`, confirming planner **partition pruning** (October 2026 query scanned only `ledger_entries_p_2026_10`, `497` heap buffers, `6.130 ms`, pruning all other 8 partitions). Provisioned and tested a live **PostgreSQL 17 physical streaming standby replica** (`5432 → 5433`), verifying `pg_stat_replication` (`state = streaming`, zero byte lag `0/2B0B0770`), `pg_is_in_recovery() = True`, real-time marker propagation (`repl-probe-cee426c704`), and read-only enforcement (`SQLSTATE 25006`). Documented multi-AZ cloud topology, `customer_id` hash sharding with 16-bucket clearing-pool striping, and CP vs. PA/EL CAP trade-offs.

---

## 4. Individual Technical Reflection
*(Personalize these points in your own words before submitting so you can explain every choice confidently during verification:)*
- **Design Choices:** Why strict double-entry (`EXTERNAL_CONTRA` + immutable `ledger_entries`) and exact `NUMERIC(19,4)` were prioritized over updating mutable balance columns alone; why MongoDB was paired only for telemetry/fraud rather than replacing ACID balances.
- **Challenges Faced & Lessons Learned:** Catching and fixing a modulo skew bug during 100k synthetic seeding via `CHECK (balance >= 0)` enforcement; resolving `psycopg` v3 connection isolation property behavior and thread-barrier deadlocks on `SERIALIZABLE` retries; verifying streaming replication LSN synchronization and partition pruning firsthand.

---

## 5. References & AI Use Declaration
- PostgreSQL Global Development Group. *PostgreSQL 17 Documentation*. https://www.postgresql.org/docs/17/
- MongoDB Inc. *MongoDB Manual*. https://www.mongodb.com/docs/manual/
- Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media.
- **AI Use Declaration:** See [AI_USE_DECLARATION.md](AI_USE_DECLARATION.md) *(summarize tool used, purpose—scaffolding, SQL/harness drafting, troubleshooting—and how you executed, inspected, and verified every script and output against live PostgreSQL 17 and MongoDB 9 instances).*
