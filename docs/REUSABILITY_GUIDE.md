# Reusability & Multi-Case-Study Guide

This repository separates **domain-agnostic database engineering tooling** (`core/`, `templates/`, `docs/`) from **case-study-specific implementations** (`case_study.json`, `portfolio-1..5/`). You can spin up a clean, production-standard portfolio for any organisation or domain (E-commerce, Hospital, University Portal, Logistics, etc.) in minutes.

---

## 1. Architecture Separation

| Layer | Location | Reusable? | Responsibility |
| :--- | :--- | :---: | :--- |
| **Manifest** | `case_study.json` / `templates/case_study.template.json` | Schema reused | Single source of truth for organisation metadata, users, data, operations, and DB names |
| **Core Engine** | `core/config.py`, `core/postgres_client.py`, `core/benchmark_runner.py`, `core/concurrency_runner.py`, `core/mongo_client.py` | 100% domain-agnostic | Connection handling, checksummed SQL migrations, `EXPLAIN (ANALYZE, BUFFERS)` comparison tables, barrier-synchronized concurrency stress tests, MongoDB schema validation & `executionStats` capture |
| **Scaffolder** | `core/scaffold.py` | 100% domain-agnostic | Generates a new standalone repository skeleton pre-populated from any case study JSON |
| **Domain Modules** | `portfolio-1-.../` through `portfolio-5-.../` | Domain-specific | Concrete ER diagrams, DDL/DML SQL scripts, queries, transaction workflows, NoSQL schemas, and partitioning/cloud docs |

---

## 2. How to Instantiate for a New Organisation / Case Study

1. **Copy the blank manifest template:**
   ```powershell
   Copy-Item templates\case_study.template.json my_hospital_case_study.json
   ```
2. **Edit `my_hospital_case_study.json`** with the new organisation's name, business context, users, major data, operations, and target PostgreSQL/MongoDB database names.
3. **Run the scaffolder** to generate a clean standalone repository:
   ```powershell
   python -m core.scaffold --target ..\hospital-database-portfolio --case-study my_hospital_case_study.json
   ```
4. **Configure environment & isolated GitHub remote** following [SETUP_AND_RUNBOOK.md](SETUP_AND_RUNBOOK.md).
5. **Author domain SQL & NoSQL artifacts** inside `portfolio-1..5/` while reusing `core.postgres_client`, `core.benchmark_runner`, `core.concurrency_runner`, and `core.mongo_client` directly without duplicating any runner, logging, or benchmarking logic.

---

## 3. Reusing `core/` Modules in Any Domain

- **Migrations (`PostgresClient.apply_migrations`)**: Reads ordered `*.sql` files, records SHA-256 checksums in `public.schema_migrations`, and prevents silent drift.
- **Query Benchmarks (`run_query_benchmark` + `export_benchmark_comparison`)**: Pass any `list[tuple[str, str]]` of `(query_name, sql_text)` before and after applying your index migration; generates `benchmark_comparison.json` and `benchmark_comparison.md`.
- **Concurrency Testing (`run_concurrent_scenario`)**: Pass any two `WorkerAction` callables + an `InvariantCheck` callable. The barrier synchronizes concurrent transactions so race conditions (e.g., double-spend, inventory oversell, double-booked clinic slot) and row-lock/serializable fixes are tested deterministically.
- **NoSQL Validation (`MongoPortfolioClient.ensure_validated_collection`)**: Pass any MongoDB `$jsonSchema` definition to enforce strict document validation and capture `explain("executionStats")` metrics.
