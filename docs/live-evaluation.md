# Evaluating actual NVIDIA repair runs

The frozen development split has four incidents. The holdout split has six
independently authored defective revisions and two clean controls. Their source,
input contracts and expected original outcomes are public and hashable. They
are unseen to an individual model call until that case is evaluated; they are
not a secret external benchmark. Do not modify the holdout after observing live
results without making and reporting a new dataset version.

First pass `doctor --live`, then exercise one development investigation. Repair
provider compatibility problems on development cases and freeze the application
revision before running the complete holdout.

```bash
PYTHONPATH=backend .venv/bin/python -m replaylab.cli evaluate-incidents \
  --split development --mode live --max-runs 4 --max-tokens 160000 \
  --output evals/development-live.json --data-dir .replaylab/evaluation-development
PYTHONPATH=backend .venv/bin/python -m replaylab.cli evaluate-incidents \
  --split holdout --mode live --max-runs 8 --max-tokens 320000 \
  --output evals/holdout-live.json --data-dir .replaylab/evaluation-holdout
```

These commands spend actual provider credits. Set a concrete budget first.
Token limits reserve capacity for another complete run; failures with missing
usage retain their reservations. Optional rates in `.env.example` estimate
inference cost only. They exclude Compute and Sandbox costs. Sandbox costs stay
in their provider-defined units until checked against billing.

The batch report is saved after every run and retains failed, rejected,
inconclusive, and unattempted cases. Report verified fixes out of **all attempted
defective cases**, clean cases changed out of **all attempted clean cases**,
time to reproduced evidence, total elapsed time, exact model IDs, tokens, and
all operation IDs. Publish evidence for failures as well as successes. Preserve
the report and its adjacent `REPORT_NAME-evidence/` directory together. The batch
copies available exact ZIPs there and records their SHA-256 hashes; paths are
local paths, not public downloads. Do not replace the human-reference report
with a live report or present the reference repair rate as model quality.

A useful live comparison needs the same frozen inputs and budget for every
model/configuration, with each run starting from clean state. For repeatability,
run a declared second pass and retain both results rather than choosing the best
attempt. This is a small synthetic evaluation with serial delivery and local
SQLite semantics; it does not establish concurrent or production behavior.
