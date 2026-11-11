// Portfolio 4 | Native mongosh inspection & aggregation verification script
// Usage: mongosh "mongodb://localhost:27017/novapay_telemetry" --file portfolio-4-nosql/scripts/mongosh_verify.js

print("=== Collection Stats ===");
printjson(db.fraud_risk_events.countDocuments());

print("=== Active Indexes ===");
printjson(db.fraud_risk_events.getIndexes());

print("=== Sample High-Risk Document ===");
printjson(db.fraud_risk_events.findOne({ decision: "BLOCK" }));

print("=== Channel Risk Summary Aggregation ===");
printjson(
  db.fraud_risk_events.aggregate([
    {
      $group: {
        _id: { channel: "$channel", decision: "$decision" },
        events: { $sum: 1 },
        avg_risk_score: { $avg: "$risk_score" },
        total_amount_ngn: { $sum: "$amount_ngn" }
      }
    },
    { $sort: { "_id.channel": 1, events: -1 } }
  ]).toArray()
);
