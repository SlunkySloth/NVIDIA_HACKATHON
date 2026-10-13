
import pytest
from replaylab.catalog import sample
from replaylab.recordings import export_recording, get_recording
from replaylab.schemas import CreateRun, digest


def test_private_or_edited_incidents_cannot_be_published_as_recordings(settings):
    from replaylab.store import Store
    store = Store(settings.data_dir)
    incident = sample("credits").model_dump(mode="json")
    incident["symptom"] = "Private edited incident"
    incident["contract"]["approved"] = True
    incident_id = store.save_incident("private-owner", incident)
    request = CreateRun(incident_id=incident_id, idempotency_key="private-recording")
    ident, _ = store.create_run("private-owner", request, digest(incident), 8, incident)
    store.transition(ident, "EXPORTED", "Test fixture", {"verdict": "Verified for tested scenarios"})
    with pytest.raises(ValueError, match="unchanged original synthetic"):
        export_recording(settings, store, ident)
    assert not (settings.data_dir / "recordings").exists()


def test_recording_route_treats_invalid_identifiers_as_missing(settings):
    assert get_recording(settings.data_dir, "../metadata.sqlite") is None
    assert get_recording(settings.data_dir, "not-an-id") is None


def test_recordings_do_not_expose_noncompleted_runs(client, settings):
    from replaylab.store import Store
    incident = sample("credits").model_dump(mode="json")
    data = client.post("/api/incidents", json=incident).json()
    store = Store(settings.data_dir)
    assert store.incident(data["id"], client.cookies["replaylab_session"])
    assert client.get("/api/recordings").json() == []
    assert client.get("/api/recordings/not-an-id").status_code == 404
    assert client.get("/api/recordings/not-an-id/artifacts/evidence.zip").status_code == 404
