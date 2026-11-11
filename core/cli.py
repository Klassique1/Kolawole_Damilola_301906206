"""Unified CLI entrypoint for inspecting environment readiness and initializing DBs."""

from __future__ import annotations

import argparse
import sys

from core.config import load_config
from core.mongo_client import MongoPortfolioClient
from core.postgres_client import PostgresClient


def cmd_doctor() -> int:
    """Verify configuration, PostgreSQL connectivity, and MongoDB connectivity."""
    cfg = load_config()
    print(f"Case Study : {cfg.org_name} ({cfg.org_short_code})")
    print(f"Target PG  : {cfg.postgres.host}:{cfg.postgres.port}/{cfg.postgres.database}")
    print(f"Target Mongo: {cfg.mongo.uri}/{cfg.mongo.database}")

    ok = True
    pg = PostgresClient(cfg)
    try:
        with pg.connect(database="postgres", use_admin=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ver = cur.fetchone()[0]
        print(f"[OK] PostgreSQL reachable: {ver}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] PostgreSQL connection failed: {exc}")
        ok = False

    mongo = MongoPortfolioClient(cfg)
    try:
        db = mongo.database()
        info = db.command("ping")
        print(f"[OK] MongoDB reachable: ping={info.get('ok')}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] MongoDB connection failed: {exc}")
        ok = False
    finally:
        mongo.close()

    return 0 if ok else 1


def cmd_init_db() -> int:
    """Ensure the target PostgreSQL database exists."""
    cfg = load_config()
    pg = PostgresClient(cfg)
    pg.ensure_database()
    print(f"[OK] PostgreSQL database ready: {cfg.postgres.database}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MIT 8103 Portfolio Operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check case study config and database connectivity.")
    sub.add_parser("init-db", help="Create the configured PostgreSQL database if missing.")

    args = parser.parse_args()
    if args.command == "doctor":
        return cmd_doctor()
    if args.command == "init-db":
        return cmd_init_db()
    return 2


if __name__ == "__main__":
    sys.exit(main())
