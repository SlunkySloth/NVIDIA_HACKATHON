"""Identify the immutable observer code and dependencies in a prepared image."""
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path

from replaylab.config import ROOT
from replaylab.schemas import digest

OBSERVER_VERSION = "2"
RUNTIME_FILES = ("__init__.py", "config.py", "schemas.py", "replay/__init__.py", "replay/runner.py", "replay/proxy.py", "replay/service.py", "replay/process.py", "sandboxes/__init__.py", "sandboxes/entrypoint.py", "sandboxes/fingerprint.py")


def fingerprint():
    package = ROOT / "backend/replaylab"
    return {"observer_version": OBSERVER_VERSION, "observer_source_hash": digest({name: digest((package / name).read_text()) for name in RUNTIME_FILES}), "runtime_build_hash": digest((ROOT / "deploy/sandbox.Dockerfile").read_text()), "runtime_lock_hash": digest((ROOT / "requirements.lock").read_text()), "python_version": platform.python_version(), "dependencies": {name: version(name) for name in ("fastapi", "httpx", "pytest", "contree-sdk")}}


def write(path=None):
    target = Path(path) if path else ROOT / "runtime-manifest.json"
    target.write_text(json.dumps(fingerprint(), indent=2) + "\n")


def probe():
    result = fingerprint()
    result["observer_uid"] = os.geteuid()
    result["manifest_matches_files"] = json.loads((ROOT / "runtime-manifest.json").read_text()) == fingerprint()
    return result


if __name__ == "__main__":
    write()
