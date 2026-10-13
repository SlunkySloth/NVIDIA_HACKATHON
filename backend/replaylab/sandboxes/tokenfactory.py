"""Token Factory Sandboxes adapter, pinned to installed contree-sdk 0.3.6.

The SDK's internal operation hook is isolated here because 0.3.6 has no public
operation-ID callback. Its waiter cancels the operation on task cancellation.
"""
import json
from pathlib import Path
from uuid import UUID

from contree_sdk import Contree
from contree_sdk.auth import IAMAuth, JWTAuth
from contree_sdk.config import ContreeConfig

from replaylab.config import ROOT
from replaylab.sandboxes.fingerprint import fingerprint


class TokenFactorySandbox:
    provider = "Token Factory Sandboxes"

    def __init__(self, settings, require_image=True):
        if require_image:
            UUID(settings.sandbox_image)  # Require a resolved checkpoint UUID.
        if not settings.sandbox_key or not settings.sandbox_url:
            raise ValueError("Sandbox access requires CONTREE_API_KEY and CONTREE_BASE_URL")
        project = settings.project_id
        auth = IAMAuth(token=settings.sandbox_key, base_url=settings.sandbox_url, project_id=project) if project else JWTAuth(token=settings.sandbox_key, base_url=settings.sandbox_url)
        config = ContreeConfig(auth=auth, operation_run_timeout=45, default_truncate_output_at=120000)
        self.sdk = Contree(config)
        self.image_uuid = settings.sandbox_image
        self.operation_ids = []
        self.operations = []
        self.validated = False
        start = self.sdk._start_operation

        async def record(request):
            ident = await start(request)
            self.operation_ids.append(str(ident))
            return ident
        self.sdk._start_operation = record

    async def run(self, image, command, **kwargs):
        result = await image.run(command, **kwargs)
        details = result.result
        self.operations.append({"operation_id": self.operation_ids[-1] if self.operation_ids else None, "exit_code": result.exit_code, "elapsed_seconds": details.elapsed_time.total_seconds(), "reported_cost": details.cost, "reported_cost_units": "provider-defined; verify against billing"})
        if result.exit_code != 0:
            raise RuntimeError(f"sandbox observer exited with status {result.exit_code}")
        if details.truncated:
            raise RuntimeError("sandbox observer output was truncated")
        return result

    async def execute(self, payload):
        if payload["operation"] != "probe" and not self.validated:
            await self.probe()
        # Fresh disposable branch from the same prepared clean image, every time.
        image = await self.sdk.images.use(self.image_uuid, strict=True)
        result = await self.run(image, "/usr/local/bin/python", args=["-m", "replaylab.sandboxes.entrypoint"], env={"PYTHONPATH": "/opt/replaylab/backend", "PYTHONDONTWRITEBYTECODE": "1"}, cwd="/opt/replaylab", stdin=json.dumps(payload), timeout=45, disposable=True, truncate_output_at=120000)
        if not isinstance(result.stdout, str) or len(result.stdout) > 120000:
            raise RuntimeError("sandbox output missing or oversized")
        try:
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise RuntimeError("sandbox observer must return an object")  # noqa: TRY004 - invalid provider protocol is a run failure.
            return value
        except json.JSONDecodeError as exc:
            raise RuntimeError("sandbox returned invalid/truncated observer output") from exc

    async def probe(self):
        observed = await self.execute({"operation": "probe"})
        expected = fingerprint()
        for key in ("observer_version", "observer_source_hash", "runtime_build_hash", "runtime_lock_hash"):
            if observed.get(key) != expected[key]:
                raise RuntimeError(f"prepared Sandbox image has mismatched {key}; rebuild it from this checkout")
        if observed.get("observer_uid") != 0 or not observed.get("manifest_matches_files"):
            raise RuntimeError("prepared Sandbox image requires an intact root observer")
        self.validated = True
        return observed

    async def prepare(self, base_image="python:3.12.12-slim"):
        # The input files are trusted application code; no credentials enter the image.
        base = await self.sdk.images.oci(base_image)
        base_uuid = str(base.uuid)
        env = {"PYTHONPATH": "/opt/replaylab/backend", "PYTHONDONTWRITEBYTECODE": "1"}
        paths = [ROOT / "requirements.lock", ROOT / "deploy/sandbox.Dockerfile", *sorted((ROOT / "backend/replaylab").rglob("*.py"))]
        files = {str(Path("/opt/replaylab") / path.relative_to(ROOT)): path for path in paths}
        directories = sorted({str(Path(path).parent) for path in files})
        image = await self.run(base, "/usr/local/bin/python", args=["-c", "import json,sys; from pathlib import Path; [Path(p).mkdir(parents=True, exist_ok=True) for p in json.load(sys.stdin)]"], stdin=json.dumps(directories), disposable=False, timeout=45)
        image = await self.run(image, "/usr/local/bin/python", args=["-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "-r", "/opt/replaylab/requirements.lock"], files=files, env=env, disposable=False, timeout=600, truncate_output_at=120000)
        script = "from replaylab.sandboxes.fingerprint import write; from pathlib import Path; write(); root=Path('/opt/replaylab'); paths=[*root.rglob('*'),root]; [(p.chmod(p.stat().st_mode & ~0o222)) for p in paths]; Path('/tmp').chmod(0o1777)"
        image = await self.run(image, "/usr/local/bin/python", args=["-c", script], env=env, disposable=False, timeout=45)
        self.image_uuid = str(image.uuid)
        UUID(self.image_uuid)
        observed = await self.probe()
        return {"base_image": base_image, "base_image_uuid": base_uuid, "image_uuid": self.image_uuid, "fingerprint": observed, "operation_ids": self.operation_ids, "operations": self.operations}

    async def replay(self, source, fixture, initial, scenario):
        return await self.execute({"operation": "replay", "source": source, "fixture": fixture, "initial": initial, "scenario": scenario})

    async def regression(self, source, fixture, initial, test):
        return await self.execute({"operation": "regression", "source": source, "fixture": fixture, "initial": initial, "test": test})

    async def close(self):
        # SDK 0.3.6 owns a httpx transport on its internal API client.
        transport = getattr(self.sdk._api, "_client", None)
        if transport is not None and hasattr(transport, "aclose"):
            await transport.aclose()
