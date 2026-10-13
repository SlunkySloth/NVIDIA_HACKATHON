import pytest
from replaylab.catalog import sample
from replaylab.replay.scenarios import scenarios
from replaylab.schemas import IncidentBundle, digest
from replaylab.verification.oracle import expected_states


@pytest.mark.parametrize("fixture", ["credits", "fulfillment", "subscriptions"])
def test_sample_scenarios_retain_the_recorded_version_one_behavior(fixture):
    incident = sample(fixture).model_dump(mode="json")
    assert scenarios(incident, version="1") == scenarios(incident)


@pytest.mark.parametrize("event_id", ["challenge_distinct_event", "challenge_other_entity", "final_event_a", "final_event_b"])
def test_challenges_do_not_reuse_imported_event_or_entity_identity(event_id):
    incident = sample("credits").model_dump(mode="json")
    for step in incident["steps"]:
        step.update(event_id=event_id, entity_id="challenge_customer_02")
    incident["initial_state"] = {"final_entity_a": 1000, "final_entity_b": 900, "challenge_customer_02": 5}
    incident["initial_state_hash"] = digest(incident["initial_state"])
    cases = scenarios(incident)
    assert cases == scenarios(incident)
    for case in cases:
        IncidentBundle.model_validate({**incident, "steps": case["steps"]})
    legitimate = next(case for case in cases if case["id"] == "legitimate")
    assert len({step["event_id"] for step in legitimate["steps"]}) == 2
    assert expected_states("credits", incident["initial_state"], legitimate["steps"])[-1]["challenge_customer_02"] == 205
    for case in cases:
        if case["held_back"]:
            for step in case["steps"]:
                if step["kind"] == "delivery":
                    assert step["event_id"] != event_id
                    assert step["entity_id"] not in incident["initial_state"]
