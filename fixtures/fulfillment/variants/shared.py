"""Deliberate defect: each new event updates the first order's ledger."""
def handle(db, event):
    if db.execute("SELECT 1 FROM processed WHERE event_id=?", (event["event_id"],)).fetchone():
        return {"accepted": True}
    db.execute("INSERT INTO processed VALUES (?)", (event["event_id"],))
    existing = db.execute("SELECT entity FROM balances ORDER BY entity LIMIT 1").fetchone()
    target = existing[0] if existing else event["entity_id"]
    db.execute("INSERT INTO balances VALUES (?, 1) ON CONFLICT(entity) DO UPDATE SET value=value+1", (target,))
    return {"accepted": True}
