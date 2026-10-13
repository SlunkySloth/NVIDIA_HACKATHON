"""Check source packaging and obvious secret patterns without displaying values."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("README.md", "LICENSE", ".env.example", "requirements.lock", "deploy/app.Dockerfile", "deploy/sandbox.Dockerfile", "deploy/compose.yaml", "docs/nebius-setup.md", "docs/submission.md")
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "API key": re.compile(r"\bsk[-_][A-Za-z0-9_-]{32,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
}


def main():
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True)
    findings = []
    for raw in set(result.stdout.split(b"\0")) - {b""}:
        name = raw.decode()
        path = ROOT / name
        if path.is_file() and path.stat().st_size < 4 * 1024**2:
            try:
                source = path.read_text()
            except UnicodeDecodeError:
                continue
            for label, pattern in PATTERNS.items():
                for match in pattern.finditer(source):
                    findings.append(f"{name}:{source.count(chr(10), 0, match.start()) + 1}: possible {label}")
    for name in missing:
        print(f"Missing release file: {name}")
    for finding in findings:
        print(finding)
    if not missing and not findings:
        print("Release source layout and obvious-secret scan passed")
    return int(bool(missing or findings))


if __name__ == "__main__":
    raise SystemExit(main())
