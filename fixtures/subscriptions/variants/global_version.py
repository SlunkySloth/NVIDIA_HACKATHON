"""Deliberate defect: entity versions are incorrectly compared across customers."""
def handle(db, event):
    highest = db.execute("SELECT COALESCE(MAX(version), 0) FROM subscriptions").fetchone()[0]
    if event["payload"]["version"] > highest:
        db.execute("INSERT INTO subscriptions VALUES (?, ?, ?) ON CONFLICT(entity) DO UPDATE SET status=excluded.status, version=excluded.version", (event["entity_id"], event["payload"]["status"], event["payload"]["version"]))
    return {"accepted": True}
