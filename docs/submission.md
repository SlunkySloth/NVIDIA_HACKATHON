# Submission description and remaining gates

This is draft submission material. No hosted URL, live NVIDIA evidence, public
YouTube URL, or completed Devpost submission has been recorded yet.

**Name:** ReplayLab

**Track:** Coding and Agentic Engineering

**Tagline:** Reproduce webhook failures, challenge candidate fixes, and export
the evidence behind every verdict.

## Description

A duplicate webhook can return HTTP 200 while granting credits twice. A patch
can pass its own regression and still break after a process restart. ReplayLab
turns an explicit, reviewed behavior contract into an investigation that compares
the original handler and a candidate against independent SQLite observations.

The workflow reproduces the incident, requires a regression to fail meaningfully
on the original, tests at most two candidate patches, and challenges each with
duplicates, distinct legitimate events, independent entities, and restarts.
Final challenge cases are withheld from patch feedback. The UI links its verdict
to synchronized state timelines, a code diff, a scenario matrix, and an exact
evidence ZIP. Inconclusive execution is retained rather than reported as a fix.

Live mode is implemented to use a configured NVIDIA/Nemotron model through
Nebius Token Factory for structured regression and patch generation, with
Token Factory Sandboxes executing generated code in disposable branches of an
immutable observer image. Persistent hosting is prepared for Nebius Compute.
These integrations still require account setup and actual live verification.
The credential-free reference workflow uses real local FastAPI/SQLite services
and human-authored patches. It makes no inference calls.

The supported scope is intentionally explicit: three original Python/SQLite
webhook fixtures, serial delivery, and process restart. Concurrent workers,
external effects, arbitrary codebases, and production deployments are outside
the demonstrated fault model. A verified patch supports the tested scenarios.

## Results and evidence available now

- Authored development baseline: 278 executions, no observed infrastructure or
  repeatability failures, and every intentionally defective source rejected.
- Frozen holdout reference baseline: six defects reproduced and six reference
  fixes verified; both clean controls unchanged. Zero model inference calls.
- Working local UI, evidence export/reproduction, cancellation/reload, and
  read-only recorded investigations.
- MIT source, pinned dependencies, setup documentation, container definitions,
  Nebius Terraform configuration, and automated verification workflow.

See [evaluation](evaluation.md) for scope and denominators, [status](status.md)
for current verification, and [user testing](user-testing.md) for actual feedback.
Replace integration and result paragraphs with observed live evidence only after
the corresponding release gates pass.

## Submission checklist

| Requirement | Concrete artifact/gate | Current state |
| --- | --- | --- |
| Public source with open-source license | [Repository](https://github.com/SlunkySloth/NVIDIA_HACKATHON), MIT LICENSE, reproducible README | Published source and MIT license verified |
| Runtime Nebius and NVIDIA usage | Passing live preflight and actual model/operation IDs in evidence | Account setup required |
| Working demo URL | Persistent HTTPS host with tested fresh live run and saved recordings | Compute account, domain and budget required |
| Demonstration video | Actual workflow, spoken sponsor attribution, less than three minutes, public YouTube URL | Local recording tooling prepared; live capture/publication required |
| Description and feedback | This draft, honest live report, observed external sessions | Draft ready; external sessions pending |
| Judging access | Keep demo and credentials functional through judging | Pending deployment |
| Final submission | Fill Devpost fields, links and team details, submit, verify confirmation | Owner action pending |

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) specify
the working demo, public licensed repository, and video requirements. The
[organizer's guidance](https://nebiusglobalaihackathon.devpost.com/updates/46205-how-to-build-a-winning-project)
also asks for spoken attribution and user feedback. Recheck these sources before
submitting; hosting on an ordinary CPU VM alone is not our evidence of qualifying
NVIDIA runtime use. The planned actual inference call establishes that path.
