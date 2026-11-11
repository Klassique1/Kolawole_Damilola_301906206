# Modular Architecture & Extensibility Guide

This repository separates **shared database engineering tooling** (`core/`, `templates/`, `docs/`) from **case-study configuration and SQL/NoSQL implementations** (`case_study.json`, `portfolio-1..5/`).

---

## 1. Architecture Separation

| Layer | Location | Role | Responsibility |
| :--- | :--- | :--- | :--- |
| **Manifest** | `case_study.json` / `templates/case_study.template.json` | Configuration | Single source of truth for organisation metadata, users, data, operations, and DB names |
| **Core Engine** | `core/config.py`, `core/postgres_client.py`, `core/benchmark_runner.py`, `core/concurrency_runner.py`, `core/mongo_client.py` | Shared infrastructure | Connection handling, checksummed SQL migrations, `EXPLAIN (ANALYZE, BUFFERS)` comparison tables, barrier-synchronized concurrency stress tests, MongoDB schema validation & `executionStats` capture |
| **Workspace Scaffolder** | `core/scaffold.py` | Project setup | Generates a structured local workspace pre-populated from a manifest file |
| **Domain Modules** | `portfolio-1-.../` through `portfolio-5-.../` | NovaPay implementation | ER diagrams, DDL/DML SQL scripts, queries, transaction workflows, NoSQL schemas, and partitioning/cloud docs |

---

## 2. Extending to a New Case Study Manifest

1. **Copy the manifest schema:**
   ```powershell
   Copy-Item templates\case_study.template.json custom_case_study.json
   ```
2. **Edit `custom_case_study.json`** with the target organisation's metadata and database names.
3. **Initialise the local skeleton** if testing an alternate domain configuration:
   ```powershell
   python -m core.scaffold --target ..\custom-db-sandbox --case-study custom_case_study.json
   ```
4. **Configure local credentials & remote** following [SETUP_AND_RUNBOOK.md](SETUP_AND_RUNBOOK.md).
5. **Implement SQL & NoSQL artifacts** inside `portfolio-1..5/` using `core.postgres_client`, `core.benchmark_runner`, `core.concurrency_runner`, and `core.mongo_client` directly without duplicating runner or logging logic.

---

## 3. Reusing `core/` Modules in Any Domain

- **Migrations (`PostgresClient.apply_migrations`)**: Reads ordered `*.sql` files, records SHA-256 checksums in `public.schema_migrations`, and prevents silent drift.
- **Query Benchmarks (`run_query_benchmark` + `export_benchmark_comparison`)**: Pass any `list[tuple[str, str]]` of `(query_name, sql_text)` before and after applying your index migration; generates `benchmark_comparison.json` and `benchmark_comparison.md`.
- **Concurrency Testing (`run_concurrent_scenario`)**: Pass any two `WorkerAction` callables + an `InvariantCheck` callable. The barrier synchronizes concurrent transactions so race conditions (e.g., double-spend, inventory oversell, double-booked clinic slot) and row-lock/serializable fixes are tested deterministically.
- **NoSQL Validation (`MongoPortfolioClient.ensure_validated_collection`)**: Pass any MongoDB `$jsonSchema` definition to enforce strict document validation and capture `explain("executionStats")` metrics.
