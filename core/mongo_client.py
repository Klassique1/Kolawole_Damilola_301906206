"""Reusable MongoDB schema validation, indexing, and aggregation runner."""

from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from core.config import PortfolioConfig


class MongoPortfolioClient:
    """Thin wrapper around PyMongo for schema-validated portfolio workflows."""

    def __init__(self, config: PortfolioConfig) -> None:
        self.config = config
        self._client: MongoClient[dict[str, Any]] | None = None

    def database(self) -> Database[dict[str, Any]]:
        """Return the configured MongoDB database handle."""
        if self._client is None:
            self._client = MongoClient(self.config.mongo.uri, serverSelectionTimeoutMS=5000)
        return self._client[self.config.mongo.database]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def ensure_validated_collection(
        self,
        collection_name: str,
        json_schema: dict[str, Any],
        *,
        validation_level: str = "strict",
        validation_action: str = "error",
    ) -> None:
        """Create or update a collection with enforced JSON Schema validation."""
        db = self.database()
        validator = {"$jsonSchema": json_schema}

        if collection_name in db.list_collection_names():
            db.command(
                "collMod",
                collection_name,
                validator=validator,
                validationLevel=validation_level,
                validationAction=validation_action,
            )
        else:
            db.create_collection(
                collection_name,
                validator=validator,
                validationLevel=validation_level,
                validationAction=validation_action,
            )

    def explain_find(
        self,
        collection_name: str,
        filter_doc: dict[str, Any],
        *,
        sort_spec: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any]:
        """Capture MongoDB executionStats for a find query."""
        db = self.database()
        cmd: dict[str, Any] = {
            "explain": {
                "find": collection_name,
                "filter": filter_doc,
            },
            "verbosity": "executionStats",
        }
        if sort_spec:
            cmd["explain"]["sort"] = dict(sort_spec)
        return db.command(cmd)
