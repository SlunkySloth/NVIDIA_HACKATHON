from __future__ import annotations

import asyncio
import json
import re
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from replaylab.catalog import catalog, contract_for, original_source
from replaylab.config import ROOT, Settings
from replaylab.orchestration.worker import Worker
from replaylab.recordings import directory as recording_directory
from replaylab.recordings import get_recording, list_recordings
from replaylab.schemas import BehaviorContract, CreateRun, IncidentBundle, digest
from replaylab.store import TERMINAL, Store


def redact(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[redacted email]", text)
    text = re.sub(r"(?i)(?:bearer\s+\S+|(?:sk|key|token)[_-][a-zA-Z0-9_-]{16,})", "[redacted credential]", text)
    return text


def create_app(settings=None):
    settings = settings or Settings()
    store = Store(settings.data_dir)
    worker = Worker(store, settings)

    @asynccontextmanager
    async def lifespan(app):
        # A process-level lease prevents multiple API workers consuming one queue.
        import fcntl
        lease = (settings.data_dir / "worker.lock").open("a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise RuntimeError("ReplayLab supports one API worker per metadata directory")
        await worker.start()
        try:
            yield
        finally:
            await worker.close()
            lease.close()

    app = FastAPI(title="ReplayLab", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.worker = store, worker

    @app.middleware("http")
    async def session(request, call_next):
        from starlette.responses import JSONResponse
        if request.method in {"POST", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "cross-origin write rejected"}, status_code=403)
        if request.headers.get("content-length"):
            try:
                if int(request.headers["content-length"]) > 131072:
                    return JSONResponse({"detail": "request exceeds 128 KiB"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "invalid content length"}, status_code=400)
        # Bound chunked uploads too; import accepts JSON only.
        if request.method in {"POST", "PUT"}:
            total, chunks = 0, []
            async for chunk in request.stream():
                total += len(chunk)
                if total > 131072:
                    return JSONResponse({"detail": "request exceeds 128 KiB"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        token = request.cookies.get("replaylab_session", "")
        fresh = not re.fullmatch(r"[a-f0-9]{64}", token)
        if fresh:
            token = secrets.token_hex(32)
        request.state.owner = token
        response = await call_next(request)
        if fresh:
            response.set_cookie("replaylab_session", token, httponly=True, samesite="strict", secure=settings.secure_cookie, max_age=30 * 86400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    def owned_run(ident, request):
        row = store.get_run(ident, request.state.owner)
        if not row:
            raise HTTPException(404, "investigation not found in this session")
        return row

    @app.get("/health")
    async def health():
        return {"ready": bool(worker.task and not worker.task.done()), "live_configured": settings.live_ready, "model": settings.model or None, "execution_provider": "Token Factory Sandboxes" if settings.live_ready else "local reference only", "public_demo": settings.public_demo}

    @app.get("/api/fixtures")
    async def fixtures():
        return catalog()

    @app.get("/api/schema/incident")
    async def schema():
        return IncidentBundle.model_json_schema()

    @app.get("/api/recordings")
    async def recordings():
        return list_recordings(settings.data_dir)

    @app.get("/api/recordings/{ident}")
    async def recording(ident: str):
        value = get_recording(settings.data_dir, ident)
        if not value:
            raise HTTPException(404, "recorded investigation not found")
        return value

    @app.get("/api/recordings/{ident}/artifacts/{name}")
    async def recording_artifact(ident: str, name: str):
        value = get_recording(settings.data_dir, ident)
        if not value or name not in {a["name"] for a in value["run"]["result"].get("artifacts", [])}:
            raise HTTPException(404, "recorded artifact not found")
        path = recording_directory(settings.data_dir, ident) / name
        if not path.is_file():
            raise HTTPException(404, "recorded artifact unavailable")
        return FileResponse(path, filename=name, media_type="application/zip" if name.endswith(".zip") else "application/octet-stream")

    @app.post("/api/incidents", status_code=201)
    async def incidents(bundle: IncidentBundle, request: Request):
        try:
            original_source(bundle.fixture_id, bundle.revision)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if bundle.contract != contract_for(bundle.fixture_id, approved=bundle.contract.approved):
            raise HTTPException(422, "this adapter requires the published behavior contract")
        if settings.public_demo and bundle.provenance != "original synthetic fixture":
            raise HTTPException(403, "public demo accepts curated synthetic fixtures only")
        if settings.public_demo:
            known = next(f["incident"] for f in catalog() if f["id"] == bundle.fixture_id)
            submitted = bundle.model_dump(mode="json")
            submitted["contract"]["approved"] = False
            if submitted != known:
                raise HTTPException(403, "public demo is limited to unchanged curated incidents")
        data = bundle.model_dump(mode="json")
        data["symptom"] = redact(data["symptom"])
        data["contract"]["rules"] = [redact(r) for r in data["contract"]["rules"]]
        ident = store.save_incident(request.state.owner, data)
        return {"id": ident, "incident": data}

    @app.get("/api/incidents/{ident}")
    async def get_incident(ident: str, request: Request):
        bundle = store.incident(ident, request.state.owner)
        if not bundle:
            raise HTTPException(404, "incident not found")
        return {"id": ident, "incident": bundle}

    @app.put("/api/incidents/{ident}/contract")
    async def save_contract(ident: str, contract: BehaviorContract, request: Request):
        bundle = store.incident(ident, request.state.owner)
        if not bundle:
            raise HTTPException(404, "incident not found")
        if contract.fixture_id != bundle["fixture_id"] or contract.id != bundle["contract"]["id"]:
            raise HTTPException(422, "contract does not match incident")
        # Business semantics are this adapter's published scope. Free text is
        # annotation, not an alternative unimplemented semantic contract.
        previous, reviewed = dict(bundle["contract"]), contract.model_dump(mode="json")
        previous["approved"] = reviewed["approved"]
        if previous != reviewed:
            raise HTTPException(422, "this adapter supports the published contract; import different semantics requires a new adapter")
        store.update_contract(ident, request.state.owner, reviewed)
        return reviewed

    @app.post("/api/runs", status_code=202)
    async def create_run(req: CreateRun, request: Request):
        bundle = store.incident(req.incident_id, request.state.owner)
        if not bundle:
            raise HTTPException(404, "incident not found")
        if not bundle["contract"]["approved"]:
            raise HTTPException(409, "review and approve the behavior contract first")
        if req.mode == "live" and not settings.live_ready:
            raise HTTPException(503, "configure NEBIUS_API_KEY, NEBIUS_MODEL and Token Factory Sandbox access to run live")
        try:
            ident, created = store.create_run(request.state.owner, req, digest({"incident": bundle, "mode": req.mode}), settings.max_queued, bundle)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except OverflowError as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc
        worker.wake.set()
        return {"id": ident, "created": created}

    @app.get("/api/runs/{ident}")
    async def run(ident: str, request: Request):
        row = owned_run(ident, request)
        row.pop("input_bundle", None)
        return row

    @app.get("/api/runs/{ident}/events")
    async def events(ident: str, request: Request, after: int = 0):
        owned_run(ident, request)
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
            if cursor < 0:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(400, "invalid progress cursor") from exc

        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                rows = store.events(ident, cursor)
                for event in rows:
                    cursor = event["id"]
                    yield f'id: {cursor}\nevent: progress\ndata: {json.dumps(event)}\n\n'
                if store.get_run(ident)["state"] in TERMINAL and len(rows) < 200:
                    yield 'event: complete\ndata: {}\n\n'
                    break
                yield ': keepalive\n\n'
                await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/runs/{ident}/cancel")
    async def cancel(ident: str, request: Request):
        owned_run(ident, request)
        store.cancel(ident, request.state.owner)
        worker.cancel(ident)
        return {"state": store.get_run(ident)["state"]}

    @app.get("/api/runs/{ident}/artifacts")
    async def artifacts(ident: str, request: Request):
        row = owned_run(ident, request)
        return (row["result"] or {}).get("artifacts", [])

    @app.get("/api/runs/{ident}/artifacts/{name}")
    async def artifact(ident: str, name: str, request: Request):
        row = owned_run(ident, request)
        allowed = {a["name"] for a in (row["result"] or {}).get("artifacts", [])}
        if name not in allowed:
            raise HTTPException(404, "artifact not found")
        path = settings.data_dir / "artifacts" / ident / name
        if not path.is_file():
            raise HTTPException(404, "artifact expired or unavailable")
        return FileResponse(path, filename=name, media_type="application/zip" if name.endswith(".zip") else "application/octet-stream")

    dist = ROOT / "apps/web/dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    if (dist / "index.html").exists():
        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "API endpoint not found")
            return FileResponse(dist / "index.html")
    return app
