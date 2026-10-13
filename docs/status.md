# ReplayLab delivery status

Updated October 14, 2026. The local application is working. The complete
hackathon submission is still awaiting actual provider access and deployment.

## Implemented and checked

- Three original synthetic incidents, explicit contracts, independently authored
  defect variants, and clean controls.
- Actual HTTP/process/SQLite replay, restart-aware red/green regression checks,
  independent scenario verification, and bounded counterexample reduction.
- Durable queue, session isolation, idempotency, streaming progress,
  cancellation/recovery, reload, and exact evidence export/reproduction.
- Comparison UI, diff, scenario matrix, and labelled read-only saved recordings.
- Bounded model adapter and remote Sandbox preparation/fingerprint validation,
  with configuration diagnostics and an explicit real-provider preflight.
- Separate development/holdout evaluation, every attempted outcome retained,
  cost/usage metadata and portable exact evidence copies.
- Persistent Nebius Compute Terraform configuration, non-root application
  container, immutable observer image definition, Caddy HTTPS, private runtime
  configuration, consistent backups, and operating instructions.
- Automated source/lint/backend/browser/container/infrastructure workflow,
  demo capture/narration tools, submission draft, and user testing protocol.

All 58 backend tests pass; four browser tests, the web production build, Python
lint, and release source scan pass. Terraform initialization/validation and
Compose configuration validation pass. The [hosted workflow](https://github.com/SlunkySloth/NVIDIA_HACKATHON/actions/runs/38447274917)
passed all three jobs at code revision `53d35a1`: clean Python 3.12 backend and
browser checks, actual root-observer and non-root API containers, and pinned
Terraform validation. See [release verification](release-verification.md).

The authored development baseline contains 278 executions with no observed
infrastructure or repeatability failures and all defective sources rejected.
The frozen holdout reference baseline reproduced six defects and verified six
reference repairs; both clean controls were unchanged. These are human-authored
reference results, with zero model inference calls. The README screenshot is an
actual reference run. The refreshed eight-case ZIPs identify clean public revision `a9b900a`; earlier
dirty-development results are retained separately.

## External release gates

| Gate | Required evidence | State |
| --- | --- | --- |
| Token Factory inference + NVIDIA model | Account-enabled accessible model, actual generation and exact returned model ID | Access not configured |
| Token Factory Sandbox | Approved access, immutable image, passing root observer/artifact/restart/cancellation preflight | Access not configured |
| Live holdout | Frozen full batch, failures retained, actual usage/latency/evidence | Pending both providers |
| Persistent public demo | Nebius project/subnet, domain, hosting budget, HTTPS and fresh live run | Prepared configuration; not provisioned |
| External user feedback | Observed sessions and actual feedback log | Zero sessions |
| Submission video | Actual live workflow, spoken attribution, public YouTube URL below three minutes | Narrated 1:50 reference walkthrough available as a GitHub preview; live YouTube publication pending |
| Source publication/CI | Clean public revision and passing hosted workflow | Published on GitHub; all three hosted jobs passed at `53d35a1` |
| Devpost submission | Verified links, team details and submission confirmation | Pending owner account access |

Follow [Nebius setup](nebius-setup.md), [live evaluation](live-evaluation.md),
[operations](operations.md), [demo capture](demo-script.md), and
[submission](submission.md). Configuration and mocked transport tests do not
demonstrate actual sponsor integration. No deployment, user, cost, video upload,
or model repair quality is claimed without its corresponding observed artifact.
