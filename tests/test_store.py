from replaylab.catalog import sample
from replaylab.schemas import CreateRun, digest
from replaylab.store import Store


def test_cancellation_freezes_the_verdict_and_cannot_be_overwritten(tmp_path):
    store = Store(tmp_path)
    incident = sample("credits").model_dump(mode="json")
    incident_id = store.save_incident("owner", incident)
    request = CreateRun(incident_id=incident_id, idempotency_key="cancel-test")
    ident, _ = store.create_run("owner", request, digest(incident), 8, incident)
    store.transition(ident, "REPRODUCING", "Replaying", {"verdict": "Inconclusive", "manifest": {}})
    assert store.cancel(ident, "owner")
    row = store.get_run(ident, "owner")
    assert row["state"] == "CANCELLED"
    assert row["result"]["verdict"] == "Cancelled"
    assert row["result"]["manifest"]["elapsed_seconds"] >= 0
    store.transition(ident, "EXPORTED", "Too late", {"verdict": "Verified"})
    assert store.get_run(ident, "owner") == row
    assert store.cancel(ident, "owner")
    assert len([event for event in store.events(ident) if event["state"] == "CANCELLED"]) == 1


def test_recovery_marks_interrupted_runs_inconclusive_and_keeps_queued_work(tmp_path):
    store = Store(tmp_path)
    incident = sample("credits").model_dump(mode="json")
    ident = store.save_incident("owner", incident)
    request = CreateRun(incident_id=ident, idempotency_key="recovery-test")
    run_id, _ = store.create_run("owner", request, digest(incident), 8, incident)
    store.claim("previous-worker")
    store.recover()
    assert store.get_run(run_id)["state"] == "INCONCLUSIVE"
    assert store.claim("new-worker") is None
    request.idempotency_key = "queued-after-recovery"
    queued, _ = store.create_run("owner", request, digest(incident), 8, incident)
    store.recover()
    assert store.get_run(queued)["state"] == "CREATED"
    assert store.claim("new-worker")["id"] == queued
