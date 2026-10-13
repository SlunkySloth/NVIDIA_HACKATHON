# Local evaluation evidence

The checked-in `evals/local-baselines.json` records a local development baseline
evaluation. It ran 139 scenario/source pairs twice, for 278 executions. Business
state and HTTP acknowledgement traces matched across those repeats. The JSON
report records total elapsed time; timings depend on local machine load.

| Check | Recorded result |
| --- | --- |
| Infrastructure failures | 0 scenario/source pairs |
| Reference patch failures | 0 scenario/source pairs |
| Defective sources escaping every challenge | 0 |
| Trace differences across repeats | 0 scenario/source pairs |

The three reference patches pass duplicate delivery, legitimate distinct events,
independent entities, process restarts, and final challenge cases. The original
handlers fail their reported incidents. Credit and fulfillment defects include
in-memory deduplication, ignoring later events, deduplication by amount, shared
entity state, and an acknowledgement without the intended effect. The subscription
comparison accepts stale versions and is rejected.

These are authored synthetic development cases. The final scenarios are withheld
from patch feedback within a run, but this evaluation is not an unseen incident
benchmark. It makes no inference calls and does not measure Nemotron repair
quality, live provider latency, spend, production reliability, or user adoption.

Scenario generator version 2 avoids collisions between imported event/entity IDs
and generated challenge IDs. The reproduction command retains generator version
1 for earlier evidence; the curated sample scenarios are unchanged across versions.

## Frozen incident reference baseline

`evals/holdout-reference.json` records eight complete investigations against
independently authored revisions: six defective cases and two clean controls.
Every defective case was reproduced and its human-authored reference repair
verified; both clean controls were left unchanged. There were no inconclusive
or unattempted cases. Total elapsed time was 136.382 seconds on this machine.
The report records the frozen dataset hash and exact per-run evidence hashes;
the eight original ZIPs are retained in `evals/holdout-reference-evidence/`.

This is a **reference baseline**, with zero inference calls and no remote
Sandbox execution. All eight source manifests identify clean public revision `a9b900a`. Exact
handler/test bytes and their hashes are preserved inside the archives. The earlier
dirty-development result remains in `evals/holdout-reference-development.json`
with its original evidence for provenance. Live model evaluation remains pending account setup;
[the protocol](live-evaluation.md) defines budgets, honest denominators,
clean controls, timings, usage and failure retention.

```bash
PYTHONPATH=backend .venv/bin/python -m replaylab.cli evaluate-incidents --split holdout --mode reference --output /tmp/holdout-reference.json --data-dir /tmp/replaylab-evaluation
PYTHONPATH=backend .venv/bin/python -m replaylab.cli reproduce evals/holdout-reference-evidence/RUN_ID.zip
```

Reproduce the development baseline evaluation from the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m replaylab.cli evaluate --all-flaws --repeats 2 --output /tmp/replaylab-baselines.json
```

The backend suite additionally exercises complete reference investigations for
all three fixtures, actual red/green regression execution, evidence download and
reproduction, flawed patch rejection, collection errors, input validation,
session isolation, idempotency, cancellation, archive integrity, and recovery.
Browser checks exercise comparison, regression inspection, ZIP export, reload,
flawed patch rejection, and cancellation followed by a fresh investigation.

Local integration tests need localhost socket access. Browser checks need Chrome
or Playwright Chromium. A restricted execution environment failing to bind a
port is an execution limitation, not evidence that a patch was rejected.
