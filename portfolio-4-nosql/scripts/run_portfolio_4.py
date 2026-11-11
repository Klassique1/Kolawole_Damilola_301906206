"""Portfolio 4 runner: MongoDB JSON Schema validation, indexing, aggregations & evidence export."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import WriteError

from core.config import load_config
from core.mongo_client import MongoPortfolioClient


def _build_telemetry_batch(count: int = 25000) -> list[dict]:
    """Generate deterministic polymorphic fraud telemetry documents across 4 payment channels."""
    rng = random.Random(8103)
    base_time = datetime.now(timezone.utc)
    channels = ["MOBILE_APP", "WEB", "USSD", "API"]
    rules_pool = [
        ("VEL_1H_SPIKE", 30, "High transfer count within 60 minutes"),
        ("NEW_DEVICE_LOGIN", 25, "Unrecognized hardware fingerprint"),
        ("GEO_MISMATCH", 35, "IP country differs from KYC profile"),
        ("NIGHT_HIGH_VALUE", 20, "High-value transfer between 00:00-04:00 WAT"),
        ("BENEFICIARY_FAN_IN", 40, "Multiple senders targeting single wallet"),
    ]

    docs: list[dict] = []
    # Shared mule device hashes so aggregation pipeline detects suspicious multi-customer clusters
    suspicious_devices = [f"dev_mule_{i:02d}" for i in range(1, 6)]

    for i in range(1, count + 1):
        channel = channels[i % len(channels)]
        cust_idx = ((i - 1) % 2000) + 1
        customer_id = f"cust-{cust_idx:04d}"
        is_high_risk = (i % 40 == 0)
        is_challenge = (i % 15 == 0) and not is_high_risk

        if is_high_risk:
            picked = rng.sample(rules_pool, k=2)
            risk_score = min(100, sum(r[1] for r in picked) + rng.randint(15, 30))
            decision = "BLOCK"
            fp = suspicious_devices[(i // 40) % len(suspicious_devices)]
            ip_country = "GH" if i % 2 == 0 else "US"
        elif is_challenge:
            picked = [rng.choice(rules_pool)]
            risk_score = picked[0][1] + rng.randint(15, 25)
            decision = "CHALLENGE"
            fp = f"dev_{cust_idx:04d}_primary"
            ip_country = "NG"
        else:
            picked = []
            risk_score = rng.randint(1, 24)
            decision = "ALLOW"
            fp = f"dev_{cust_idx:04d}_primary"
            ip_country = "NG"

        # Polymorphic device attributes depending on channel
        device: dict[str, str] = {
            "fingerprint_hash": fp,
            "ip_country": ip_country,
        }
        if channel == "MOBILE_APP":
            device["os"] = "Android 15" if i % 2 == 0 else "iOS 19"
            device["app_version"] = "4.12.0"
        elif channel == "USSD":
            device["cell_tower_id"] = f"NG-LAG-{1000 + (i % 250)}"
        elif channel == "WEB":
            device["os"] = "Windows 11"

        docs.append(
            {
                "event_id": f"evt_{i:08d}",
                "transaction_ref": f"NP-BTXN-{((i - 1) % 98000) + 1:06d}",
                "customer_id": customer_id,
                "channel": channel,
                "amount_ngn": float(260000 + (i % 10) * 15000 if is_high_risk else 1500 + (i % 40) * 500),
                "risk_score": risk_score,
                "decision": decision,
                "device": device,
                "rule_hits": [
                    {"rule_code": code, "weight": weight, "detail": detail}
                    for code, weight, detail in picked
                ],
                "created_at": base_time - timedelta(minutes=(count - i) % (60 * 24 * 30)),
            }
        )
    return docs


def _extract_explain_summary(explain_doc: dict) -> dict:
    stats = explain_doc.get("executionStats", {})
    plan = explain_doc.get("queryPlanner", {}).get("winningPlan", {})
    stage = plan.get("stage", "UNKNOWN")
    input_stage = plan.get("inputStage", {})
    if input_stage:
        stage = f"{stage} -> {input_stage.get('stage', '')}"
        if "indexName" in input_stage:
            stage += f" ({input_stage['indexName']})"
    return {
        "winning_plan": stage,
        "execution_time_ms": stats.get("executionTimeMillis", 0),
        "docs_examined": stats.get("totalDocsExamined", 0),
        "keys_examined": stats.get("totalKeysExamined", 0),
        "n_returned": stats.get("nReturned", 0),
    }


def main() -> None:
    portfolio_dir = Path(__file__).resolve().parent.parent
    schema_path = portfolio_dir / "schemas" / "fraud_event_schema.json"
    evidence_dir = portfolio_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    mongo = MongoPortfolioClient(cfg)
    try:
        db = mongo.database()
        collection_name = "fraud_risk_events"

        print("1/6 Creating schema-validated collection fraud_risk_events...")
        db[collection_name].drop()
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        mongo.ensure_validated_collection(collection_name, schema)

        print("2/6 Testing JSON Schema validation rejection on invalid document...")
        validation_test = "FAILED"
        try:
            db[collection_name].insert_one(
                {
                    "event_id": "evt_invalid_01",
                    "transaction_ref": "INVALID_PREFIX",
                    "customer_id": "cust-0001",
                    "channel": "MOBILE_APP",
                    "amount_ngn": 5000,
                    "risk_score": 150,  # Exceeds maximum 100
                    "decision": "BLOCK",
                    "device": {"fingerprint_hash": "x", "ip_country": "NG"},
                    "rule_hits": [],
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except WriteError as exc:
            validation_test = f"PASS (MongoDB rejected invalid doc with code {exc.code}: {exc.details.get('errmsg')})"

        print("3/6 Seeding 25,000 polymorphic telemetry documents...")
        docs = _build_telemetry_batch(25000)
        for start in range(0, len(docs), 5000):
            db[collection_name].insert_many(docs[start : start + 5000], ordered=False)

        target_filter = {"decision": "BLOCK", "channel": "MOBILE_APP"}
        target_sort = [("created_at", DESCENDING)]

        print("4/6 Capturing COLLSCAN baseline explain(executionStats)...")
        baseline_explain = _extract_explain_summary(
            mongo.explain_find(collection_name, target_filter, sort_spec=target_sort)
        )

        print("5/6 Building ESR compound, multikey, unique & TTL indexes...")
        db[collection_name].create_index([("event_id", ASCENDING)], unique=True, name="uq_event_id")
        db[collection_name].create_index(
            [("decision", ASCENDING), ("channel", ASCENDING), ("created_at", DESCENDING)],
            name="idx_decision_channel_created",
        )
        db[collection_name].create_index([("rule_hits.rule_code", ASCENDING)], name="idx_rule_hits_code")
        db[collection_name].create_index(
            [("created_at", ASCENDING)],
            expireAfterSeconds=7776000,  # 90-day automated telemetry retention
            name="idx_ttl_90d_created_at",
        )

        optimised_explain = _extract_explain_summary(
            mongo.explain_find(collection_name, target_filter, sort_spec=target_sort)
        )

        print("6/6 Running aggregation pipelines and exporting evidence...")
        channel_summary = list(
            db[collection_name].aggregate(
                [
                    {
                        "$group": {
                            "_id": {"channel": "$channel", "decision": "$decision"},
                            "events": {"$sum": 1},
                            "avg_risk_score": {"$avg": "$risk_score"},
                            "total_amount_ngn": {"$sum": "$amount_ngn"},
                        }
                    },
                    {"$sort": {"_id.channel": 1, "events": -1}},
                ]
            )
        )

        top_rules = list(
            db[collection_name].aggregate(
                [
                    {"$unwind": "$rule_hits"},
                    {
                        "$group": {
                            "_id": "$rule_hits.rule_code",
                            "trigger_count": {"$sum": 1},
                            "avg_weight": {"$avg": "$rule_hits.weight"},
                        }
                    },
                    {"$sort": {"trigger_count": -1}},
                ]
            )
        )

        mule_clusters = list(
            db[collection_name].aggregate(
                [
                    {"$match": {"risk_score": {"$gte": 70}}},
                    {
                        "$group": {
                            "_id": "$device.fingerprint_hash",
                            "blocked_events": {"$sum": 1},
                            "distinct_customers": {"$addToSet": "$customer_id"},
                            "total_flagged_ngn": {"$sum": "$amount_ngn"},
                        }
                    },
                    {
                        "$project": {
                            "_id": 1,
                            "blocked_events": 1,
                            "distinct_customer_count": {"$size": "$distinct_customers"},
                            "total_flagged_ngn": 1,
                        }
                    },
                    {"$match": {"distinct_customer_count": {"$gte": 2}}},
                    {"$sort": {"blocked_events": -1}},
                ]
            )
        )

        report = {
            "collection": collection_name,
            "total_documents": db[collection_name].count_documents({}),
            "schema_validation_test": validation_test,
            "explain_before_index": baseline_explain,
            "explain_after_index": optimised_explain,
            "aggregations": {
                "channel_risk_summary": channel_summary,
                "top_triggered_rules": top_rules,
                "suspected_mule_device_clusters": mule_clusters,
            },
        }
        (evidence_dir / "portfolio_4_nosql_report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )

        md_lines = [
            "# Portfolio 4: MongoDB Verification & Benchmark Evidence",
            "",
            f"- **Database / Collection:** `{cfg.nosql_db_name}.{collection_name}`",
            f"- **Total Documents:** `{report['total_documents']:,}`",
            f"- **JSON Schema Validation Guardrail:** `{validation_test}`",
            "",
            "## Index Performance (`decision = 'BLOCK' AND channel = 'MOBILE_APP' ORDER BY created_at DESC`)",
            "| Phase | Winning Plan | Exec Time (ms) | Docs Examined | Keys Examined | Returned |",
            "| :--- | :--- | ---: | ---: | ---: | ---: |",
            f"| Baseline (No Index) | `{baseline_explain['winning_plan']}` | {baseline_explain['execution_time_ms']} | {baseline_explain['docs_examined']:,} | {baseline_explain['keys_examined']:,} | {baseline_explain['n_returned']:,} |",
            f"| Optimised (ESR Compound) | `{optimised_explain['winning_plan']}` | {optimised_explain['execution_time_ms']} | {optimised_explain['docs_examined']:,} | {optimised_explain['keys_examined']:,} | {optimised_explain['n_returned']:,} |",
            "",
            "## Aggregation 1: Top Triggered Fraud Rules (`$unwind` + `$group`)",
            "| Rule Code | Trigger Count | Avg Weight |",
            "| :--- | ---: | ---: |",
        ]
        for row in top_rules:
            md_lines.append(f"| `{row['_id']}` | {row['trigger_count']:,} | {row['avg_weight']:.1f} |")

        md_lines.extend(
            [
                "",
                "## Aggregation 2: Suspected Mule Device Fingerprint Clusters (`risk_score >= 70`)",
                "| Device Fingerprint | Blocked Events | Distinct Customers | Flagged Amount (NGN) |",
                "| :--- | ---: | ---: | ---: |",
            ]
        )
        for row in mule_clusters:
            md_lines.append(
                f"| `{row['_id']}` | {row['blocked_events']:,} | {row['distinct_customer_count']:,} | {row['total_flagged_ngn']:,.2f} |"
            )

        (evidence_dir / "portfolio_4_nosql_report.md").write_text(
            "\n".join(md_lines) + "\n", encoding="utf-8"
        )
        print(f"Portfolio 4 evidence exported to {evidence_dir}")
    finally:
        mongo.close()


if __name__ == "__main__":
    main()
