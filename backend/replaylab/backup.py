"""Consistent local backups of metadata and completed evidence; no provider keys."""
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

from replaylab.store import Store, now


def backup(settings, output):
    if output.exists():
        raise ValueError("backup output exists; choose a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    store = Store(settings.data_dir)
    missing, copied = [], 0
    with tempfile.TemporaryDirectory(prefix="replaylab-backup-") as work:
        snapshot = Path(work) / "metadata.sqlite"
        with store.connect() as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        with sqlite3.connect(snapshot) as db:
            rows = db.execute("SELECT id,result FROM runs WHERE result IS NOT NULL").fetchall()
        with tempfile.NamedTemporaryFile(prefix=".replaylab-backup-", suffix=".zip", dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "metadata.sqlite")
                for ident, raw in rows:
                    UUID(ident)
                    for artifact in json.loads(raw).get("artifacts", []):
                        name = artifact["name"]
                        if Path(name).name != name or name in {".", ".."} or "\\" in name:
                            raise ValueError("invalid artifact path in metadata")
                        source = settings.data_dir / "artifacts" / ident / name
                        if source.is_file():
                            archive.write(source, f"artifacts/{ident}/{name}")
                            copied += 1
                        else:
                            missing.append(f"{ident}/{name}")
                recording_root = settings.data_dir / "recordings"
                if recording_root.exists():
                    for source in recording_root.rglob("*"):
                        if source.is_file() and not source.is_symlink():
                            archive.write(source, str(source.relative_to(settings.data_dir)))
                manifest = {"schema_version": "1", "created_at": now(), "metadata_sha256": __import__("hashlib").sha256(snapshot.read_bytes()).hexdigest(), "copied_artifacts": copied, "missing_artifacts": missing}
                archive.writestr("backup-manifest.json", json.dumps(manifest, indent=2))
            # Atomic creation refuses to overwrite an existing backup.
            os.link(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"output": str(output), "copied_artifacts": copied, "missing_artifacts": missing}, indent=2))
    return 2 if missing else 0
