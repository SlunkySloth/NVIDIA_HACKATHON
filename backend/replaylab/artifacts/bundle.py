import json
import zipfile
from pathlib import Path

from replaylab.schemas import digest

LIMITATIONS = ["Synthetic Python/FastAPI/SQLite fixtures only.", "Serial deliveries and process restarts; concurrent workers and external side effects are untested.", "Contract checks establish tested behavior, not universal or production safety.", "Local reference mode uses a human-authored patch and test, with no inference or cloud execution."]


def write_bundle(directory: Path, run_id, incident, result):
    target = directory / "artifacts" / run_id
    target.mkdir(parents=True, exist_ok=True)
    manifest = result["manifest"]
    files = {
        "incident.redacted.json": incident,
        "contract.json": incident["contract"],
        "scenarios.json": result.get("scenarios", []),
        "original-results.json": result.get("original_results", []),
        "candidate-results.json": result.get("candidate_results", []),
        "regression-results.json": result.get("regression", {}),
        "attempts.json": result.get("attempts", []),
        "counterexample.json": result.get("counterexample", {}),
        "rejection-counterexample.json": result.get("rejection_counterexample", {}),
        "original_handler.py": result.get("original_source", ""),
        "candidate_handler.py": result.get("candidate_source", ""),
        "candidate.patch": result.get("diff", ""),
        "generated_regression_test.py": result.get("test_source", ""),
        "verification-summary.md": f'# ReplayLab verification\n\n{result["verdict"]}\n\n{result["explanation"]}\n\n' + "\n".join(f"- {line}" for line in LIMITATIONS) + "\n",
        "replay-instructions.md": '''# Reproduce this evidence

Install from the exact ReplayLab revision recorded in run-manifest.json, using
requirements.lock and the documented runtime build. The bundle includes the
exact original and candidate source; generating a new patch is unnecessary.

If working_tree_dirty is true, the recorded commit alone does not contain the
executed implementation. Use the matching working checkout identified by
application_source_hash. Publish and tag a clean checkout before sharing a
release as reproducible from Git history.

For a human-authored local reference bundle:

    python -m replaylab.cli reproduce evidence.zip

For a generated candidate (requires configured remote sandbox access):

    python -m replaylab.cli reproduce evidence.zip --provider tokenfactory

The local command refuses unknown source and never runs arbitrary exported code.
Live generation is separate: start the app, approve the contract, and select Run live.
An eight-minute run limit and a two-candidate limit apply.
''',
    }
    encoded = {name: json.dumps(value, indent=2, sort_keys=True) if not isinstance(value, str) else value for name, value in files.items()}
    manifest["artifact_hashes"] = {name: digest(value) for name, value in encoded.items()}
    encoded["run-manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True)
    for name, content in encoded.items():
        (target / name).write_text(content)
    with zipfile.ZipFile(target / "evidence.zip", "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in encoded.items():
            bundle.writestr(name, content)
    return [{"name": name, "size": (target / name).stat().st_size, "sha256": digest(content)} for name, content in encoded.items()] + [{"name": "evidence.zip", "size": (target / "evidence.zip").stat().st_size}]


def read_bundle(path):
    try:
        return _read_bundle(path)
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise ValueError("invalid evidence archive or manifest") from exc


def _read_bundle(path):
    with zipfile.ZipFile(path) as bundle:
        if len(bundle.infolist()) > 30 or sum(info.file_size for info in bundle.infolist()) > 4 * 1024**2:
            raise ValueError("archive exceeds limits")
        seen = set()
        for info in bundle.infolist():
            if "/" in info.filename or "\\" in info.filename or info.filename in {".", ".."} or info.filename in seen or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("unsafe archive path, duplicate file or symlink")
            seen.add(info.filename)
        files = {info.filename: bundle.read(info).decode() for info in bundle.infolist()}
    manifest = json.loads(files["run-manifest.json"])
    hashes = manifest["artifact_hashes"]
    required = {"incident.redacted.json", "contract.json", "scenarios.json", "original_handler.py", "candidate_handler.py", "generated_regression_test.py"}
    if not required.issubset(files) or set(hashes) != set(files) - {"run-manifest.json"}:
        raise ValueError("evidence archive must hash every artifact and include replay inputs")
    for name, expected in hashes.items():
        if name not in files or digest(files[name]) != expected:
            raise ValueError(f"artifact hash mismatch: {name}")
    return files
