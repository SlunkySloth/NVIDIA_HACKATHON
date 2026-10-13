from __future__ import annotations

import asyncio
import difflib
import json
import logging
import platform
import time
import uuid
from importlib.metadata import version

from replaylab.artifacts.bundle import LIMITATIONS, write_bundle
from replaylab.catalog import original_source
from replaylab.config import ROOT
from replaylab.models.nebius import Nemotron
from replaylab.models.policy import (
    Candidate,
    Diagnosis,
    validate_candidate,
    validate_test,
)
from replaylab.release import checkout_info
from replaylab.replay.scenarios import GENERATOR_VERSION, indexed, scenarios
from replaylab.sandboxes.fingerprint import fingerprint
from replaylab.sandboxes.local import LocalReference, baseline
from replaylab.sandboxes.tokenfactory import TokenFactorySandbox
from replaylab.schemas import digest
from replaylab.store import now
from replaylab.verification.oracle import expected_states, verify

logger = logging.getLogger(__name__)


def reference_test(incident):
    # Authored deterministically from the approved input; visibly labeled reference.
    want = expected_states(incident["fixture_id"], incident["initial_state"], incident["steps"])[-1]
    lines = ["def test_reported_incident(client):"]
    for step in incident["steps"]:
        if step["kind"] == "restart":
            lines.append("    response = client.post('/__replay/restart')")
        else:
            lines.append(f"    response = client.post('/webhook', json={step!r})")
        lines.append("    assert response.status_code == 200")
    lines.append(f"    assert client.get('/state').json() == {want!r}")
    return "\n".join(lines) + "\n"


