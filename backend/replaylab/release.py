"""Release identity from a source checkout or explicit container build metadata."""
import os
import subprocess

from replaylab.config import ROOT


def checkout_info():
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
        state = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, capture_output=True, text=True, check=False)
        if revision.returncode == 0:
            return revision.stdout.strip(), bool(state.stdout.strip()) if state.returncode == 0 else None
    except FileNotFoundError:
        pass
    declared = os.getenv("REPLAYLAB_REVISION", "uncommitted")
    clean = os.getenv("REPLAYLAB_SOURCE_CLEAN", "")
    return declared, clean.lower() != "true" if clean else None
