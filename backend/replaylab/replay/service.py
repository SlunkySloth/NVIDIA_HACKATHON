"""Fixed fixture adapter. Generated patches can change only handler.py."""
import importlib.util
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI

app = FastAPI()
DB_PATH = os.environ["REPLAYLAB_DB"]
FIXTURE = os.environ["REPLAYLAB_FIXTURE"]
spec = importlib.util.spec_from_file_location("candidate_handler", Path(os.environ["REPLAYLAB_HANDLER"]))
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


@app.post("/webhook")
def webhook(event: dict):
    with sqlite3.connect(DB_PATH) as db:
        return handler.handle(db, event)


@app.get("/health")
def health():
    return {"ready": True}


@app.get("/state")
def state():
    # Convenience for generated tests. Independent checks read SQLite externally.
    with sqlite3.connect(DB_PATH) as db:
        if FIXTURE == "subscriptions":
            return {e: {"status": s, "version": v} for e, s, v in db.execute("SELECT entity,status,version FROM subscriptions ORDER BY entity")}
        return dict(db.execute("SELECT entity,value FROM balances ORDER BY entity"))
