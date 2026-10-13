"""CLI and evaluation clients for the same durable worker used by the API."""
import asyncio
import sys
import uuid

from replaylab.catalog import contract_for, original_source
from replaylab.schemas import CreateRun, IncidentBundle, digest
from replaylab.store import TERMINAL


def reviewed_input(value):
    incident = IncidentBundle.model_validate(value).model_dump(mode="json")
    original_source(incident["fixture_id"], incident["revision"])
    if incident["contract"] != contract_for(incident["fixture_id"], approved=incident["contract"]["approved"]).model_dump(mode="json"):
        raise ValueError("incident must use the published behavior contract")
    if not incident["contract"]["approved"]:
        raise ValueError("approve the incident's published contract before CLI execution")
    return incident


async def run_once(app, incident, mode="reference", verbose=True):
    incident = reviewed_input(incident)
    if mode == "live" and not app.state.worker.settings.live_ready:
        raise ValueError("live mode requires configured NVIDIA inference and Token Factory Sandbox access")
    store, worker = app.state.store, app.state.worker
    owner = str(uuid.uuid4())
    incident_id = store.save_incident(owner, incident)
    request = CreateRun(incident_id=incident_id, mode=mode, idempotency_key=str(uuid.uuid4()))
    ident, _ = store.create_run(owner, request, digest({"incident": incident, "mode": mode}), worker.settings.max_queued, incident)
    worker.wake.set()
    cursor = 0
    try:
        while True:
            for event in store.events(ident, cursor):
                cursor = event["id"]
                if verbose:
                    print(f'{event["state"]}: {event["message"]}', file=sys.stderr, flush=True)
            row = store.get_run(ident, owner)
            if row["state"] in TERMINAL:
                return row
            if not worker.task or worker.task.done():
                raise RuntimeError("investigation worker stopped before completing the run")
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        store.cancel(ident, owner)
        worker.cancel(ident)
        raise
