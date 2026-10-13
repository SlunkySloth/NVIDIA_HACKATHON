"""Deliberate defect: arrival order overrides entity version."""

def handle(db, event):
    db.execute("INSERT INTO subscriptions(entity, status, version) VALUES (?, ?, ?) ON CONFLICT(entity) DO UPDATE SET status=excluded.status, version=excluded.version", (event["entity_id"], event["payload"]["status"], event["payload"]["version"]))
    db.commit()
    return {"accepted": True}
