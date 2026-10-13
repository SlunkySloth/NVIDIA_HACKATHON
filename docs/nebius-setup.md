# Nebius setup and deployment

No cloud resources have been provisioned by this checkout. Inference, Sandbox,
and Compute access must be enabled in the owner's account. Keep API keys in
private runtime configuration; do not paste them into chat, commit them, or put
them in Terraform variables. The application reads environment variables and
does not load `.env` automatically.

## Enable inference and Sandbox access

1. Create or select a Token Factory account, enable inference, and create a
   server-side API key. Choose the exact NVIDIA/Nemotron model ID available in
   your account's authenticated model catalog. Do not guess a model identifier.
2. Request Sandbox access if it is not enabled. Sandboxes are a separate service
   and access may require approval. Obtain its API base URL, authentication token,
   and project ID when using Nebius IAM authentication.
3. Install the dependencies from `requirements.lock`. This adapter targets
   **contree-sdk 0.3.6**. Newer documentation can describe a different client API;
   do not upgrade the SDK without updating and testing the adapter.

References: [Sandbox overview](https://docs.tokenfactory.nebius.com/sandboxes/overview),
[model catalog API](https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models).

Create a private file from `.env.example`, edit it locally, and load it in your
shell. Its values must be valid shell assignments; quote values when necessary.

```bash
install -m 0600 .env.example .env
# Edit .env privately: inference key/model, Sandbox URL/key and IAM project ID.
set -a
source .env
set +a
PYTHONPATH=backend .venv/bin/python -m replaylab.cli doctor --output .replaylab/configuration.json
PYTHONPATH=backend .venv/bin/python -m replaylab.cli prepare-sandbox --output .replaylab/sandbox-image.json
```

Preparation imports the public Python base image, installs the reviewed lockfile,
uploads trusted observer code, makes it read-only, saves an immutable image UUID,
and verifies its fingerprint. It requires network/package installation inside
Sandbox and incurs provider usage. It requires no local Docker daemon. Put the
reported `image_uuid` in `CONTREE_IMAGE` in the private environment file, then
reload that environment.

```bash
PYTHONPATH=backend .venv/bin/python -m replaylab.cli doctor --live --output .replaylab/live-preflight.json
PYTHONPATH=backend .venv/bin/python -m replaylab.cli investigate credits --mode live
```

The live doctor performs actual inference, observer fingerprint validation,
original/reference replay, generated regression red/green execution, restart
checks, artifact retrieval, and cancellation of an operation it starts. Stop
if any check fails. A configured flag alone does not prove provider compatibility.
Save the report and evidence; both identify actual model and operation IDs.
Rebuild the immutable image after changing observer code or the dependency lock.

## Prepare a persistent Compute host

Required account metadata: Compute project ID, subnet ID, an SSH public key,
DNS hostname, approved hosting budget, and a reviewed source tag/branch. The
default plan creates a CPU host with 2 vCPUs/8 GiB RAM, a 40 GiB boot disk, a
separate 40 GiB data disk, and a static public IP. These defaults are a starting
configuration, not a quoted price. Inspect current pricing and account credits
before applying. The data disk has a Terraform destruction guard.

[Terraform authentication](https://docs.nebius.com/terraform-provider/authentication)
uses the Compute credential in the invoking environment, separately from
application inference/Sandbox keys.

```bash
cd deploy/nebius
cp terraform.tfvars.example terraform.tfvars
# Fill non-secret account IDs, public key, domain and source ref.
# Configure NEBIUS_IAM_TOKEN privately using your account's authentication flow.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=/tmp/replaylab-host.plan
# Review the concrete resource and cost implications before applying.
terraform apply /tmp/replaylab-host.plan
```

Retrieve the instance's public IP in the Nebius console, point the domain's A
record to it, and SSH as `replaylab`. Wait for `cloud-init status --wait`.
Cloud-init mounts the data disk, installs Docker, configures the firewall, clones
the source, and creates private `/srv/replaylab/runtime.env`. It does not start
the application before credentials are installed.

## Start and verify the deployment

On the server, edit `/srv/replaylab/runtime.env` privately with the verified
configuration. Keep permissions at 0600. Verify DNS and firewall access to ports
80/443 so Caddy can obtain its TLS certificate.

```bash
cd /srv/replaylab/app
sudo bash scripts/start-host.sh
sudo docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml ps
```

The start script builds a revision-labelled image, runs configuration and live
preflight inside it, then starts the persistent API and HTTPS proxy. A failed
live preflight prevents startup. Observe the application at `https://YOUR_DOMAIN`,
run a fresh live investigation, inspect its actual model and operation IDs,
download evidence, and reload the page. Open a separate browser profile to
verify private runs are not shared between sessions.

```bash
sudo docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml stop app
sudo docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml run --rm --no-deps -T app \
  python -m replaylab.cli seed-recordings --fixture all --mode live --include-flawed
sudo docker compose --env-file /srv/replaylab/hosting.env -f deploy/compose.yaml up -d
```

This command executes real investigations and exposes curated completed evidence
for read-only inspection. Recorded mode is labelled in the UI; opening a recording
does not execute or generate code. `--include-flawed` adds a separately labelled,
human-authored counterexample.
The API is stopped temporarily because standalone commands acquire the same
exclusive worker lease; recordings remain on the persistent disk afterwards.
Keep hosting and provider access available during judging.
See [operations](operations.md), [live evaluation](live-evaluation.md),
and [submission](submission.md).
