"""Authored clean control: no repair should be requested."""
def handle(db, event):
    key, customer = event["event_id"], event["entity_id"]
    if db.execute("SELECT event_id FROM processed WHERE event_id=?", (key,)).fetchone() is None:
        previous = db.execute("SELECT value FROM balances WHERE entity=?", (customer,)).fetchone()
        total = (previous[0] if previous else 0) + event["payload"]["credits"]
        db.execute("INSERT INTO processed VALUES (?)", (key,))
        db.execute("INSERT OR REPLACE INTO balances VALUES (?, ?)", (customer, total))
    return {"accepted": True}