class Worker:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.task = None
        self.active_task = None
        self.active_id = None
        self.wake = asyncio.Event()

    async def start(self):
        self.store.recover()
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    def cancel(self, ident):
        if self.active_id == ident and self.active_task:
            self.active_task.cancel()
        self.wake.set()

    async def loop(self):
        while True:
            row = self.store.claim(str(uuid.uuid4()))
            if row:
                self.active_id = row["id"]
                self.active_task = asyncio.create_task(self.investigate(row))
                try:
                    await self.active_task
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                self.active_task = None
                self.active_id = None
            else:
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), 0.5)
                except TimeoutError:
                    pass

    async def investigate(self, row):
        ident = row["id"]
        adapter, model = None, None
        started = time.monotonic()
        incident = json.loads(row["input_bundle"])
        fixture, initial = incident["fixture_id"], incident["initial_state"]
        result = {"mode": row["mode"], "original_source": original_source(fixture, incident["revision"]), "candidate_source": "", "diff": "", "test_source": "", "scenarios": scenarios(incident), "original_results": [], "candidate_results": [], "attempts": [], "regression": {}, "limitations": LIMITATIONS, "explanation": "", "verdict": "Inconclusive"}
        revision, dirty = await asyncio.to_thread(checkout_info)
        manifest = {"schema_version": "1", "run_id": ident, "started_at": now(), "repository_revision": revision, "fixture_revision": incident["revision"], "input_hash": digest(incident), "contract_hash": digest(incident["contract"]), "initial_state_hash": incident["initial_state_hash"], "prompt_version": "2", "scenario_generator_version": GENERATOR_VERSION, "mode": row["mode"], "python_version": platform.python_version(), "dependencies": {p: version(p) for p in ("fastapi", "httpx", "pytest", "contree-sdk")}, "runtime_build_hash": digest((ROOT / "deploy/sandbox.Dockerfile").read_text()), "runtime_lock_hash": digest((ROOT / "requirements.lock").read_text()), "application_source_hash": digest({str(p.relative_to(ROOT)): digest(p.read_text()) for p in sorted((ROOT / "backend/replaylab").rglob("*.py"))})}
        result["manifest"] = manifest
        manifest["observer_source_hash"] = fingerprint()["observer_source_hash"]
        manifest["working_tree_dirty"] = dirty
        def change(state, message):
            self.store.transition(ident, state, message, result)

        def finish(state, verdict, explanation):
            result["verdict"], result["explanation"] = verdict, explanation
            manifest.update({"finished_at": now(), "elapsed_seconds": round(time.monotonic() - started, 3), "execution_provider": adapter.provider if adapter else None, "sandbox_operation_ids": adapter.operation_ids if adapter else [], "sandbox_operations": adapter.operations if isinstance(adapter, TokenFactorySandbox) else [], "image_uuid": self.settings.sandbox_image if row["mode"] == "live" else None, "model_calls": model.calls if model else [], "model_ids": sorted({call["model"] for call in model.calls}) if model else [], "candidate_hash": digest(result["candidate_source"]), "test_hash": digest(result["test_source"]), "verdict": verdict})
            result["artifacts"] = write_bundle(self.settings.data_dir, ident, incident, result)
            self.store.transition(ident, state, explanation, result)

        try:
            async with asyncio.timeout(self.settings.run_timeout):
                change("INPUT_VALIDATED", "Input hashes and supported fixture revision validated")
                if not incident["contract"]["approved"]:
                    finish("NEEDS_CLARIFICATION", "Needs clarification", "Approve the behavior contract before investigating.")
                    return
                change("CONTRACT_READY", "Using your reviewed business contract")
                if row["mode"] == "live":
                    if not self.settings.live_ready:
                        raise RuntimeError("live mode requires configured Nemotron inference and Token Factory Sandboxes")
                    adapter, model = TokenFactorySandbox(self.settings), Nemotron(self.settings)
                else:
                    adapter = LocalReference(fixture)
                change("ENVIRONMENT_READY", f"Prepared {adapter.provider}")
                change("REPRODUCING", "Delivering the incident against a clean original service")
                incident_scenario = result["scenarios"][0]
                observed = await adapter.replay(result["original_source"], fixture, initial, incident_scenario)
                checked = verify(fixture, initial, incident_scenario, observed)
                result["original_results"].append({**observed, "check": checked})
                if checked["inconclusive"]:
                    raise RuntimeError("original replay could not complete: " + str(checked["failures"]))
                if checked["passed"]:
                    finish("NOT_REPRODUCED", "Not reproduced", "The original input does not violate the reviewed contract; no patch was requested.")
                    return
                change("REPRODUCED", "Original business-state violation reproduced")
                result["counterexample"] = await self.minimize(adapter, result["original_source"], fixture, initial, incident_scenario)
                for scenario in result["scenarios"][1:]:
                    observed = await adapter.replay(result["original_source"], fixture, initial, scenario)
                    result["original_results"].append({**observed, "check": verify(fixture, initial, scenario, observed)})
                if model:
                    context = {"task": "Diagnose this observed failure and write one regression test function taking only client (httpx.Client). Use straight-line client.post('/webhook', json=event), client.post('/__replay/restart') for each restart step, and client.get('/state').json() with assignments and assertions; no imports, decorators, loops, helpers or arbitrary calls. Keep all assertions about the incident's intended behavior.", "incident": incident, "files": {"handler.py": result["original_source"]}, "observations": result["original_results"][0], "counterexample": result["counterexample"]}
                    diagnosis = await self.diagnose(model, adapter, context, result, fixture, initial)
                    result["diagnosis"] = diagnosis.explanation
                else:
                    result["test_source"] = reference_test(incident)
                    result["diagnosis"] = "Human-authored comparison: duplicate deliveries or stale entity versions change state incorrectly. This mode makes no model calls."
                    result["regression"]["original"] = await adapter.regression(result["original_source"], fixture, initial, result["test_source"])
                if not result["regression"]["original"]["meaningful_failure"]:
                    raise RuntimeError("regression did not fail on an assertion against the original; no candidate can be verified")
                change("PATCHING", "Regression is red on original code; preparing a separate candidate")
                feedback = None
                for attempt in range(2 if model else 1):
                    if model:
                        candidate = await model.request(Candidate, {"task": "Return a minimal complete replacement for handler.py. Only this path is editable. Persist event identity in the existing processed table; use a transaction for coupled local writes. Subscription updates must follow strictly increasing entity versions.", "incident": incident, "source": result["original_source"], "diagnosis": result["diagnosis"], "regression_test": result["test_source"], "counterexample": feedback})
                        result["candidate_source"] = validate_candidate(candidate)
                        result["patch_explanation"] = candidate.explanation
                    else:
                        result["candidate_source"] = baseline(fixture, row["mode"] == "flawed")
                        result["patch_explanation"] = "Pre-authored flawed comparison" if row["mode"] == "flawed" else "Human-authored persistent reference patch"
                    result["diff"] = "".join(difflib.unified_diff(result["original_source"].splitlines(True), result["candidate_source"].splitlines(True), fromfile="a/handler.py", tofile="b/handler.py"))
                    change("VERIFYING", f"Challenging candidate {attempt + 1}: duplicates, legitimate events, entities, restarts, and final checks")
                    candidate_regression = await adapter.regression(result["candidate_source"], fixture, initial, result["test_source"])
                    result["regression"]["candidate"] = candidate_regression
                    if candidate_regression["collected"] == 0 or candidate_regression["errors"] or candidate_regression["exit_status"] not in {0, 1}:
                        raise RuntimeError("candidate regression could not complete; verdict is inconclusive")
                    result["candidate_results"] = []
                    for scenario in result["scenarios"]:
                        observed = await adapter.replay(result["candidate_source"], fixture, initial, scenario)
                        result["candidate_results"].append({**observed, "check": verify(fixture, initial, scenario, observed)})
                    passed = candidate_regression["collected"] > 0 and candidate_regression["exit_status"] == 0 and candidate_regression["passed"] == candidate_regression["collected"] and all(r["check"]["passed"] for r in result["candidate_results"])
                    result["attempts"].append({"attempt": attempt + 1, "source": result["candidate_source"], "source_hash": digest(result["candidate_source"]), "regression": candidate_regression, "results": result["candidate_results"], "passed": passed})
                    if passed:
                        finish("EXPORTED", "Verified for tested scenarios", "The original failed; this candidate passes the regression and all independent scenarios. Review the evidence and stated limitations before applying it.")
                        return
                    if any(r["check"]["inconclusive"] for r in result["candidate_results"]):
                        raise RuntimeError("candidate replay infrastructure failed; verdict is inconclusive")
                    # Final held-back failures are never fed back to the author.
                    visible = [r for r in result["candidate_results"] if not next(s for s in result["scenarios"] if s["id"] == r["scenario_id"])["held_back"] and not r["check"]["passed"]]
                    if not visible:
                        break
                    failed = visible[0]
                    scenario = next(s for s in result["scenarios"] if s["id"] == failed["scenario_id"])
                    feedback = await self.minimize(adapter, result["candidate_source"], fixture, initial, scenario)
                    result["rejection_counterexample"] = feedback
                    if model and attempt == 0:
                        change("PATCHING", "Candidate rejected; returning a bounded counterexample for one revision")
                finish("PATCH_REJECTED", "Patch rejected", "The candidate failed independent checks. Inspect the counterexample; no patch is labeled verified.")
        except asyncio.CancelledError:
            change("CANCELLED", "Investigation cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - persist a terminal verdict for any investigation error.
            # Never expose provider transport URLs, credentials or raw headers.
            message = str(exc)[:500] if isinstance(exc, (RuntimeError, ValueError, TimeoutError)) else type(exc).__name__
            finish("INCONCLUSIVE", "Inconclusive", message or "Investigation timed out")
            logger.info("Run %s ended inconclusively (%s)", ident, type(exc).__name__)
        finally:
            if model:
                await model.close()
            if adapter:
                await adapter.close()

    async def diagnose(self, model, adapter, context, result, fixture, initial):
        for repair in range(2):
            try:
                diagnosis = await model.request(Diagnosis, context)
                result["test_source"] = validate_test(diagnosis.regression_test)
                red = await adapter.regression(result["original_source"], fixture, initial, result["test_source"])
                result["regression"]["original"] = red
                if not red["meaningful_failure"]:
                    raise ValueError("regression must produce an assertion failure, with nonzero collection and zero collection errors")
                return diagnosis
            except ValueError as exc:
                if repair:
                    raise
                context = {**context, "repair": str(exc)[:400], "test_observation": result["regression"].get("original")}
        raise RuntimeError("diagnosis exhausted bounded repair")

    async def minimize(self, adapter, source, fixture, initial, scenario):
        steps = list(scenario["steps"])
        attempts, index = 0, 0
        while index < len(steps) and attempts < 40:
            reduced = steps[:index] + steps[index + 1:]
            if not any(s["kind"] == "delivery" for s in reduced):
                index += 1
                continue
            trial = {**scenario, "steps": indexed(reduced)}
            observed = await adapter.replay(source, fixture, initial, trial)
            checked = verify(fixture, initial, trial, observed)
            attempts += 1
            if not checked["passed"] and not checked["inconclusive"]:
                steps = reduced
                index = 0
            else:
                index += 1
        minimized = {**scenario, "steps": indexed(steps)}
        return {"original_length": len(scenario["steps"]), "length": len(steps), "attempts": attempts, "locally_minimal": index >= len(steps), "scenario": minimized}
