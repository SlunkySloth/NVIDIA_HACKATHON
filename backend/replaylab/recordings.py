"""Read-only, explicitly recorded investigations from curated synthetic inputs."""
import json
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from replaylab.artifacts.bundle import read_bundle
from replaylab.catalog import sample


def directory(data_dir, ident):
    if str(UUID(ident)) != ident:
        raise ValueError("invalid recording ID")
    return data_dir / "recordings" / ident


def get_recording(data_dir, ident):
    try:
        path = directory(data_dir, ident) / "recording.json"
        if not path.is_file() or path.stat().st_size > 4 * 1024**2:
            return None
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None


def list_recordings(data_dir):
    root = data_dir / "recordings"
    rows = []
    if not root.exists():
        return rows
    for path in root.iterdir():
        recorded = get_recording(data_dir, path.name)
        if recorded:
            run, incident = recorded["run"], recorded["incident"]
            rows.append({"id": run["id"], "fixture_id": incident["fixture_id"], "title": incident["symptom"], "mode": run["mode"], "created": run["created"], "verdict": run["result"]["verdict"], "model_ids": run["result"]["manifest"].get("model_ids", [])})
    return sorted(rows, key=lambda row: row["created"], reverse=True)[:12]


def export_recording(settings, store, ident):
    row = store.get_run(ident)
    if not row or row["state"] not in {"EXPORTED", "PATCH_REJECTED"} or not row["result"]:
        raise ValueError("recordings require a completed verified or rejected investigation")
    incident = json.loads(row["input_bundle"])
    canonical = sample(incident["fixture_id"]).model_dump(mode="json")
    canonical["contract"]["approved"] = True
    if incident != canonical:
        raise ValueError("public recordings accept unchanged original synthetic samples only")
    source = settings.data_dir / "artifacts" / ident
    read_bundle(source / "evidence.zip")
    target = directory(settings.data_dir, ident)
    if target.exists():
        return ident
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"recorded": True, "incident": incident, "run": {name: row[name] for name in ("id", "incident_id", "mode", "state", "created", "updated", "result")}, "events": store.events(ident)}
    with tempfile.TemporaryDirectory(prefix="pending-", dir=target.parent) as temporary:
        staging = Path(temporary) / ident
        staging.mkdir()
        for artifact in row["result"]["artifacts"]:
            name = artifact["name"]
            if Path(name).name != name or name in {".", "..", "recording.json"} or "\\" in name:
                raise ValueError("unsafe recording artifact name")
            shutil.copyfile(source / name, staging / name)
        (staging / "recording.json").write_text(json.dumps(payload, indent=2) + "\n")
        staging.rename(target)
    return ident


async def seed_recordings(args, settings):
    from replaylab.api.app import create_app
    from replaylab.orchestration.commands import run_once
    selected = ("credits", "fulfillment", "subscriptions") if args.fixture == "all" else (args.fixture,)
    rows = []
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        for fixture in selected:
            incident = sample(fixture).model_dump(mode="json")
            incident["contract"]["approved"] = True
            modes = (args.mode, "flawed") if args.include_flawed and fixture == "credits" else (args.mode,)
            for mode in modes:
                row = await run_once(app, incident, mode)
                if row["state"] not in {"EXPORTED", "PATCH_REJECTED"}:
                    raise RuntimeError(f"recording investigation ended as {row['state']}")
                ident = export_recording(settings, app.state.store, row["id"])
                rows.append({"id": ident, "fixture": fixture, "mode": mode, "url_path": f"/?recording={ident}"})
    print(json.dumps(rows, indent=2))
    return 0
