"""Deliberate defect: retries schedule another fulfillment."""

def handle(db, event):
    db.execute("INSERT INTO balances(entity, value) VALUES (?, 1) ON CONFLICT(entity) DO UPDATE SET value=value+1", (event["entity_id"],))
    db.commit()
    return {"accepted": True}
