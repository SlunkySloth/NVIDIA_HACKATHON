"""Deliberate defect: every delivery grants credits again."""

def handle(db, event):
    db.execute("INSERT INTO balances(entity, value) VALUES (?, ?) ON CONFLICT(entity) DO UPDATE SET value=value+excluded.value", (event["entity_id"], event["payload"]["credits"]))
    db.commit()
    return {"accepted": True}
