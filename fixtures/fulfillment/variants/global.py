"""Deliberate defect: the first fulfillment suppresses unrelated paid orders."""
def handle(db, event):
    if db.execute("SELECT COUNT(*) FROM processed").fetchone()[0] == 0:
        db.execute("INSERT INTO processed VALUES (?)", (event["event_id"],))
        db.execute("INSERT INTO balances VALUES (?, 1) ON CONFLICT(entity) DO UPDATE SET value=value+1", (event["entity_id"],))
    return {"accepted": True}
