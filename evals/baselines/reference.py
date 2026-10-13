"""Human-authored reference patches. Excluded from live model context and sandbox image."""

def source(fixture):
    if fixture == "subscriptions":
        return '''def handle(db, event):
    with db:
        db.execute("INSERT INTO subscriptions(entity, status, version) VALUES (?, ?, ?) ON CONFLICT(entity) DO UPDATE SET status=excluded.status, version=excluded.version WHERE excluded.version > subscriptions.version", (event["entity_id"], event["payload"]["status"], event["payload"]["version"]))
    return {"accepted": True}
'''
    value = 'event["payload"]["credits"]' if fixture == "credits" else "1"
    return f'''def handle(db, event):
    with db:
        inserted = db.execute("INSERT OR IGNORE INTO processed(event_id) VALUES (?)", (event["event_id"],)).rowcount
        if inserted:
            db.execute("INSERT INTO balances(entity, value) VALUES (?, ?) ON CONFLICT(entity) DO UPDATE SET value=value+excluded.value", (event["entity_id"], {value}))
    return {{"accepted": True}}
'''


def flawed_source(fixture, flaw="memory"):
    base = source(fixture)
    if fixture == "subscriptions":
        return base.replace(" WHERE excluded.version > subscriptions.version", "")
    if flaw == "memory":
        return 'seen = set()\n' + base.replace('inserted = db.execute("INSERT OR IGNORE INTO processed(event_id) VALUES (?)", (event["event_id"],)).rowcount', 'inserted = event["event_id"] not in seen\n        seen.add(event["event_id"])')
    if flaw == "ignore_later":
        return base.replace('(event["event_id"],)', '("all",)')
    if flaw == "amount":
        return base.replace('(event["event_id"],)', '(str(event["payload"].get("credits", 1)),)')
    if flaw == "entity_shared":
        return base.replace('event["entity_id"], ', '"customer_01", ')
    if flaw == "no_effect":
        return 'def handle(db, event):\n    return {"accepted": True}\n'
    raise ValueError(flaw)
