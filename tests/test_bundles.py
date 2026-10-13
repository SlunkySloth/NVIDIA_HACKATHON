import json
import zipfile

import pytest
from replaylab.artifacts.bundle import read_bundle, write_bundle
from replaylab.catalog import sample
from replaylab.schemas import digest


@pytest.fixture
def archive(tmp_path):
    incident = sample("credits").model_dump(mode="json")
    result = {"manifest": {"run_id": "test"}, "verdict": "Inconclusive", "explanation": "No investigation executed"}
    write_bundle(tmp_path, "test", incident, result)
    return tmp_path / "artifacts/test/evidence.zip"


def rewritten(tmp_path, archive, edit):
    with zipfile.ZipFile(archive) as bundle:
        files = {name: bundle.read(name).decode() for name in bundle.namelist()}
    edit(files)
    target = tmp_path / "edited.zip"
    with zipfile.ZipFile(target, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return target


def test_bundle_detects_altered_source(tmp_path, archive):
    target = rewritten(tmp_path, archive, lambda files: files.update({"candidate_handler.py": "altered"}))
    with pytest.raises(ValueError, match="hash mismatch"):
        read_bundle(target)


def test_bundle_rejects_unhashed_artifact(tmp_path, archive):
    target = rewritten(tmp_path, archive, lambda files: files.update({"extra.py": "unexpected"}))
    with pytest.raises(ValueError, match="hash every artifact"):
        read_bundle(target)


def test_bundle_rejects_missing_replay_input(tmp_path, archive):
    def remove_source(files):
        files.pop("candidate_handler.py")
        manifest = json.loads(files["run-manifest.json"])
        manifest["artifact_hashes"].pop("candidate_handler.py")
        files["run-manifest.json"] = json.dumps(manifest)

    target = rewritten(tmp_path, archive, remove_source)
    with pytest.raises(ValueError, match="include replay inputs"):
        read_bundle(target)


@pytest.mark.parametrize("name", ["../outside.py", "/absolute.py", "folder/file.py", "folder\\file.py"])
def test_bundle_rejects_unsafe_paths(tmp_path, archive, name):
    target = rewritten(tmp_path, archive, lambda files: files.update({name: "unexpected"}))
    with pytest.raises(ValueError, match="unsafe archive path"):
        read_bundle(target)


def test_bundle_rejects_invalid_manifest(tmp_path, archive):
    target = rewritten(tmp_path, archive, lambda files: files.update({"run-manifest.json": "not json"}))
    with pytest.raises(ValueError, match="invalid evidence"):
        read_bundle(target)


def test_bundle_records_exact_artifact_hashes(archive):
    files = read_bundle(archive)
    hashes = json.loads(files["run-manifest.json"])["artifact_hashes"]
    assert hashes == {name: digest(content) for name, content in files.items() if name != "run-manifest.json"}
