#!/usr/bin/env bash
# Start only a concrete, configured live deployment; never print credentials.
set -euo pipefail
cd /srv/replaylab/app
test -r /srv/replaylab/runtime.env
test -r /srv/replaylab/hosting.env
test -z "$(git status --porcelain)" || { echo 'Host source must be a clean reviewed checkout.' >&2; exit 2; }
export REPLAYLAB_REVISION
REPLAYLAB_REVISION=$(git rev-parse HEAD)
export REPLAYLAB_SOURCE_CLEAN=true
compose=(docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" build app
"${compose[@]}" run --rm --no-deps -T app python -m replaylab.cli doctor --live --output /data/live-preflight.json
"${compose[@]}" up -d
