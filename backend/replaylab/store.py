"""Durable queue, leases and progress. One worker owns this SQLite database."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

TERMINAL = {"EXPORTED", "NEEDS_CLARIFICATION", "UNSUPPORTED", "NOT_REPRODUCED", "PATCH_REJECTED", "INCONCLUSIVE", "CANCELLED", "FAILED"}


def now():
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "metadata.sqlite"
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, owner TEXT NOT NULL, bundle TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, owner TEXT NOT NULL, incident_id TEXT NOT NULL, mode TEXT NOT NULL, input_bundle TEXT NOT NULL, idem TEXT NOT NULL, request_hash TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0, lease TEXT, result TEXT, UNIQUE(owner,idem));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, created TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS event_run ON events(run_id,id);
''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_incident(self, owner, bundle):
        ident = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO incidents VALUES(?,?,?)", (ident, owner, json.dumps(bundle)))
        return ident

    def incident(self, ident, owner):
        with self.connect() as db:
            row = db.execute("SELECT bundle FROM incidents WHERE id=? AND owner=?", (ident, owner)).fetchone()
        return json.loads(row[0]) if row else None

    def update_contract(self, ident, owner, contract):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT bundle FROM incidents WHERE id=? AND owner=?", (ident, owner)).fetchone()
            if not row:
                raise KeyError(ident)
            bundle = json.loads(row[0])
            bundle["contract"] = contract
            db.execute("UPDATE incidents SET bundle=? WHERE id=? AND owner=?", (json.dumps(bundle), ident, owner))
        return bundle

    def create_run(self, owner, req, request_hash, max_queued, bundle):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE owner=? AND idem=?", (owner, req.idempotency_key)).fetchone()
            if row:
                if row["request_hash"] != request_hash:
                    raise ValueError("idempotency key was used for different input")
                return row["id"], False
            if db.execute("SELECT COUNT(*) FROM runs WHERE state='CREATED'").fetchone()[0] >= max_queued:
                raise OverflowError("worker queue is full")
            placeholders = ",".join("?" for _ in TERMINAL)
            if db.execute(f"SELECT COUNT(*) FROM runs WHERE owner=? AND state NOT IN ({placeholders})", (owner, *TERMINAL)).fetchone()[0]:
                raise OverflowError("this session already has an active investigation")
            ident, timestamp = str(uuid.uuid4()), now()
            db.execute("INSERT INTO runs(id,owner,incident_id,mode,input_bundle,idem,request_hash,state,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)", (ident, owner, req.incident_id, req.mode, json.dumps(bundle), req.idempotency_key, request_hash, "CREATED", timestamp, timestamp))
            db.execute("INSERT INTO events(run_id,created,state,message) VALUES(?,?,?,?)", (ident, timestamp, "CREATED", "Investigation queued"))
        return ident, True

    def recover(self):
        with self.connect() as db:
            rows = db.execute("SELECT id FROM runs WHERE lease IS NOT NULL AND state NOT IN ('EXPORTED','PATCH_REJECTED','CANCELLED','INCONCLUSIVE','FAILED','NOT_REPRODUCED','NEEDS_CLARIFICATION','UNSUPPORTED')").fetchall()
        for row in rows:
            self.transition(row[0], "INCONCLUSIVE", "Worker restarted; previous operation cannot be reconciled. Retry from a clean state.")

    def claim(self, lease):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE state='CREATED' AND lease IS NULL ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE runs SET lease=? WHERE id=?", (lease, row["id"]))
                return dict(row)
        return None

    def get_run(self, ident, owner=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?" + (" AND owner=?" if owner is not None else ""), (ident, owner) if owner is not None else (ident,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["result"] = json.loads(result["result"]) if result["result"] else None
        result.pop("owner", None)
        result.pop("lease", None)
        return result

    def transition(self, ident, state, message, result=None):
        timestamp = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,cancelled FROM runs WHERE id=?", (ident,)).fetchone()
            if not row or row["state"] in TERMINAL:
                return
            if row["cancelled"] and state != "CANCELLED":
                return
            db.execute("UPDATE runs SET state=?,updated=?,result=COALESCE(?,result) WHERE id=?", (state, timestamp, json.dumps(result) if result is not None else None, ident))
            db.execute("INSERT INTO events(run_id,created,state,message) VALUES(?,?,?,?)", (ident, timestamp, state, message))

    def events(self, ident, after=0):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 200", (ident, after))]

    def cancel(self, ident, owner):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,result,created FROM runs WHERE id=? AND owner=?", (ident, owner)).fetchone()
            if not row:
                return False
            if row["state"] in TERMINAL:
                return True
            timestamp = now()
            message = "Cancelled by user; active operations are being terminated"
            result = json.loads(row["result"]) if row["result"] else None
            if result:
                result.update(verdict="Cancelled", explanation=message)
                result["manifest"].update(finished_at=timestamp, elapsed_seconds=round((datetime.fromisoformat(timestamp) - datetime.fromisoformat(row["created"])).total_seconds(), 3), verdict="Cancelled")
            db.execute("UPDATE runs SET cancelled=1,state='CANCELLED',updated=?,result=? WHERE id=?", (timestamp, json.dumps(result) if result else None, ident))
            db.execute("INSERT INTO events(run_id,created,state,message) VALUES(?,?,?,?)", (ident, timestamp, "CANCELLED", message))
        return True
