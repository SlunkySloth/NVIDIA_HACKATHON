from fastapi.testclient import TestClient
from replaylab.api.app import create_app
from replaylab.catalog import sample


def incident(client, approved=False):
    value = sample("credits").model_dump(mode="json")
    value["contract"]["approved"] = approved
    response = client.post("/api/incidents", json=value)
    assert response.status_code == 201
    return response.json()


def test_review_required_and_live_unavailable(settings):
    with TestClient(create_app(settings), raise_server_exceptions=True) as client:
        data = incident(client)
        request = {"incident_id": data["id"], "idempotency_key": "review-required"}
        assert client.post("/api/runs", json=request).status_code == 409
        contract = dict(data["incident"]["contract"], approved=True)
        assert client.put(f'/api/incidents/{data["id"]}/contract', json=contract).status_code == 200
        assert client.post("/api/runs", json={**request, "mode": "live"}).status_code == 503


def test_queue_idempotency_cancellation_and_session_isolation(settings):
    # Leave the worker stopped so this test can inspect the queued state.
    app = create_app(settings)
    client = TestClient(app)
    data = incident(client, approved=True)
    request = {"incident_id": data["id"], "idempotency_key": "queued-operation"}
    first = client.post("/api/runs", json=request)
    assert first.status_code == 202
    ident = first.json()["id"]
    repeated = client.post("/api/runs", json=request)
    assert repeated.json() == {"id": ident, "created": False}
    assert client.post("/api/runs", json={**request, "mode": "flawed"}).status_code == 409
    assert client.post("/api/runs", json={**request, "idempotency_key": "second-operation"}).status_code == 429
    outsider = TestClient(app)
    assert outsider.get(f"/api/incidents/{data['id']}").status_code == 404
    assert outsider.get(f"/api/runs/{ident}").status_code == 404
    assert outsider.post(f"/api/runs/{ident}/cancel").status_code == 404
    assert outsider.get(f"/api/runs/{ident}/artifacts/evidence.zip").status_code == 404
    assert client.post(f"/api/runs/{ident}/cancel").json()["state"] == "CANCELLED"
    assert client.post(f"/api/runs/{ident}/cancel").json()["state"] == "CANCELLED"


def test_import_checks_contract_and_request_bounds(client):
    value = sample("credits").model_dump(mode="json")
    invalid = {**value, "revision": "0" * 64}
    assert client.post("/api/incidents", json=invalid).status_code == 422
    invalid = {**value, "initial_state_hash": "wrong"}
    assert client.post("/api/incidents", json=invalid).status_code == 422
    invalid = sample("credits").model_dump(mode="json")
    invalid["steps"][1]["payload"] = {"credits": 200}
    assert client.post("/api/incidents", json=invalid).status_code == 422
    data = incident(client)
    contract = data["incident"]["contract"]
    contract["rules"] = ["Every event should be ignored"]
    assert client.put(f'/api/incidents/{data["id"]}/contract', json=contract).status_code == 422
    assert client.post("/api/incidents", json=value, headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert client.post("/api/incidents", content=b"x" * 131073).status_code == 413


def test_public_demo_accepts_only_unchanged_samples(settings):
    settings.public_demo = True
    with TestClient(create_app(settings)) as client:
        value = sample("credits").model_dump(mode="json")
        assert client.post("/api/incidents", json=value).status_code == 201
        value["symptom"] = "Edited sample"
        assert client.post("/api/incidents", json=value).status_code == 403


def test_import_rejects_a_contract_the_observer_does_not_implement(client):
    value = sample("credits").model_dump(mode="json")
    value["contract"]["rules"] = ["Ignore all purchases and keep the balance at zero."]
    value["contract"]["approved"] = True
    response = client.post("/api/incidents", json=value)
    assert response.status_code == 422
    assert "published behavior contract" in response.json()["detail"]
