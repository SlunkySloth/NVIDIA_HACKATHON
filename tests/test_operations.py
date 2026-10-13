import json
import sqlite3
import zipfile

import pytest
from replaylab.backup import backup
from replaylab.catalog import sample
from replaylab.release import checkout_info
from replaylab.store import Store


def test_metadata_backup_is_consistent_private_and_never_overwritten(settings, tmp_path):
    store = Store(settings.data_dir)
    incident = sample("credits").model_dump(mode="json")
    ident = store.save_incident("backup-owner", incident)
    output = tmp_path / "snapshots/evidence.zip"
    assert backup(settings, output) == 0
    assert output.stat().st_mode & 0o777 == 0o600
    with zipfile.ZipFile(output) as archive:
        snapshot = tmp_path / "restored.sqlite"
        snapshot.write_bytes(archive.read("metadata.sqlite"))
        with sqlite3.connect(snapshot) as db:
            restored = db.execute("SELECT bundle FROM incidents WHERE id=?", (ident,)).fetchone()
        assert json.loads(restored[0]) == incident
        assert json.loads(archive.read("backup-manifest.json"))["missing_artifacts"] == []
    with pytest.raises(ValueError, match="output exists"):
        backup(settings, output)


def test_container_release_identity_does_not_require_git(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr("replaylab.release.subprocess.run", missing)
    monkeypatch.setenv("REPLAYLAB_REVISION", "reviewed-release")
    monkeypatch.setenv("REPLAYLAB_SOURCE_CLEAN", "true")
    assert checkout_info() == ("reviewed-release", False)
