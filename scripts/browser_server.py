"""Start a local browser-test server with one real, labeled reference recording."""
import argparse
import asyncio
from argparse import Namespace

import uvicorn
from replaylab.config import Settings
from replaylab.recordings import list_recordings, seed_recordings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    settings = Settings()
    if not list_recordings(settings.data_dir):
        asyncio.run(seed_recordings(Namespace(fixture="credits", mode="reference", include_flawed=False), settings))
    uvicorn.run("replaylab.api.app:create_app", factory=True, host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
