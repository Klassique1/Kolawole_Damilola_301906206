"""Portfolio 2 runner: seeds analytical volume and compares baseline vs. indexed plans."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure sibling queries.py resolves cleanly regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.benchmark_runner import export_benchmark_comparison, run_query_benchmark
from core.config import load_config
from core.postgres_client import PostgresClient
from queries import build_benchmark_queries


def _run_sql_file(client: PostgresClient, sql_path: Path, *, autocommit: bool = False) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    with client.connect(autocommit=autocommit) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        if not autocommit:
            conn.commit()


def _export_index_and_sample_evidence(
    client: PostgresClient,
    queries: list[tuple[str, str]],
    evidence_dir: Path,
) -> None:
    lines = ["# Portfolio 2: Index Footprint & Sample Query Outputs", ""]

    with client.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    schemaname,
                    relname AS table_name,
                    n_live_tup AS live_rows,
                    pg_size_pretty(pg_relation_size(relid)) AS heap_size,
                    pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
                    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
                FROM pg_stat_user_tables
                WHERE schemaname = 'core'
                ORDER BY pg_total_relation_size(relid) DESC;
                """
            )
            table_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    t.relname AS table_name,
                    i.relname AS index_name,
                    pg_size_pretty(pg_relation_size(i.oid)) AS index_size,
                    ix.indisunique AS is_unique,
                    pg_get_expr(ix.indpred, ix.indrelid) AS partial_predicate
                FROM pg_class t
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_index ix ON ix.indrelid = t.oid
                JOIN pg_class i ON i.oid = ix.indexrelid
                WHERE n.nspname = 'core'
                  AND i.relname LIKE 'idx_%'
                ORDER BY pg_relation_size(i.oid) DESC;
                """
            )
            idx_rows = cur.fetchall()

            lines.append("## Table & Storage Overview")
            lines.append("| Table | Live Rows | Heap Size | Indexes Size | Total Size |")
            lines.append("| :--- | ---: | ---: | ---: | ---: |")
            for r in table_rows:
                lines.append(f"| `{r[0]}.{r[1]}` | {r[2]:,} | {r[3]} | {r[4]} | {r[5]} |")

            lines.append("\n## Portfolio 2 Optimisation Indexes")
            lines.append("| Table | Index Name | Size | Unique | Partial Predicate |")
            lines.append("| :--- | :--- | ---: | :---: | :--- |")
            for r in idx_rows:
                pred = f"`{r[4]}`" if r[4] else "*(full table)*"
                lines.append(f"| `{r[0]}` | `{r[1]}` | {r[2]} | {r[3]} | {pred} |")

            lines.append("\n## Sample Query Result Rows")
            for qname, qsql in queries:
                cur.execute(qsql.strip().rstrip(";"))
                cols = [d.name for d in (cur.description or [])]
                rows = cur.fetchmany(5)
                lines.append(f"\n### {qname}")
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for row in rows:
                    lines.append("| " + " | ".join(str(v) for v in row) + " |")

    (evidence_dir / "index_and_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    portfolio_dir = Path(__file__).resolve().parent
    sql_dir = portfolio_dir / "sql"
    evidence_dir = portfolio_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    client = PostgresClient(cfg)

    print("1/6 Seeding analytical volume (100k transactions / ~196k ledger entries)...")
    _run_sql_file(client, sql_dir / "001_seed_analytical_volume.sql")

    print("2/6 Dropping optimisation indexes for clean baseline...")
    _run_sql_file(client, sql_dir / "002_drop_optimisation_indexes.sql")

    with client.connect(autocommit=True) as conn:
        conn.execute("VACUUM ANALYZE core.customers, core.accounts, core.transactions, core.ledger_entries;")
        sample_acct = conn.execute(
            "SELECT account_id::text FROM core.accounts WHERE account_number = '4000000420'"
        ).fetchone()[0]

    queries = build_benchmark_queries(sample_acct)

    print("3/6 Running baseline EXPLAIN (ANALYZE, BUFFERS)...")
    baseline = run_query_benchmark(client, queries, phase="baseline", warmup_runs=1)

    print("4/6 Creating composite, partial, covering, functional & FK indexes...")
    _run_sql_file(client, sql_dir / "003_optimisation_indexes.sql")

    with client.connect(autocommit=True) as conn:
        conn.execute("VACUUM ANALYZE core.customers, core.accounts, core.transactions, core.ledger_entries;")

    print("5/6 Running optimised EXPLAIN (ANALYZE, BUFFERS)...")
    optimised = run_query_benchmark(client, queries, phase="optimised", warmup_runs=1)

    print("6/6 Exporting comparison tables, index footprints, and sample outputs...")
    json_path, md_path = export_benchmark_comparison(baseline, optimised, evidence_dir)
    _export_index_and_sample_evidence(client, queries, evidence_dir)

    print(f"Benchmark JSON : {json_path}")
    print(f"Benchmark MD   : {md_path}")


if __name__ == "__main__":
    main()
