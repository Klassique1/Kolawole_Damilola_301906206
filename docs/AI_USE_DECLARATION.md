# Academic Integrity & AI Use Declaration

- **Student Name:** Kolawole Damilola Ayodeji
- **Matriculation Number:** `301906206`
- **Course:** MIT 8103 Advanced Database Systems (2026/2027 First Semester CA)
- **Repository:** `https://github.com/Klassique1/Kolawole_Damilola_301906206`

In accordance with **Section 11 (Academic Integrity and AI Use Declaration)** of the MIT 8103 assignment brief, this record declares all AI tools used, their scope, and how all outputs were reviewed, corrected, executed, and verified against live PostgreSQL 17.11 and MongoDB 9.0.4 engines.

| Stage / Portfolio | AI Tool Used | Purpose of Use | How Output Was Reviewed, Corrected, Tested & Verified |
| :--- | :--- | :--- | :--- |
| Foundation & Tooling | Antigravity AI Assistant | Reusable `core/` runner architecture, `.env.example`, lifecycle script, unit tests | Reviewed all Python/PowerShell modules, verified zero hardcoded secrets, executed `pytest` (`4 passed`), verified local DB isolation via `core.cli doctor`. |
| Portfolio 1: Database Design | Antigravity AI Assistant | SQL DDL design, Mermaid ERD, double-entry trigger/view drafts | Corrected single-sided float seed by introducing `EXTERNAL_CONTRA`; executed `run_portfolio_1.py` against live PostgreSQL 17.11 and verified `104` constraints, `0.0000` imbalance, and `SQLSTATE 42501`/`23514` guardrails. |
| Portfolio 2: Query Optimisation | Antigravity AI Assistant | 100k data generator and index benchmarking suite | Caught and fixed modulo seed skew (`s % 50` vs coprime `s % 53`) flagged by `accounts_check`; refactored `benchmark_runner.py` to capture metrics from one `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` pass; verified speedups across Q1–Q4. |
| Portfolio 3: Transactions & Concurrency | Antigravity AI Assistant | Multi-thread concurrency scenarios (`COMMIT`/`ROLLBACK`, Lost Update, Deadlock, `FOR UPDATE`, `SERIALIZABLE`) | Fixed `psycopg` v3 `isolation_level` assignment and barrier handling during `40001` retries; verified live PostgreSQL outputs for every anomaly and control mechanism. |
| Portfolio 4: NoSQL & Advanced Models | Antigravity AI Assistant | `$jsonSchema` validator, 25k telemetry generator, ESR/TTL indexes, aggregation pipelines | Fixed mule device distribution formula `(i // 40) % 5`; verified schema rejection (`code 121`), `24 ms → 8 ms` index gain (`25,000 → 625` docs scanned), and `mongosh` CLI queries against MongoDB 9.0.4. |
| Portfolio 5: Distributed & Cloud | Antigravity AI Assistant | Monthly range partitioning SQL, multi-AZ topology spec, streaming replica verifier | Provisioned live local standby (`5432 → 5433`) with `pg_basebackup`; verified partition pruning on `ledger_entries_p_2026_10`, `pg_stat_replication` (`streaming`), marker propagation, and read-only rejection (`SQLSTATE 25006`). |

## External References & Documentation
- PostgreSQL Global Development Group. *PostgreSQL 17 Documentation*. https://www.postgresql.org/docs/17/
- MongoDB Inc. *MongoDB Manual*. https://www.mongodb.com/docs/manual/
- Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media.
- Silberschatz, A., Korth, H. F., & Sudarshan, S. *Database System Concepts*. McGraw-Hill.
