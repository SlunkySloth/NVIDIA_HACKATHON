"""Trusted observer controlling unprivileged service processes via HTTP.

Local use is restricted to human-authored fixtures/references. Remote mode drops
candidate privileges before launch. Reports are constructed by this observer.
"""
from __future__ import annotations

import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from replaylab.replay.proxy import RegressionProxy
from replaylab.schemas import digest

MAX_OUTPUT = 65536


def initialize(path, fixture, initial):
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE balances(entity TEXT PRIMARY KEY, value INTEGER NOT NULL); CREATE TABLE processed(event_id TEXT PRIMARY KEY); CREATE TABLE subscriptions(entity TEXT PRIMARY KEY, status TEXT NOT NULL, version INTEGER NOT NULL);")
        if fixture == "subscriptions":
            db.executemany("INSERT INTO subscriptions VALUES(?,?,?)", [(e, s["status"], s["version"]) for e, s in initial.items()])
        else:
            db.executemany("INSERT INTO balances VALUES(?,?)", initial.items())


def observe(path, fixture):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as db:
        if fixture == "subscriptions":
            return {e: {"status": s, "version": v} for e, s, v in db.execute("SELECT entity,status,version FROM subscriptions ORDER BY entity")}
        return dict(db.execute("SELECT entity,value FROM balances ORDER BY entity"))


class Service:
    def __init__(self, source, fixture, initial, isolated=False, cancel_event=None):
        self.temp = tempfile.TemporaryDirectory(prefix="replaylab-service-")
        self.path = Path(self.temp.name)
        self.db = self.path / "ledger.sqlite"
        self.log = self.path / "service.log"
        self.fixture = fixture
        self.isolated = isolated
        self.cancel_event = cancel_event
        self.process = None
        (self.path / "handler.py").write_text(source)
        initialize(self.db, fixture, initial)
        self.path.chmod(0o700)
        if isolated:
            if os.geteuid() != 0:
                raise RuntimeError("sandbox observer must start as root to separate candidate privileges")
            os.chown(self.path, 65534, 65534)
            for p in self.path.iterdir():
                os.chown(p, 65534, 65534)
        try:
            self.start()
        except BaseException:
            self.close()
            raise

    def start(self):
        self.check_cancelled()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(Path(__file__).resolve().parents[2]), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "REPLAYLAB_DB": str(self.db), "REPLAYLAB_HANDLER": str(self.path / "handler.py"), "REPLAYLAB_FIXTURE": self.fixture}
        kwargs = {"user": 65534, "group": 65534, "extra_groups": []} if self.isolated else {}
        self.log_file = self.log.open("ab")
        self.process = subprocess.Popen([sys.executable, "-m", "replaylab.replay.process", "-m", "uvicorn", "replaylab.replay.service:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"], cwd=self.path, env=env, stdout=self.log_file, stderr=self.log_file, start_new_session=True, **kwargs)
        deadline = time.monotonic() + 6
        with httpx.Client(timeout=0.4, trust_env=False) as client:
            while time.monotonic() < deadline:
                self.check_cancelled()
                if self.process.poll() is not None:
                    raise RuntimeError("service exited before becoming ready")
                try:
                    if client.get(self.url + "/health").status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.025)
        self.stop()
        raise TimeoutError("service readiness timed out")

    def check_cancelled(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise RuntimeError("local execution cancelled")

    def stop(self):
        if self.process:
            # Kill the whole process group, including any candidate children.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=3)
            self.log_file.close()
            self.process = None

    def close(self):
        self.stop()
        self.temp.cleanup()


def replay(source, fixture, initial, scenario, isolated=False, cancel_event=None):
    result = {"scenario_id": scenario["id"], "seed": 0, "initial_state_hash": digest(initial), "steps": [], "exit_status": None, "infrastructure_error": None}
    service = None
    try:
        service = Service(source, fixture, initial, isolated, cancel_event)
        with httpx.Client(timeout=3, trust_env=False) as client:
            for i, step in enumerate(scenario["steps"]):
                service.check_cancelled()
                status, body = None, None
                if step["kind"] == "restart":
                    service.stop()
                    service.start()
                else:
                    response = client.post(service.url + "/webhook", json=step)
                    status, body = response.status_code, response.text[:2048]
                result["steps"].append({"sequence": i, "kind": step["kind"], "event_id": step.get("event_id"), "entity_id": step.get("entity_id"), "status": status, "response": body, "state": observe(service.db, fixture)})
        result["final_state_digest"] = digest(result["steps"][-1]["state"] if result["steps"] else initial)
        result["exit_status"] = service.process.poll()
        if result["exit_status"] is not None:
            result["infrastructure_error"] = "service exited during replay"
    except Exception as exc:  # noqa: BLE001 - report execution errors as inconclusive evidence.
        result["infrastructure_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    finally:
        if service:
            service.close()
    return result


def regression(source, fixture, initial, test_source, isolated=False, cancel_event=None):
    service, proxy = None, None
    result = {"collected": 0, "passed": 0, "failures": 0, "errors": 0, "exit_status": None, "output": "", "meaningful_failure": False}
    try:
        service = Service(source, fixture, initial, isolated, cancel_event)
        proxy = RegressionProxy(service)
        (service.path / "test_regression.py").write_text(test_source)
        (service.path / "conftest.py").write_text('import os\nimport httpx\nimport pytest\n@pytest.fixture\ndef client():\n    with httpx.Client(base_url=os.environ["REPLAYLAB_URL"], timeout=8, trust_env=False) as c:\n        yield c\n')
        if isolated:
            for name in ("test_regression.py", "conftest.py"):
                os.chown(service.path / name, 65534, 65534)
        kwargs = {"user": 65534, "group": 65534, "extra_groups": []} if isolated else {}
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(Path(__file__).resolve().parents[2]), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1", "REPLAYLAB_URL": proxy.url}
        with (service.path / "test.log").open("wb") as log:
            proc = subprocess.Popen([sys.executable, "-m", "replaylab.replay.process", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=report.xml", "test_regression.py"], cwd=service.path, env=env, stdout=log, stderr=log, start_new_session=True, **kwargs)
            try:
                deadline = time.monotonic() + 30
                while proc.poll() is None:
                    service.check_cancelled()
                    if time.monotonic() >= deadline:
                        raise TimeoutError("regression timed out")
                    time.sleep(0.05)
                result["exit_status"] = proc.returncode
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=3)
        result["output"] = (service.path / "test.log").read_text(errors="replace")[:MAX_OUTPUT]
        report = service.path / "report.xml"
        if report.exists() and report.stat().st_size < MAX_OUTPUT:
            root = ET.parse(report).getroot()
            cases = root.findall(".//testcase")
            result["collected"] = len(cases)
            result["failures"] = len(root.findall(".//failure"))
            result["errors"] = len(root.findall(".//error"))
            result["passed"] = sum(not list(c) for c in cases)
            result["meaningful_failure"] = result["exit_status"] == 1 and result["failures"] > 0 and result["errors"] == 0 and all("AssertionError" in f.get("message", "") or "assert " in (f.text or "") for f in root.findall(".//failure"))
        if proxy.error:
            result["errors"] += 1
            result["meaningful_failure"] = False
            result["output"] += f"\nObserver proxy failed: {proxy.error}"
    except Exception as exc:  # noqa: BLE001 - collection and execution errors must remain inconclusive.
        result["errors"] += 1
        result["output"] += f"\n{type(exc).__name__}: {str(exc)[:300]}"
    finally:
        if proxy:
            proxy.close()
        if service:
            service.close()
    return result
