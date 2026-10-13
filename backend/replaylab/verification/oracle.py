"""Independent, hand-authored business semantics; never supplied as patch context."""
from copy import deepcopy


def expected_states(fixture, initial, steps):
    state, seen, outputs = deepcopy(initial), set(), []
    for step in steps:
        if step["kind"] == "delivery":
            entity, event_id, payload = step["entity_id"], step["event_id"], step["payload"]
            if fixture == "subscriptions":
                if payload["version"] > state.get(entity, {"version": 0})["version"]:
                    state[entity] = {"version": payload["version"], "status": payload["status"]}
            elif event_id not in seen:
                state[entity] = state.get(entity, 0) + (payload["credits"] if fixture == "credits" else 1)
            seen.add(event_id)
        outputs.append(deepcopy(state))
    return outputs


def verify(fixture, initial, scenario, observed):
    expected = expected_states(fixture, initial, scenario["steps"])
    failures = []
    if observed.get("infrastructure_error"):
        return {"passed": False, "inconclusive": True, "failures": [observed["infrastructure_error"]]}
    if len(observed.get("steps", [])) != len(expected):
        return {"passed": False, "inconclusive": True, "failures": ["incomplete replay trace"]}
    for i, (want, actual) in enumerate(zip(expected, observed["steps"])):
        if want != actual["state"]:
            failures.append({"step": i, "expected": want, "actual": actual["state"], "reason": "business state violates reviewed contract"})
        if scenario["steps"][i]["kind"] == "delivery" and actual.get("status") != 200:
            failures.append({"step": i, "reason": "delivery must acknowledge with HTTP 200", "status": actual.get("status")})
    return {"passed": not failures, "inconclusive": False, "failures": failures}
