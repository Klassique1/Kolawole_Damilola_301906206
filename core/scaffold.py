"""Reusable portfolio generator for cloning this framework to any case study."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

PORTFOLIO_FOLDERS = [
    ("portfolio-1-database-design", "Portfolio 1: Database Design and Modelling", ["diagrams", "sql", "evidence"]),
    ("portfolio-2-query-optimisation", "Portfolio 2: Query Processing and Optimisation", ["sql", "evidence"]),
    ("portfolio-3-transactions-concurrency", "Portfolio 3: Transactions and Concurrency", ["sql", "scenarios", "evidence"]),
    ("portfolio-4-nosql", "Portfolio 4: NoSQL and Advanced Data Models", ["schemas", "scripts", "evidence"]),
    ("portfolio-5-distributed-cloud", "Portfolio 5: Distributed and Cloud Database Exercise", ["sql", "configs", "evidence"]),
]


def _render_root_readme(manifest: dict[str, Any]) -> str:
    org = manifest["organisation"]
    users_md = "\n".join(
        f"- **{u['role']}**: {u['purpose']}" for u in manifest["database_users"]
    )
    data_md = "\n".join(f"- {item}" for item in manifest["major_data_stored"])
    ops_md = "\n".join(f"- {item}" for item in manifest["key_operations"])

    return f"""# Advanced Database Systems Portfolio — {org["name"]}

> **Course:** MIT 8103 Advanced Database Systems
> **Case Study Domain:** {org["domain_type"]}
> **Relational Engine:** {manifest["databases"]["relational"]["engine"]} (`{manifest["databases"]["relational"]["database_name"]}`)
> **NoSQL Engine:** {manifest["databases"]["nosql"]["engine"]} (`{manifest["databases"]["nosql"]["database_name"]}`)

## 1. Selected Organisation / Case Study Statement

- **Organisation / Scenario:** {org["name"]}
- **Nature of Business / System:** {org["nature_of_business"]}

### Database Users
{users_md}

### Major Data Stored
{data_md}

### Key Operations Supported
{ops_md}

## 2. Repository Structure

```text
advanced-database-portfolio/
├── portfolio-1-database-design/
├── portfolio-2-query-optimisation/
├── portfolio-3-transactions-concurrency/
├── portfolio-4-nosql/
├── portfolio-5-distributed-cloud/
├── core/
├── docs/
├── templates/
├── case_study.json
└── README.md
```

## 3. Setup & Quickstart

See [docs/SETUP_AND_RUNBOOK.md](docs/SETUP_AND_RUNBOOK.md) for local installation, isolated GitHub configuration, and execution steps.
"""


def scaffold_portfolio(target_dir: Path, case_study_path: Path) -> Path:
    """Create a fresh, parameterized portfolio repository for any case study JSON."""
    source_root = Path(__file__).resolve().parent.parent
    manifest = json.loads(case_study_path.read_text(encoding="utf-8"))

    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_file in (".gitignore", ".editorconfig", "pyproject.toml"):
        src = source_root / rel_file
        if src.is_file():
            shutil.copy2(src, target_dir / rel_file)

    env_example = source_root / ".env.example"
    if env_example.is_file():
        rel_db = manifest["databases"]["relational"]["database_name"]
        nosql_db = manifest["databases"]["nosql"]["database_name"]
        text = env_example.read_text(encoding="utf-8")
        text = text.replace("PGDATABASE=portfolio_db", f"PGDATABASE={rel_db}")
        text = text.replace("MONGO_DATABASE=portfolio_nosql", f"MONGO_DATABASE={nosql_db}")
        (target_dir / ".env.example").write_text(text, encoding="utf-8")

    (target_dir / "case_study.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    for folder_name in ("core", "templates"):
        src_dir = source_root / folder_name
        dst_dir = target_dir / folder_name
        if src_dir.is_dir():
            shutil.copytree(
                src_dir,
                dst_dir,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                dirs_exist_ok=True,
            )

    (target_dir / "docs").mkdir(exist_ok=True)
    for folder_name, title, subdirs in PORTFOLIO_FOLDERS:
        p_dir = target_dir / folder_name
        p_dir.mkdir(exist_ok=True)
        for sub in subdirs:
            (p_dir / sub).mkdir(exist_ok=True)
        readme = p_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {title}\n\nCase Study: **{manifest['organisation']['name']}**\n",
                encoding="utf-8",
            )

    (target_dir / "README.md").write_text(_render_root_readme(manifest), encoding="utf-8")
    return target_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new MIT 8103 portfolio repository.")
    parser.add_argument("--target", required=True, type=Path, help="Target repository directory.")
    parser.add_argument("--case-study", required=True, type=Path, help="Path to case_study JSON manifest.")
    args = parser.parse_args()
    out = scaffold_portfolio(args.target, args.case_study)
    print(f"Portfolio scaffold created at: {out}")


if __name__ == "__main__":
    main()
