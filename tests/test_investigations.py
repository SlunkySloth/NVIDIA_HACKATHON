import asyncio
import json
import time
from argparse import Namespace

import pytest
from replaylab.artifacts.bundle import read_bundle
from replaylab.catalog import sample
from replaylab.cli import reproduce
from replaylab.replay.scenarios import GENERATOR_VERSION
from replaylab.sandboxes.local import LocalReference, baseline
from replaylab.store import TERMINAL


def start_run(client, fixture="credits", mode="reference"):
    response = client.post("/api/incidents", json=sample(fixture).model_dump(mode="json"))
    assert response.status_code == 201, response.text
    data = response.json()
    contract = dict(data["incident"]["contract"], approved=True)
    assert client.put(f'/api/incidents/{data["id"]}/contract', json=contract).status_code == 200
    response = client.post("/api/runs", json={"incident_id": data["id"], "mode": mode, "idempotency_key": "integration-run"})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def completed_run(client, ident):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{ident}")
        assert response.status_code == 200, response.text
        row = response.json()
        if row["state"] in TERMINAL:
            return row
        time.sleep(0.1)
    pytest.fail("investigation did not reach a terminal state")


@pytest.mark.parametrize("fixture", ["credits", "fulfillment", "subscriptions"])
def test_reference_investigation_exports_red_green_evidence(client, settings, fixture):
    ident = start_run(client, fixture)
    row = completed_run(client, ident)
    assert row["state"] == "EXPORTED", row["result"]["explanation"]
    result = row["result"]
    assert result["verdict"] == "Verified for tested scenarios"
    assert result["regression"]["original"]["meaningful_failure"]
    assert result["regression"]["candidate"]["passed"] > 0
    assert not result["original_results"][0]["check"]["passed"]
    assert all(observation["check"]["passed"] for observation in result["candidate_results"])
    assert result["manifest"]["model_calls"] == []
    assert isinstance(result["manifest"]["working_tree_dirty"], bool)
    assert result["manifest"]["scenario_generator_version"] == GENERATOR_VERSION
    assert result["diff"] and result["counterexample"]["length"] == 2
    response = client.get(f"/api/runs/{ident}/artifacts/evidence.zip")
    assert response.status_code == 200
    archive = settings.data_dir / f"{fixture}-download.zip"
    archive.write_bytes(response.content)
    files = read_bundle(archive)
    assert files["candidate_handler.py"] == result["candidate_source"]
    assert json.loads(files["run-manifest.json"])["verdict"] == result["verdict"]
    progress = client.get(f"/api/runs/{ident}/events").text
    assert "event: complete" in progress and "REPRODUCED" in progress
    cursor = client.get(f"/api/runs/{ident}").json()
    assert "owner" not in cursor and "input_bundle" not in cursor
    if fixture == "credits":
        assert asyncio.run(reproduce(Namespace(bundle=archive, provider="local"))) == 0
        from replaylab.recordings import export_recording
        assert export_recording(settings, client.app.state.store, ident) == ident
        recorded = client.get(f"/api/recordings/{ident}")
        assert recorded.status_code == 200
        assert recorded.json()["recorded"] is True
        assert "owner" not in recorded.json()["run"]
        assert "input_bundle" not in recorded.json()["run"]
        assert client.get(f"/api/recordings/{ident}/artifacts/evidence.zip").content == response.content


@pytest.mark.parametrize("fixture,failed_scenario", [("credits", "restart"), ("subscriptions", "incident")])
def test_flawed_patch_is_rejected_with_a_counterexample(client, fixture, failed_scenario):
    result = completed_run(client, start_run(client, fixture, "flawed"))
    assert result["state"] == "PATCH_REJECTED", result["result"]["explanation"]
    evidence = result["result"]
    assert not next(row for row in evidence["candidate_results"] if row["scenario_id"] == failed_scenario)["check"]["passed"]
    assert evidence["rejection_counterexample"]["length"] >= 2
    if fixture == "credits":
        assert evidence["regression"]["candidate"]["exit_status"] == 0


def test_candidate_test_collection_failure_is_inconclusive(client, monkeypatch):
    original_regression = LocalReference.regression

    async def regression_with_collection_error(adapter, source, fixture, initial, test):
        if source == baseline(fixture):
            return {"collected": 0, "passed": 0, "failures": 0, "errors": 1, "exit_status": 2, "output": "collection failed", "meaningful_failure": False}
        return await original_regression(adapter, source, fixture, initial, test)

    monkeypatch.setattr(LocalReference, "regression", regression_with_collection_error)
    row = completed_run(client, start_run(client))
    assert row["state"] == "INCONCLUSIVE"
    assert "candidate regression could not complete" in row["result"]["explanation"]


def test_single_delivery_is_not_reproduced(client):
    incident = sample("credits").model_dump(mode="json")
    incident["steps"] = incident["steps"][:1]
    incident["contract"]["approved"] = True
    ident = client.post("/api/incidents", json=incident).json()["id"]
    run = client.post("/api/runs", json={"incident_id": ident, "idempotency_key": "single-event"}).json()["id"]
    row = completed_run(client, run)
    assert row["state"] == "NOT_REPRODUCED"
    assert row["result"]["candidate_source"] == ""
