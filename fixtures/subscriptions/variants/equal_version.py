"""Deliberate defect: equal versions can replace already-applied entity state."""
def handle(db, event):
    row = db.execute("SELECT version FROM subscriptions WHERE entity=?", (event["entity_id"],)).fetchone()
    if row is None or event["payload"]["version"] >= row[0]:
        db.execute("REPLACE INTO subscriptions VALUES (?, ?, ?)", (event["entity_id"], event["payload"]["status"], event["payload"]["version"]))
    return {"accepted": True}
