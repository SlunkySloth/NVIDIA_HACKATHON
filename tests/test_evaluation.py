from argparse import Namespace

import pytest
from replaylab.catalog import original_source
from replaylab.evaluation.batch import summarize
from replaylab.evaluation.cases import cases
from replaylab.models.policy import validate_test
from replaylab.orchestration.worker import reference_test
from replaylab.replay.runner import regression, replay
from replaylab.replay.scenarios import scenarios
from replaylab.sandboxes.local import baseline
from replaylab.schemas import IncidentBundle
from replaylab.verification.oracle import verify


@pytest.mark.parametrize("case", cases(), ids=lambda item: item["name"])
def test_frozen_incidents_have_the_independently_expected_original_outcome(case):
    incident = IncidentBundle.model_validate(case["incident"]).model_dump(mode="json")
    fixture = incident["fixture_id"]
    source = original_source(fixture, incident["revision"])
    scenario = scenarios(incident)[0]
    observed = replay(source, fixture, incident["initial_state"], scenario)
    checked = verify(fixture, incident["initial_state"], scenario, observed)
    assert not checked["inconclusive"], checked
    assert checked["passed"] != case["defective"], checked


def test_a_restart_dependent_regression_is_red_then_green():
    incident = cases()[0]["incident"]
    test = validate_test(reference_test(incident))
    assert "/__replay/restart" in test
    red = regression(original_source("credits", incident["revision"]), "credits", incident["initial_state"], test)
    green = regression(baseline("credits"), "credits", incident["initial_state"], test)
    assert red["meaningful_failure"], red
    assert green["exit_status"] == 0 and green["passed"] == 1, green


def test_report_denominators_keep_failures_and_unattempted_cases():
    rows = [
        {"state": "EXPORTED", "defective": True, "reproduced": True, "candidate_present": True, "model_tokens": 30, "estimated_inference_cost_usd": None},
        {"state": "PATCH_REJECTED", "defective": True, "reproduced": True, "candidate_present": True, "model_tokens": 40, "estimated_inference_cost_usd": None},
        {"state": "NOT_REPRODUCED", "defective": False, "reproduced": False, "candidate_present": False, "model_tokens": 0, "estimated_inference_cost_usd": 0},
        {"state": "NOT_ATTEMPTED", "defective": True},
    ]
    summary = summarize(rows)
    assert summary["planned"] == 4 and summary["attempted"] == 3
    assert summary["verified_fix_rate"] == 0.5
    assert summary["clean_false_repair_rate"] == 0
    assert summary["not_attempted"] == 1
    assert summary["estimated_inference_cost_usd"] is None
    rows[0].update(model_tokens=None, budgeted_tokens=5000)
    summary = summarize(rows)
    assert summary["total_model_tokens"] is None
    assert summary["total_budgeted_tokens"] == 5040


@pytest.mark.asyncio
async def test_live_evaluation_requires_access_before_starting_a_batch(settings, tmp_path):
    from replaylab.evaluation.batch import evaluate_incidents
    with pytest.raises(ValueError, match="requires configured"):
        await evaluate_incidents(Namespace(mode="live", output=tmp_path / "results.json"), settings)
    assert not (tmp_path / "results.json").exists()
