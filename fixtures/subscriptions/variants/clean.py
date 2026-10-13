"""Authored clean control: strictly higher versions replace entity state."""
def handle(db, event):
    customer, incoming = event["entity_id"], event["payload"]
    current = db.execute("SELECT version FROM subscriptions WHERE entity=?", (customer,)).fetchone()
    if current is None or incoming["version"] > current[0]:
        db.execute("DELETE FROM subscriptions WHERE entity=?", (customer,))
        db.execute("INSERT INTO subscriptions VALUES (?, ?, ?)", (customer, incoming["status"], incoming["version"]))
    return {"accepted": True}
