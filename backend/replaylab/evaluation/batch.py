"""Bounded evaluations that retain failures and distinguish reference/live runs."""
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime

from replaylab.api.app import create_app
from replaylab.evaluation.cases import DATASET_VERSION, cases
from replaylab.orchestration.commands import run_once
from replaylab.schemas import digest
from replaylab.store import now


def summarize(rows):
    attempted = [r for r in rows if r["state"] != "NOT_ATTEMPTED"]
    defective = [r for r in attempted if r["defective"]]
    clean = [r for r in attempted if not r["defective"]]
    repaired = sum(r["state"] == "EXPORTED" for r in defective)
    reproduced = sum(r["reproduced"] for r in defective)
    changed_clean = sum(r["candidate_present"] for r in clean)
    return {
        "planned": len(rows), "attempted": len(attempted),
        "defective_attempted": len(defective), "original_failures_reproduced": reproduced,
        "verified_fixes": repaired, "verified_fix_rate": repaired / len(defective) if defective else None,
        "clean_attempted": len(clean), "clean_cases_changed": changed_clean,
        "clean_false_repair_rate": changed_clean / len(clean) if clean else None,
        "inconclusive": sum(r["state"] in {"INCONCLUSIVE", "FAILED", "CANCELLED"} for r in attempted),
        "not_attempted": len(rows) - len(attempted),
        "total_model_tokens": sum(r["model_tokens"] for r in attempted) if all(r["model_tokens"] is not None for r in attempted) else None,
        "total_budgeted_tokens": sum(r.get("budgeted_tokens", r["model_tokens"] or 0) for r in attempted),
        "estimated_inference_cost_usd": sum(r["estimated_inference_cost_usd"] for r in attempted) if attempted and all(r["estimated_inference_cost_usd"] is not None for r in attempted) else None,
    }


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


async def evaluate_incidents(args, settings):
    if args.mode == "live" and not settings.live_ready:
        raise ValueError("live evaluation requires configured NVIDIA inference and Token Factory Sandbox access")
    splits = ("development", "holdout") if args.split == "all" else (args.split,)
    planned = [(split, case, repeat) for split in splits for case in cases(split) for repeat in range(1, args.repeats + 1)]
    dataset_hash = digest([{**case, "split": split} for split in splits for case in cases(split)])
    rows = [{"case": case["name"], "split": split, "repeat": repeat, "defective": case["defective"], "state": "NOT_ATTEMPTED", "reason": "not started"} for split, case, repeat in planned]
    report = {"schema_version": "1", "dataset_version": DATASET_VERSION, "dataset_hash": dataset_hash, "kind": "live model repair evaluation" if args.mode == "live" else "human-authored reference repair baseline; no inference", "mode": args.mode, "declared_model": settings.model if args.mode == "live" else None, "started_at": now(), "results": rows, "limitations": ["Original synthetic Python/SQLite incidents only.", "Holdout definitions are public; unseen to this application's model calls until evaluation, not an undisclosed external benchmark.", "Provider smoke tests and reference outcomes do not establish live model repair quality.", "Pricing is an optional inference estimate; sandbox and hosting spend are excluded."]}
    app, started = create_app(settings), time.monotonic()
    max_tokens = args.max_tokens if args.max_tokens is not None else settings.token_budget * len(planned)
    completed, tokens = 0, 0
    async with app.router.lifespan_context(app):
        for index, (split, case, repeat) in enumerate(planned):
            if completed >= args.max_runs or (args.mode == "live" and tokens + settings.token_budget > max_tokens):
                rows[index]["reason"] = "batch run or token budget reached"
                continue
            print(f'Evaluating {split}/{case["name"]}, repeat {repeat}', file=sys.stderr, flush=True)
            row = await run_once(app, case["incident"], args.mode, verbose=False)
            result = row["result"] or {}
            manifest = result.get("manifest", {})
            calls = manifest.get("model_calls", [])
            charged = sum(call.get("budgeted_tokens", call.get("usage", {}).get("total_tokens") or settings.token_budget) for call in calls)
            reported = sum(call["usage"]["total_tokens"] for call in calls) if all("total_tokens" in call.get("usage", {}) for call in calls) else None
            prices = [call.get("estimated_cost_usd") for call in calls]
            events = app.state.store.events(row["id"])
            evidence_time = next((datetime.fromisoformat(e["created"]) - datetime.fromisoformat(row["created"]) for e in events if e["state"] == "REPRODUCED"), None)
            rows[index] = {**rows[index], "state": row["state"], "reason": result.get("explanation", ""), "verdict": result.get("verdict"), "run_id": row["id"], "fixture_revision": case["incident"]["revision"], "reproduced": any(e["state"] == "REPRODUCED" for e in events), "candidate_present": bool(result.get("candidate_source")), "elapsed_seconds": manifest.get("elapsed_seconds"), "time_to_evidence_seconds": evidence_time.total_seconds() if evidence_time else None, "model_ids": manifest.get("model_ids", []), "model_tokens": reported, "budgeted_tokens": charged, "estimated_inference_cost_usd": sum(prices) if all(p is not None for p in prices) else None, "execution_provider": manifest.get("execution_provider"), "sandbox_operation_ids": manifest.get("sandbox_operation_ids", []), "evidence": str(settings.data_dir / "artifacts" / row["id"] / "evidence.zip")}
            evidence = settings.data_dir / "artifacts" / row["id"] / "evidence.zip"
            if evidence.is_file():
                retained = args.output.parent / (args.output.stem + "-evidence") / (row["id"] + ".zip")
                retained.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(evidence, retained)
                rows[index].update(evidence=str(retained), evidence_sha256=hashlib.sha256(retained.read_bytes()).hexdigest())
            completed, tokens = completed + 1, tokens + charged
            report.update(summary=summarize(rows), elapsed_seconds=round(time.monotonic() - started, 3))
            save_report(args.output, report)
    report.update(summary=summarize(rows), finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
    save_report(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    if report["summary"]["not_attempted"] or report["summary"]["inconclusive"]:
        return 2
    return int(any((r["state"] != "EXPORTED" if r["defective"] else r["state"] != "NOT_REPRODUCED") for r in rows))
