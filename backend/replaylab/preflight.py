"""Configuration diagnostics and explicit, bounded live provider smoke tests."""
import asyncio
import hashlib
import json
import time
from importlib.metadata import version
from uuid import UUID

import httpx

from replaylab.catalog import original_source, sample
from replaylab.models.nebius import Nemotron
from replaylab.models.policy import Diagnosis, validate_test
from replaylab.orchestration.worker import reference_test
from replaylab.replay.scenarios import scenarios
from replaylab.sandboxes.fingerprint import fingerprint
from replaylab.sandboxes.local import baseline
from replaylab.sandboxes.tokenfactory import TokenFactorySandbox
from replaylab.store import now
from replaylab.verification.oracle import verify


def configuration(settings):
    names = {"NEBIUS_API_KEY": settings.api_key, "NEBIUS_MODEL": settings.model, "CONTREE_API_KEY": settings.sandbox_key, "CONTREE_BASE_URL": settings.sandbox_url, "CONTREE_IMAGE": settings.sandbox_image}
    missing = [name for name, value in names.items() if not value]
    errors = []
    if settings.sandbox_image:
        try:
            UUID(settings.sandbox_image)
        except ValueError:
            errors.append("CONTREE_IMAGE must be an immutable image UUID")
    if version("contree-sdk") != "0.3.6":
        errors.append("install the pinned contree-sdk==0.3.6; newer client APIs differ")
    if settings.run_timeout <= 0 or settings.token_budget <= 0 or settings.max_queued <= 0:
        errors.append("run timeout, token budget, and queue capacity must be positive")
    return {"configured": not missing and not errors, "missing": missing, "errors": errors, "declared_model": settings.model or None, "sandbox_auth": "Nebius IAM project" if settings.project_id else "legacy Sandbox token", "observer": fingerprint(), "inference_verified": False, "sandbox_verified": False}


