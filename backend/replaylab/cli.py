"""Local development commands and credential-free evidence reproduction."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from replaylab.artifacts.bundle import read_bundle
from replaylab.catalog import TITLES, contract_for, original_source, sample
from replaylab.config import Settings
from replaylab.models.policy import validate_test
from replaylab.replay.scenarios import (
    GENERATOR_VERSION,
    SUPPORTED_GENERATORS,
    scenarios,
)
from replaylab.sandboxes.local import FLAWS, LocalReference, baseline
from replaylab.schemas import IncidentBundle, digest
from replaylab.verification.oracle import verify


async def investigate(args):
    settings = Settings()
    if args.data_dir:
        settings.data_dir = args.data_dir.resolve()
    if args.mode == "live" and not settings.live_ready:
        raise ValueError("live mode requires NEBIUS_API_KEY, NEBIUS_MODEL, CONTREE_API_KEY, CONTREE_BASE_URL and CONTREE_IMAGE")
    if args.incident:
        if args.incident.stat().st_size > 131072:
            raise ValueError("incident exceeds 128 KiB")
        incident = json.loads(args.incident.read_text())
    else:
        incident = sample(args.fixture).model_dump(mode="json")
        incident["contract"]["approved"] = True
    # Use the API worker so the same lease and durable queue rules apply.
    from replaylab.api.app import create_app
    from replaylab.orchestration.commands import run_once
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        row = await run_once(app, incident, args.mode)
    ident = row["id"]
    result = row["result"] or {}
    summary = {"run_id": ident, "state": row["state"], "verdict": result.get("verdict"), "explanation": result.get("explanation"), "evidence": str(settings.data_dir / "artifacts" / ident / "evidence.zip")}
    print(json.dumps(summary, indent=2))
    return 0 if row["state"] in {"EXPORTED", "NOT_REPRODUCED"} else 1 if row["state"] == "PATCH_REJECTED" else 2


async def reproduce(args):
    files = read_bundle(args.bundle)
    incident = IncidentBundle.model_validate_json(files["incident.redacted.json"]).model_dump(mode="json")
    manifest = json.loads(files["run-manifest.json"])
    fixture = incident["fixture_id"]
    original, candidate = files["original_handler.py"], files["candidate_handler.py"]
    if original != original_source(fixture, incident["revision"]):
        raise ValueError("unsupported original revision; use the recorded ReplayLab checkout")
    generator_version = manifest["scenario_generator_version"]
    if generator_version not in SUPPORTED_GENERATORS:
        raise ValueError("unsupported scenario generator; use the recorded ReplayLab checkout")
    if manifest["input_hash"] != digest(incident) or manifest["contract_hash"] != digest(incident["contract"]):
        raise ValueError("incident or contract does not match the manifest")
    generated_scenarios = scenarios(incident, version=generator_version)
    if json.loads(files["scenarios.json"]) != generated_scenarios:
        raise ValueError("scenarios do not match the supported incident generator")
    if not incident["contract"]["approved"]:
        raise ValueError("bundle requires a reviewed behavior contract")
    if incident["contract"] != contract_for(fixture, approved=True).model_dump(mode="json") or json.loads(files["contract.json"]) != incident["contract"]:
        raise ValueError("bundle requires the published behavior contract in both replay inputs")
    if args.provider == "tokenfactory":
        settings = Settings()
        if not all((settings.sandbox_key, settings.sandbox_url, settings.sandbox_image)):
            raise ValueError("remote reproduction requires CONTREE_API_KEY, CONTREE_BASE_URL and CONTREE_IMAGE")
        if settings.sandbox_image != manifest.get("image_uuid"):
            raise ValueError("CONTREE_IMAGE must match the immutable image UUID in the recorded manifest")
        from replaylab.sandboxes.tokenfactory import TokenFactorySandbox
        adapter = TokenFactorySandbox(settings)
    else:
        adapter = LocalReference(fixture)
        if candidate and candidate not in adapter.allowed_sources:
            raise ValueError("local reproduction refuses unknown candidate source; use --provider tokenfactory")
    results, regression = [], {}
    try:
        for scenario in generated_scenarios:
            row = {"scenario_id": scenario["id"]}
            for label, source in (("original", original), ("candidate", candidate)):
                if source:
                    observed = await adapter.replay(source, fixture, incident["initial_state"], scenario)
                    row[label] = verify(fixture, incident["initial_state"], scenario, observed)
            results.append(row)
        if candidate:
            test = validate_test(files["generated_regression_test.py"])
            for label, source in (("original", original), ("candidate", candidate)):
                regression[label] = await adapter.regression(source, fixture, incident["initial_state"], test)
    finally:
        await adapter.close()
    if any(check["inconclusive"] for row in results for check in (row.get("original"), row.get("candidate")) if check):
        verdict, code = "Inconclusive", 2
    elif results[0]["original"]["passed"]:
        verdict, code = "Not reproduced", 0
    elif not candidate or not regression["original"]["meaningful_failure"] or regression["candidate"]["errors"] or regression["candidate"]["exit_status"] not in {0, 1}:
        verdict, code = "Inconclusive", 2
    elif all(row["candidate"]["passed"] for row in results) and regression["candidate"]["exit_status"] == 0 and regression["candidate"]["collected"] > 0 and regression["candidate"]["passed"] == regression["candidate"]["collected"]:
        verdict, code = "Verified for tested scenarios", 0
    else:
        verdict, code = "Patch rejected", 1
    print(json.dumps({"verdict": verdict, "provider": adapter.provider, "scenarios": results, "regression": regression}, indent=2))
    return code


async def evaluate(args):
    """Measure authored baselines; these cases are development checks, not holdout."""
    started = time.monotonic()
    rows = []
    fixtures = TITLES if args.fixture == "all" else [args.fixture]
    for fixture in fixtures:
        incident = sample(fixture).model_dump(mode="json")
        sources = {"original": original_source(fixture), "reference": baseline(fixture)}
        flaws = FLAWS if args.all_flaws else ("memory",)
        sources.update({f"flawed_{flaw}": baseline(fixture, True, flaw) for flaw in flaws})
        # All subscription flawed variants resolve to the same stale-version patch.
        if fixture == "subscriptions":
            sources = {"original": sources["original"], "reference": sources["reference"], "flawed_stale_version": baseline(fixture, True)}
        adapter = LocalReference(fixture)
        try:
            for label, source in sources.items():
                for scenario in scenarios(incident):
                    repeats = []
                    for _ in range(args.repeats):
                        observed = await adapter.replay(source, fixture, incident["initial_state"], scenario)
                        repeats.append({"trace_hash": digest([{k: step.get(k) for k in ("sequence", "kind", "event_id", "entity_id", "status", "state")} for step in observed["steps"]]), "check": verify(fixture, incident["initial_state"], scenario, observed)})
                    rows.append({"fixture": fixture, "source": label, "scenario": scenario["id"], "repeats": repeats, "deterministic": len({r["trace_hash"] for r in repeats}) == 1})
                print(f"Evaluated {fixture}/{label}", file=sys.stderr, flush=True)
        finally:
            await adapter.close()
    infrastructure = sum(any(r["check"]["inconclusive"] for r in row["repeats"]) for row in rows)
    reference_failures = sum(row["source"] == "reference" and any(not r["check"]["passed"] for r in row["repeats"]) for row in rows)
    groups = {(row["fixture"], row["source"]) for row in rows if row["source"] != "reference"}
    missed = [f"{fixture}/{label}" for fixture, label in sorted(groups) if all(r["check"]["passed"] for row in rows if (row["fixture"], row["source"]) == (fixture, label) for r in row["repeats"])]
    report = {"kind": "authored synthetic development baselines; no model repair measured", "scenario_generator_version": GENERATOR_VERSION, "repeats": args.repeats, "elapsed_seconds": round(time.monotonic() - started, 3), "scenario_source_pairs": len(rows), "inconclusive_pairs": infrastructure, "reference_failures": reference_failures, "unrejected_defective_sources": missed, "nondeterministic_pairs": sum(not row["deterministic"] for row in rows), "results": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    return int(bool(infrastructure or reference_failures or missed or report["nondeterministic_pairs"]))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="replaylab", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="serve the API and built web UI with one worker")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    export = commands.add_parser("sample", help="print a compatible incident JSON bundle")
    export.add_argument("fixture", choices=TITLES)
    run = commands.add_parser("investigate", help="investigate a curated incident using the application worker")
    run.add_argument("fixture", choices=TITLES, default="credits", nargs="?")
    run.add_argument("--mode", choices=("reference", "flawed", "live"), default="reference")
    run.add_argument("--data-dir", type=Path)
    run.add_argument("--incident", type=Path, help="reviewed compatible incident JSON, including vetted variants")
    replay = commands.add_parser("reproduce", help="rerun exported code and tests without generating a patch")
    replay.add_argument("bundle", type=Path)
    replay.add_argument("--provider", choices=("local", "tokenfactory"), default="local")
    bench = commands.add_parser("evaluate", help="evaluate authored synthetic baselines against the independent observer")
    bench.add_argument("--fixture", choices=("all", *TITLES), default="all")
    bench.add_argument("--repeats", type=int, choices=range(1, 11), default=1)
    bench.add_argument("--all-flaws", action="store_true")
    bench.add_argument("--output", type=Path)
    incident_bench = commands.add_parser("evaluate-incidents", help="evaluate frozen incident variants and clean controls; retain every outcome")
    incident_bench.add_argument("--split", choices=("development", "holdout", "all"), default="holdout")
    incident_bench.add_argument("--mode", choices=("reference", "live"), default="reference")
    incident_bench.add_argument("--repeats", type=int, choices=range(1, 4), default=1)
    incident_bench.add_argument("--max-runs", type=int, choices=range(1, 37), default=12)
    incident_bench.add_argument("--max-tokens", type=int)
    incident_bench.add_argument("--output", type=Path, required=True)
    incident_bench.add_argument("--data-dir", type=Path)
    diagnostic = commands.add_parser("doctor", help="check configuration without exposing keys; --live performs real bounded provider tests")
    diagnostic.add_argument("--live", action="store_true")
    diagnostic.add_argument("--output", type=Path)
    preparation = commands.add_parser("prepare-sandbox", help="prepare an immutable remote observer image; requires configured Sandbox access")
    preparation.add_argument("--base-image", default="python:3.12.12-slim")
    preparation.add_argument("--output", type=Path, required=True)
    recording = commands.add_parser("export-recording", help="make a curated synthetic completed run available for read-only public inspection")
    recording.add_argument("run_id")
    recording.add_argument("--data-dir", type=Path)
    seed = commands.add_parser("seed-recordings", help="execute real curated investigations and save labeled recordings")
    seed.add_argument("--fixture", choices=("all", *TITLES), default="credits")
    seed.add_argument("--mode", choices=("reference", "live"), default="reference")
    seed.add_argument("--include-flawed", action="store_true")
    seed.add_argument("--data-dir", type=Path)
    snapshot = commands.add_parser("backup", help="snapshot metadata and evidence into a private ZIP; never overwrite an existing backup")
    snapshot.add_argument("--output", type=Path, required=True)
    snapshot.add_argument("--data-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            print(sample(args.fixture).model_dump_json(indent=2))
            return 0
        if args.command == "serve":
            import uvicorn
            uvicorn.run("replaylab.api.app:create_app", factory=True, host=args.host, port=args.port, workers=1)
            return 0
        if args.command == "evaluate-incidents":
            from replaylab.evaluation.batch import evaluate_incidents
            settings = Settings()
            if args.data_dir:
                settings.data_dir = args.data_dir.resolve()
            return asyncio.run(evaluate_incidents(args, settings))
        if args.command in {"doctor", "prepare-sandbox"}:
            from replaylab.preflight import doctor, prepare_sandbox
            return asyncio.run((doctor if args.command == "doctor" else prepare_sandbox)(args, Settings()))
        if args.command in {"export-recording", "seed-recordings"}:
            from replaylab.recordings import export_recording, seed_recordings
            from replaylab.store import Store
            settings = Settings()
            if args.data_dir:
                settings.data_dir = args.data_dir.resolve()
            if args.command == "seed-recordings":
                return asyncio.run(seed_recordings(args, settings))
            ident = export_recording(settings, Store(settings.data_dir), args.run_id)
            print(json.dumps({"id": ident, "url_path": f"/?recording={ident}"}, indent=2))
            return 0
        if args.command == "backup":
            from replaylab.backup import backup
            settings = Settings()
            if args.data_dir:
                settings.data_dir = args.data_dir.resolve()
            return backup(settings, args.output)
        return asyncio.run({"investigate": investigate, "reproduce": reproduce, "evaluate": evaluate}[args.command](args))
    except KeyboardInterrupt:
        return 130
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        print(f"replaylab: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
