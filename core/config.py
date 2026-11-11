"""Configuration loader for environment variables and case study manifests."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from dotenv import load_dotenv
except ImportError:  # Allow running config checks before dependencies are installed
    load_dotenv = None


@dataclass(frozen=True)
class PostgresSettings:
    """PostgreSQL connection settings loaded from environment variables."""

    host: str
    port: int
    database: str
    user: str
    password: str
    admin_user: str
    admin_password: str

    def dsn(
        self,
        database_override: str | None = None,
        use_admin: bool = False,
        port_override: int | None = None,
    ) -> str:
        """Build a libpq connection URI with URL-encoded credentials."""
        db = database_override or self.database
        usr = quote(self.admin_user if use_admin else self.user, safe="")
        pwd = quote(self.admin_password if use_admin else self.password, safe="")
        port = port_override if port_override is not None else self.port
        return f"postgresql://{usr}:{pwd}@{self.host}:{port}/{db}"


@dataclass(frozen=True)
class MongoSettings:
    """MongoDB connection settings loaded from environment variables."""

    uri: str
    database: str


@dataclass(frozen=True)
class PortfolioConfig:
    """Resolved project configuration combining environment and case study metadata."""

    root_dir: Path
    postgres: PostgresSettings
    mongo: MongoSettings
    case_study: dict[str, Any]

    @property
    def org_name(self) -> str:
        return str(self.case_study["organisation"]["name"])

    @property
    def org_short_code(self) -> str:
        return str(self.case_study["organisation"]["short_code"])

    @property
    def relational_db_name(self) -> str:
        return str(self.case_study["databases"]["relational"]["database_name"])

    @property
    def relational_schema(self) -> str:
        return str(self.case_study["databases"]["relational"]["schema_name"])

    @property
    def nosql_db_name(self) -> str:
        return str(self.case_study["databases"]["nosql"]["database_name"])


def _fallback_load_env(env_path: Path) -> None:
    """Minimal .env parser used only when python-dotenv is unavailable."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(root_dir: Path | None = None) -> PortfolioConfig:
    """Load .env and case_study.json from the repository root."""
    resolved_root = (root_dir or Path(__file__).resolve().parent.parent).resolve()
    env_file = resolved_root / ".env"

    if load_dotenv is not None and env_file.is_file():
        load_dotenv(env_file, override=False)
    else:
        _fallback_load_env(env_file)

    case_study_file = resolved_root / os.getenv("CASE_STUDY_FILE", "case_study.json")
    if not case_study_file.is_file():
        raise FileNotFoundError(f"Case study manifest not found: {case_study_file}")

    case_study = json.loads(case_study_file.read_text(encoding="utf-8"))
    default_pg_db = str(case_study["databases"]["relational"]["database_name"])
    default_mongo_db = str(case_study["databases"]["nosql"]["database_name"])

    pg = PostgresSettings(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        database=os.getenv("PGDATABASE", default_pg_db),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        admin_user=os.getenv("PGADMIN_USER", "postgres"),
        admin_password=os.getenv("PGADMIN_PASSWORD", os.getenv("PGPASSWORD", "")),
    )

    mongo = MongoSettings(
        uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        database=os.getenv("MONGO_DATABASE", default_mongo_db),
    )

    return PortfolioConfig(
        root_dir=resolved_root,
        postgres=pg,
        mongo=mongo,
        case_study=case_study,
    )
