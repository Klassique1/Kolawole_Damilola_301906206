"""Unit tests for the reusable core portfolio framework."""

from __future__ import annotations

import json
from pathlib import Path

from core.benchmark_runner import _parse_text_plan_metrics
from core.config import PostgresSettings, load_config
from core.scaffold import scaffold_portfolio


def test_load_config_reads_case_study_and_defaults(tmp_path: Path) -> None:
    manifest = {
        "organisation": {"name": "Test Org", "short_code": "testorg"},
        "database_users": [{"role": "User", "purpose": "Access"}],
        "major_data_stored": ["Entities"],
        "key_operations": ["Read/Write"],
        "databases": {
            "relational": {"engine": "PostgreSQL 17", "database_name": "test_rel", "schema_name": "core"},
            "nosql": {"engine": "MongoDB 9", "database_name": "test_nosql", "model_type": "Document"},
        },
    }
    (tmp_path / "case_study.json").write_text(json.dumps(manifest), encoding="utf-8")

    cfg = load_config(tmp_path)
    assert cfg.org_name == "Test Org"
    assert cfg.relational_db_name == "test_rel"
    assert cfg.nosql_db_name == "test_nosql"


def test_scaffold_portfolio_creates_complete_structure(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    template_path = repo_root / "templates" / "case_study.template.json"
    target = tmp_path / "new-portfolio"

    out = scaffold_portfolio(target, template_path)
    assert (out / "README.md").is_file()
    assert (out / "core" / "postgres_client.py").is_file()
    assert (out / "portfolio-1-database-design" / "README.md").is_file()
    assert (out / "portfolio-2-query-optimisation" / "README.md").is_file()
    assert (out / "portfolio-3-transactions-concurrency" / "README.md").is_file()
    assert (out / "portfolio-4-nosql" / "README.md").is_file()
    assert (out / "portfolio-5-distributed-cloud" / "README.md").is_file()
    assert "PGDATABASE=example_core" in (out / ".env.example").read_text(encoding="utf-8")


def test_parse_text_plan_metrics_extracts_timings_buffers_and_scan() -> None:
    sample_plan = """Limit  (cost=0.42..3.01 rows=25 width=60) (actual time=0.015..0.043 rows=25 loops=1)
  Buffers: shared hit=5 read=2
  ->  Index Only Scan using idx_test on ledger_entries  (cost=0.42..10.05 rows=93 width=60) (actual time=0.014..0.036 rows=25 loops=1)
        Heap Fetches: 0
Planning Time: 0.133 ms
Execution Time: 0.066 ms"""
    planning, execution, hits, reads, scan_type, rows = _parse_text_plan_metrics(sample_plan)
    assert planning == 0.133
    assert execution == 0.066
    assert hits == 5
    assert reads == 2
    assert scan_type == "Index Only Scan"
    assert rows == 25


def test_postgres_dsn_encodes_credentials_and_supports_port_override() -> None:
    pg = PostgresSettings(
        host="localhost",
        port=5432,
        database="novapay_core",
        user="app@user",
        password="p@ss:w/rd#1?",
        admin_user="postgres",
        admin_password="adm!n:pw",
    )
    app_dsn = pg.dsn(port_override=5433)
    assert app_dsn == "postgresql://app%40user:p%40ss%3Aw%2Frd%231%3F@localhost:5433/novapay_core"
    assert pg.dsn(database_override="postgres", use_admin=True) == (
        "postgresql://postgres:adm%21n%3Apw@localhost:5432/postgres"
    )
