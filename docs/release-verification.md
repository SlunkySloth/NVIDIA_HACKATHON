# Verified local preview prerelease

Observed October 14, 2026 (India Standard Time). Actual provider access is still
unconfigured. This release establishes the local application and container
workflow, with no model-quality or cloud-deployment claim.

## Public source and clean installation

Code revision: `53d35a1ae3cbcaead629289f74ef437af0378ad7`.
[Hosted workflow](https://github.com/SlunkySloth/NVIDIA_HACKATHON/actions/runs/38447274917):
all three jobs passed. The application job installed the reviewed dependencies
from scratch on Python 3.12 and Node 22, passed 58 backend tests and four browser
checks, and built the web workspace. The infrastructure job initialized the
pinned Nebius provider and passed Terraform format/validation checks without
provisioning resources.

The container job built both reviewed Dockerfiles. The root observer successfully
ran actual original/reference HTTP replay and assertion red/green tests for all
three fixtures with networking disabled, a read-only filesystem, and temporary
writable state. Its limited capabilities include permission to stop lower-UID
candidate processes. The production API started successfully as UID 10001 with
all capabilities dropped, a read-only root filesystem, and a writable persistent
Docker volume. These checks exercise Docker locally on the CI runner; they do
not substitute for Token Factory Sandbox preflight.

## Reference evaluation and walkthrough

The refreshed eight-case report in `evals/holdout-reference.json` reproduces six
defects and verifies six human-authored reference repairs; both clean controls
remain unchanged. No cases are unattempted or inconclusive. Runtime was 136.382
seconds. All eight exact evidence archives identify clean public revision
`a9b900a3ead626fd1c7f00e9f4379e5e25c2e5bb`, with the same application source as
this code release. Earlier development results and their evidence remain
separately labelled for provenance.

The narrated 110.286-second reference walkthrough captures a real browser run
`ab1a2aac-af1d-44e8-8d84-ebdd69313572`, which completed in 36.380 seconds. It shows
the reviewed contract, actual 200/100-credit comparison, original/candidate
regression results, process restart, independent matrix, and evidence export.
Waiting is explicitly compressed. The screen and speech identify human-authored
reference mode and zero inference. This clip is a preview, not the final
qualifying live hackathon demonstration. Narration uses a generic eSpeak voice.

## Delivery still requiring account access or real people

Follow [Nebius setup](nebius-setup.md) to enable inference/Sandbox access, prepare
an immutable image, and pass actual provider preflight. Then execute the frozen
live evaluation, provision the approved Compute host/domain, verify HTTPS and a
fresh live investigation, observe external testers, capture the live walkthrough,
and publish/submit its actual links. The owner must supply private configuration,
account metadata, domain/budget and account authentication where required.
