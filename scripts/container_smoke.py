"""Exercise the actual credential-free root observer image with Docker."""
import argparse
import json
import subprocess
import time
import uuid

from replaylab.catalog import original_source, sample
from replaylab.orchestration.worker import reference_test
from replaylab.replay.scenarios import scenarios
from replaylab.sandboxes.fingerprint import fingerprint
from replaylab.sandboxes.local import baseline
from replaylab.verification.oracle import verify


def execute(image, payload):
    # The trusted observer needs KILL to stop its children after dropping their
    # UID; the non-root application container still has all capabilities dropped.
    command = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m", "--memory", "1g", "--pids-limit", "128", "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "DAC_OVERRIDE", "--cap-add", "KILL", image]
    result = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(f"credential-free observer container exited with status {result.returncode}: {result.stderr[-6000:]}")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="replaylab-sandbox:test")
    parser.add_argument("--app-image", default="replaylab-app:test")
    args = parser.parse_args()
    observed = execute(args.image, {"operation": "probe"})
    assert observed["observer_uid"] == 0 and observed["manifest_matches_files"]
    assert observed["observer_source_hash"] == fingerprint()["observer_source_hash"]
    for fixture in ("credits", "fulfillment", "subscriptions"):
        incident = sample(fixture).model_dump(mode="json")
        scenario = scenarios(incident)[0]
        test = reference_test(incident)
        for label, source in (("original", original_source(fixture)), ("reference", baseline(fixture))):
            replay = execute(args.image, {"operation": "replay", "source": source, "fixture": fixture, "initial": {}, "scenario": scenario})
            checked = verify(fixture, {}, scenario, replay)
            assert not checked["inconclusive"] and checked["passed"] == (label == "reference"), checked
            regression = execute(args.image, {"operation": "regression", "source": source, "fixture": fixture, "initial": {}, "test": test})
            assert (regression["meaningful_failure"] if label == "original" else regression["exit_status"] == 0 and regression["passed"] == 1), regression
        print(f"Container root-observer red/green passed: {fixture}")
    # Prove the production API starts as the unprivileged image user with a
    # read-only filesystem and a writable persistent volume, without any keys.
    name = "replaylab-smoke-" + uuid.uuid4().hex[:12]
    volume = name + "-data"
    subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True)
    try:
        subprocess.run(["docker", "run", "-d", "--name", name, "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--mount", f"type=volume,src={volume},dst=/data", args.app_image], check=True, capture_output=True)
        script = "import json,os,urllib.request; h=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)); assert os.geteuid()==10001 and h['ready'] and not h['live_configured']; print('Application container non-root API readiness passed')"
        for _ in range(30):
            result = subprocess.run(["docker", "exec", name, "python", "-c", script], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(result.stdout.strip())
                break
            time.sleep(1)
        else:
            raise RuntimeError("application container failed API readiness")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True, check=False)


if __name__ == "__main__":
    main()
