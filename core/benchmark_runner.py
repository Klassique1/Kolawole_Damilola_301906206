"""Domain-agnostic PostgreSQL EXPLAIN (ANALYZE, BUFFERS) benchmark harness."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from core.postgres_client import PostgresClient


@dataclass(frozen=True)
class QueryBenchmarkResult:
    """Structured metrics extracted from PostgreSQL EXPLAIN (ANALYZE, BUFFERS) output."""

    name: str
    phase: str
    planning_time_ms: float
    execution_time_ms: float
    total_time_ms: float
    shared_hit_blocks: int
    shared_read_blocks: int
    top_node_type: str
    actual_rows: int
    plan_text: str


_PLANNING_RE = re.compile(r"^Planning Time:\s*([\d.]+)\s*ms", re.MULTILINE)
_EXECUTION_RE = re.compile(r"^Execution Time:\s*([\d.]+)\s*ms", re.MULTILINE)
_ROOT_NODE_RE = re.compile(r"^([A-Za-z ]+?)\s+\(cost=.*?\(actual time=[\d.]+\.\.[\d.]+\s+rows=(\d+)")
_SCAN_NODE_RE = re.compile(
    r"(?:^|\->\s*)(Parallel Seq Scan|Seq Scan|Index Only Scan|Index Scan|Bitmap Index Scan|Bitmap Heap Scan)\b"
)
_EXEC_BUFFERS_RE = re.compile(r"^\s+Buffers:\s*(.+)$", re.MULTILINE)


def _parse_text_plan_metrics(plan_text: str) -> tuple[float, float, int, int, str, int]:
    """Extract timings, primary scan node, rows, and buffers from one FORMAT TEXT plan."""
    plan_match = _PLANNING_RE.search(plan_text)
    exec_match = _EXECUTION_RE.search(plan_text)
    root_match = _ROOT_NODE_RE.search(plan_text)
    scan_matches = _SCAN_NODE_RE.findall(plan_text)
    buf_match = _EXEC_BUFFERS_RE.search(plan_text)

    planning_ms = float(plan_match.group(1)) if plan_match else 0.0
    execution_ms = float(exec_match.group(1)) if exec_match else 0.0
    if scan_matches:
        unique_scans = list(dict.fromkeys(scan_matches))
        top_node = " + ".join(unique_scans[:2])
    else:
        top_node = root_match.group(1).strip() if root_match else "Unknown"
    actual_rows = int(root_match.group(2)) if root_match else 0

    hits = 0
    reads = 0
    if buf_match:
        buf_line = buf_match.group(1)
        hit_m = re.search(r"shared hit=(\d+)", buf_line)
        read_m = re.search(r"read=(\d+)", buf_line)
        hits = int(hit_m.group(1)) if hit_m else 0
        reads = int(read_m.group(1)) if read_m else 0

    return planning_ms, execution_ms, hits, reads, top_node, actual_rows


def run_query_benchmark(
    client: PostgresClient,
    queries: list[tuple[str, str]],
    *,
    phase: str,
    warmup_runs: int = 1,
) -> list[QueryBenchmarkResult]:
    """Execute queries under EXPLAIN (ANALYZE, BUFFERS) and collect plan metrics."""
    results: list[QueryBenchmarkResult] = []

    with client.connect() as conn:
        for name, query_sql in queries:
            clean_sql = query_sql.strip().rstrip(";")

            for _ in range(warmup_runs):
                with conn.cursor() as cur:
                    cur.execute(clean_sql)
                    cur.fetchall()

            with conn.cursor() as cur:
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {clean_sql}")
                text_lines = [row[0] for row in cur.fetchall()]

            plan_text = "\n".join(text_lines)
            planning_ms, execution_ms, hits, reads, top_node, actual_rows = _parse_text_plan_metrics(
                plan_text
            )

            results.append(
                QueryBenchmarkResult(
                    name=name,
                    phase=phase,
                    planning_time_ms=round(planning_ms, 3),
                    execution_time_ms=round(execution_ms, 3),
                    total_time_ms=round(planning_ms + execution_ms, 3),
                    shared_hit_blocks=hits,
                    shared_read_blocks=reads,
                    top_node_type=top_node,
                    actual_rows=actual_rows,
                    plan_text=plan_text,
                )
            )

    return results


def export_benchmark_comparison(
    baseline: list[QueryBenchmarkResult],
    optimised: list[QueryBenchmarkResult],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write machine-readable JSON and human-readable Markdown benchmark reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    opt_by_name = {item.name: item for item in optimised}

    json_path = output_dir / "benchmark_comparison.json"
    md_path = output_dir / "benchmark_comparison.md"

    payload = {
        "baseline": [asdict(item) for item in baseline],
        "optimised": [asdict(item) for item in optimised],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Query Performance Comparison (Before vs. After Optimisation)",
        "",
        "| Query | Baseline Exec (ms) | Optimised Exec (ms) | Speedup | Baseline Scan | Optimised Scan | Buffers (Before Hit/Read -> After Hit/Read) |",
        "| :--- | ---: | ---: | ---: | :--- | :--- | :--- |",
    ]

    for base in baseline:
        opt = opt_by_name.get(base.name)
        if opt is None:
            continue
        speedup = (
            f"{base.execution_time_ms / opt.execution_time_ms:.2f}x"
            if opt.execution_time_ms > 0
            else "N/A"
        )
        lines.append(
            f"| {base.name} | {base.execution_time_ms:.3f} | {opt.execution_time_ms:.3f} | "
            f"{speedup} | {base.top_node_type} | {opt.top_node_type} | "
            f"{base.shared_hit_blocks}/{base.shared_read_blocks} -> "
            f"{opt.shared_hit_blocks}/{opt.shared_read_blocks} |"
        )

    lines.append("")
    lines.append("## Detailed Execution Plans")
    for base in baseline:
        opt = opt_by_name.get(base.name)
        lines.append(f"\n### {base.name}\n")
        lines.append("#### Baseline Plan\n```text\n" + base.plan_text + "\n```")
        if opt is not None:
            lines.append("#### Optimised Plan\n```text\n" + opt.plan_text + "\n```")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
