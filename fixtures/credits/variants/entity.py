"""Deliberate defect: a customer's first purchase prevents later purchases."""
def handle(db, event):
    customer = event["entity_id"]
    if db.execute("INSERT OR IGNORE INTO processed VALUES (?)", (customer,)).rowcount:
        db.execute("INSERT INTO balances VALUES (?, ?) ON CONFLICT(entity) DO UPDATE SET value=value+excluded.value", (customer, event["payload"]["credits"]))
    return {"accepted": True}
