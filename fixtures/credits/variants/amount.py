"""Deliberate defect: equal purchase amounts are treated as the same event."""
def handle(db, event):
    purchase_key = "amount-" + str(event["payload"]["credits"])
    exists = db.execute("SELECT 1 FROM processed WHERE event_id=?", (purchase_key,)).fetchone()
    if not exists:
        db.execute("INSERT INTO processed VALUES (?)", (purchase_key,))
        db.execute("INSERT INTO balances VALUES (?, ?) ON CONFLICT(entity) DO UPDATE SET value=value+excluded.value", (event["entity_id"], event["payload"]["credits"]))
    return {"accepted": True}