async def cancellation_check(adapter):
    image = await adapter.sdk.images.use(adapter.image_uuid, strict=True)
    before = len(adapter.operation_ids)
    task = asyncio.create_task(adapter.run(image, "/usr/local/bin/python", args=["-c", "import time; time.sleep(60)"], disposable=True, timeout=45))
    try:
        async with asyncio.timeout(15):
            while len(adapter.operation_ids) == before:
                if task.done():
                    await task
                    raise RuntimeError("cancellation probe finished without a recorded operation")
                await asyncio.sleep(0.1)
        operation = adapter.operation_ids[-1]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        async with asyncio.timeout(15):
            while True:
                observed = await adapter.sdk._api.get_operation_status(UUID(operation))
                status = str(observed.status)
                if status in {"CANCELLED", "SUCCESS", "FAILED"}:
                    if status != "CANCELLED":
                        raise RuntimeError(f"cancellation probe ended as {status}")
                    return {"operation_id": operation, "status": status}
                await asyncio.sleep(0.25)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def doctor(args, settings):
    report = {"schema_version": "1", "checked_at": now(), "live_requested": args.live, **configuration(settings), "checks": []}
    model, sandbox = None, None
    if args.live and report["configured"]:
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
                response = await client.get(settings.inference_url + "/models", headers={"Authorization": f"Bearer {settings.api_key}"})
                if response.status_code != 200:
                    raise RuntimeError(f"model catalog returned HTTP {response.status_code}")
                if len(response.content) > 1000000:
                    raise RuntimeError("model catalog exceeded size limit")
                identifiers = [row["id"] for row in response.json()["data"]]
            report["available_nvidia_models"] = [name for name in identifiers if "nvidia" in name.lower() or "nemotron" in name.lower()]
            if settings.model not in report["available_nvidia_models"]:
                raise RuntimeError("NEBIUS_MODEL must select an accessible NVIDIA model from the account catalog")
            report["checks"].append({"name": "NVIDIA model catalog", "passed": True})
            incident = sample("credits").model_dump(mode="json")
            incident["contract"]["approved"] = True
            model = Nemotron(settings)
            diagnosis = await model.request(Diagnosis, {"task": "Write one straight-line regression function taking client. Deliver the two incident steps with client.post('/webhook', json=event), assert HTTP 200, then assert client.get('/state').json() equals {'customer_01':100}. Return the requested JSON diagnosis.", "incident": incident, "source": original_source("credits")}, max_tokens=2000)
            test = validate_test(diagnosis.regression_test)
            report.update(inference_verified=True, model_calls=model.calls)
            report["checks"].append({"name": "real NVIDIA structured generation", "passed": True})
            sandbox = TokenFactorySandbox(settings)
            report["remote_observer"] = await sandbox.probe()
            scenario = scenarios(incident)[0]
            original = await sandbox.replay(original_source("credits"), "credits", {}, scenario)
            candidate = await sandbox.replay(baseline("credits"), "credits", {}, scenario)
            original_check, candidate_check = verify("credits", {}, scenario, original), verify("credits", {}, scenario, candidate)
            if original_check["inconclusive"] or original_check["passed"] or not candidate_check["passed"]:
                raise RuntimeError("remote original/reference states did not match the expected independent outcomes")
            report["checks"].append({"name": "remote credit reproduction and reference replay", "passed": True, "original": original_check, "candidate": candidate_check})
            red = await sandbox.regression(original_source("credits"), "credits", {}, test)
            green = await sandbox.regression(baseline("credits"), "credits", {}, test)
            if not red["meaningful_failure"] or green["exit_status"] != 0 or green["collected"] < 1 or green["errors"]:
                raise RuntimeError("generated regression did not produce meaningful remote red/green results")
            report["checks"].append({"name": "remote generated regression red/green", "passed": True, "original": red, "candidate": green, "test_source": test})
            # Also exercise restart-aware assertions on the known memory-only defect.
            restart_incident = {**incident, "steps": scenarios(incident)[5]["steps"]}
            restart_test = reference_test(restart_incident)
            restart_red = await sandbox.regression(baseline("credits", True), "credits", {}, restart_test)
            restart_green = await sandbox.regression(baseline("credits"), "credits", {}, restart_test)
            if not restart_red["meaningful_failure"] or restart_green["exit_status"] != 0 or restart_green["errors"]:
                raise RuntimeError("remote restart-aware regression failed its red/green smoke check")
            report["checks"].append({"name": "remote process restart regression", "passed": True})
            image = await sandbox.sdk.images.use(sandbox.image_uuid, strict=True)
            artifact = b"ReplayLab sandbox artifact v1\n"
            artifact_image = await sandbox.run(image, "/usr/local/bin/python", args=["-c", "from pathlib import Path; Path('/tmp/replaylab-smoke.txt').write_bytes(b'ReplayLab sandbox artifact v1\\n')"], disposable=False, timeout=45)
            downloaded = await artifact_image.read("/tmp/replaylab-smoke.txt")
            if downloaded != artifact:
                raise RuntimeError("Sandbox artifact retrieval did not preserve exact bytes")
            report["checks"].append({"name": "artifact retrieval", "passed": True, "image_uuid": str(artifact_image.uuid), "sha256": hashlib.sha256(downloaded).hexdigest()})
            report["checks"].append({"name": "owned operation cancellation", "passed": True, **await cancellation_check(sandbox)})
            report["sandbox_verified"] = True
        except Exception as exc:  # noqa: BLE001 - never log provider URLs, headers, or secret values.
            report["checks"].append({"name": "live provider smoke", "passed": False, "error_type": type(exc).__name__, "message": str(exc)[:300] if isinstance(exc, RuntimeError) else "Provider smoke failed; check account access and the pinned runtime."})
        finally:
            if model:
                report["model_calls"] = model.calls
                await model.close()
            if sandbox:
                report.update(sandbox_operation_ids=sandbox.operation_ids, sandbox_operations=sandbox.operations)
                await sandbox.close()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if (not args.live and not report["errors"]) or (report["inference_verified"] and report["sandbox_verified"]) else 2


async def prepare_sandbox(args, settings):
    started = time.monotonic()
    adapter = TokenFactorySandbox(settings, require_image=False)
    try:
        report = await adapter.prepare(args.base_image)
        report.update(prepared_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        await adapter.close()
