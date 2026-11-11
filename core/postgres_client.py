"""Reusable PostgreSQL migration and script execution utilities."""

from __future__ import annotations

import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg import sql

from core.config import PortfolioConfig


@dataclass(frozen=True)
class MigrationRecord:
    """Metadata describing an applied SQL migration."""

    filename: str
    checksum: str


class PostgresClient:
    """Thin production-oriented wrapper around psycopg connections and migrations."""

    def __init__(self, config: PortfolioConfig) -> None:
        self.config = config

    @contextmanager
    def connect(
        self,
        *,
        database: str | None = None,
        use_admin: bool = False,
        autocommit: bool = False,
        isolation_level: psycopg.IsolationLevel | None = None,
    ) -> Iterator[psycopg.Connection]:
        """Open a scoped PostgreSQL connection with optional isolation level."""
        dsn = self.config.postgres.dsn(database_override=database, use_admin=use_admin)
        with psycopg.connect(
            dsn,
            autocommit=autocommit,
            connect_timeout=5,
        ) as conn:
            if isolation_level is not None:
                conn.isolation_level = isolation_level
            yield conn

    def ensure_database(self) -> None:
        """Create the target application database owned by the configured app user if missing."""
        target_db = self.config.postgres.database
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", target_db):
            raise ValueError(f"Unsafe PostgreSQL database identifier: {target_db!r}")
        app_user = self.config.postgres.user
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", app_user):
            raise ValueError(f"Unsafe PostgreSQL user identifier: {app_user!r}")

        with self.connect(database="postgres", use_admin=True, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (target_db,),
                )
                if cur.fetchone() is None:
                    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
                    if cur.fetchone() is not None:
                        cur.execute(
                            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                                sql.Identifier(target_db),
                                sql.Identifier(app_user),
                            )
                        )
                    else:
                        cur.execute(
                            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db))
                        )

    def _ensure_migrations_table(self, conn: psycopg.Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    filename    TEXT NOT NULL UNIQUE,
                    checksum    TEXT NOT NULL,
                    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()

    def apply_migrations(
        self,
        migrations_dir: Path,
        *,
        files: list[Path] | None = None,
    ) -> list[MigrationRecord]:
        """Apply numbered .sql files idempotently with SHA-256 checksum verification."""
        if files is not None:
            sql_files = list(files)
        else:
            if not migrations_dir.is_dir():
                raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")
            sql_files = sorted(migrations_dir.glob("*.sql"))
        applied_now: list[MigrationRecord] = []

        with self.connect() as conn:
            self._ensure_migrations_table(conn)

            with conn.cursor() as cur:
                cur.execute("SELECT filename, checksum FROM public.schema_migrations")
                existing = {row[0]: row[1] for row in cur.fetchall()}

            for file_path in sql_files:
                sql_text = file_path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()

                if file_path.name in existing:
                    if existing[file_path.name] != checksum:
                        raise RuntimeError(
                            f"Checksum mismatch for already-applied migration {file_path.name}. "
                            "Create a new forward migration instead of editing applied files."
                        )
                    continue

                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(sql_text)
                        cur.execute(
                            """
                            INSERT INTO public.schema_migrations (filename, checksum)
                            VALUES (%s, %s)
                            """,
                            (file_path.name, checksum),
                        )

                applied_now.append(MigrationRecord(filename=file_path.name, checksum=checksum))

        return applied_now
