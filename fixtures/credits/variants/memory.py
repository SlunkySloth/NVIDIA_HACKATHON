"""Deliberate defect: delivery identity is lost when the process restarts."""
delivered = set()


def handle(db, event):
    if event["event_id"] not in delivered:
        delivered.add(event["event_id"])
        db.execute("INSERT INTO balances VALUES (?, ?) ON CONFLICT(entity) DO UPDATE SET value=value+excluded.value", (event["entity_id"], event["payload"]["credits"]))
    return {"accepted": True}
