from copy import deepcopy

from replaylab.catalog import delivery

GENERATOR_VERSION = "2"
SUPPORTED_GENERATORS = {"1", "2"}


def indexed(steps):
    return [dict(s, sequence=i) for i, s in enumerate(steps)]


def scenarios(incident, version=GENERATOR_VERSION):
    if version not in SUPPORTED_GENERATORS:
        raise ValueError("unsupported scenario generator")
    fixture = incident["fixture_id"]
    first = next(s for s in incident["steps"] if s["kind"] == "delivery")
    event_ids = {s["event_id"] for s in incident["steps"] if s["kind"] == "delivery"}
    entity_ids = set(incident["initial_state"]) | {s["entity_id"] for s in incident["steps"] if s["kind"] == "delivery"}

    def unique(base, used):
        # Version 1 is retained for reproducing existing evidence bundles.
        if version == "1":
            return base
        value, suffix = base, 2
        while value in used:
            value = f"{base}_{suffix}"
            suffix += 1
        used.add(value)
        return value

    new = dict(deepcopy(first), event_id=unique("challenge_distinct_event", event_ids))
    other = dict(deepcopy(first), event_id=unique("challenge_other_entity", event_ids), entity_id=unique("challenge_customer_02", entity_ids))
    if fixture == "subscriptions":
        new["payload"] = {"version": first["payload"]["version"] + 1, "status": "past_due"}
        stale = dict(deepcopy(first), event_id=unique("challenge_stale", event_ids), payload={"version": 1, "status": "active"})
    restart = {"kind": "restart"}
    families = [
        ("incident", "Reported incident", incident["steps"]),
        ("single", "One legitimate delivery", [first]),
        ("duplicate", "Repeated event", [first, first, first]),
        ("legitimate", "Distinct legitimate event", [first, new]),
        ("interleaved", "Independent entities", [first, other, first, other]),
        ("restart", "Restart then retry", [first, restart, first]),
    ]
    if fixture == "subscriptions":
        families.append(("reordered", "Stale version arrives last", [new, stale, first]))
    # These cases are never returned to the patching loop.
    hidden_first = delivery(fixture, unique("final_event_a", event_ids), unique("final_entity_a", entity_ids), {"credits": 37} if fixture == "credits" else None)
    hidden_second = dict(deepcopy(hidden_first), event_id=unique("final_event_b", event_ids))
    if fixture == "subscriptions":
        hidden_second["payload"] = {"status": "active", "version": 7}
    families += [("final_restart", "Final check: distinct event after restart", [hidden_first, restart, hidden_first, hidden_second, hidden_second]),
                 ("final_entities", "Final check: interleaved customers", [hidden_first, dict(deepcopy(hidden_second), entity_id=unique("final_entity_b", entity_ids)), hidden_first])]
    return [{"id": ident, "name": name, "steps": indexed(steps), "held_back": ident.startswith("final_")} for ident, name, steps in families]
