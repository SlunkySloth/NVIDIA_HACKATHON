"""Root observer entrypoint in a credential-free prepared sandbox image."""
import json
import sys

from replaylab.replay.runner import regression, replay
from replaylab.sandboxes.fingerprint import probe


def main():
    payload = json.loads(sys.stdin.read(200000))
    if payload["operation"] == "probe":
        result = probe()
    elif payload["operation"] == "replay":
        result = replay(payload["source"], payload["fixture"], payload["initial"], payload["scenario"], isolated=True)
    elif payload["operation"] == "regression":
        result = regression(payload["source"], payload["fixture"], payload["initial"], payload["test"], isolated=True)
    else:
        raise ValueError("unsupported observer operation")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
