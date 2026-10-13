# Supported incidents

ReplayLab accepts JSON data for three vetted Python/FastAPI/SQLite handlers:

| Fixture | Event type | Payload | Expected behavior |
| --- | --- | --- | --- |
| `credits` | `purchase.succeeded` | `{"credits": 100}` | Each unique event grants its amount once. |
| `fulfillment` | `order.paid` | `{}` | Each unique event creates one local fulfillment. |
| `subscriptions` | `subscription.updated` | `{"version": 2, "status": "cancelled"}` | A strictly higher entity version replaces state. |

Obtain compatible examples with:

```bash
PYTHONPATH=backend .venv/bin/python -m replaylab.cli sample credits > /tmp/credits.json
```

The API publishes the full schema at `/api/schema/incident`; a checked-in copy is
available in [contracts/incident.schema.json](../contracts/incident.schema.json).
Input includes the
exact handler SHA-256, initial state and its hash, an ordered event sequence, and
the published behavior contract. At least one step must be a delivery; restart
steps may appear between deliveries. Sequence indexes start at zero and must be
contiguous. An incident has at most 32 steps and a request is limited to 128 KiB.

Credits and fulfillment initial state map entity IDs to nonnegative integer
counts. Subscription state maps entity IDs to objects containing a nonnegative
integer version and one of `active`, `cancelled`, or `past_due`. New subscription
deliveries require positive versions. Repeated event IDs must identify the same
entity, event type, and payload.

Local imports may change the symptom, deliveries, arrival timestamps, and initial
state. Recompute `initial_state_hash` with `replaylab.schemas.digest` when editing
state. Keep the fixture revision and published contract unchanged. The observer
implements these fixed semantics; changing a contract's prose does not introduce
a different supported business rule. The UI requires contract review before
starting an investigation.

Set `provenance` to `sanitized local import` for prepared local data and ensure it
contains no sensitive information. The `redacted` field is an input declaration;
the application does not guarantee complete automatic redaction. Public demo mode
accepts only unchanged synthetic sample incidents.

Imports do not accept executable code, archives, arbitrary repositories, package
installation instructions, real billing operations, or external fulfillment.
The supported execution model is serial delivery and process restart with
persistent SQLite. Arrival timestamps do not establish subscription ordering;
the fixture explicitly uses entity versions.
