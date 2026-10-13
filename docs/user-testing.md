# User testing protocol and feedback log

No external user sessions have been observed yet. This document is a protocol,
not a claim of adoption or a fabricated testimonial.

Ask three to five developers familiar with webhook handlers to use the hosted
demo. Obtain permission before recording a session or quoting feedback. Use
anonymous participant IDs and synthetic incidents only. Observe these tasks
without explaining the answer:

1. Identify the intended behavior and approve the contract.
2. Run an investigation, identify which observed state violates the contract,
   and explain the verified verdict's limits.
3. Inspect a restart and a legitimate distinct event; explain why in-memory
   deduplication is insufficient.
4. Find the red/green regression, inspect a failed scenario, download evidence,
   and return after reloading the page.
5. Open a saved recording and explain whether it launches new model work.

Record task completion, elapsed time, errors, points of confusion, one desired
improvement, and whether they would use the tool on a supported incident. Do
not treat passing automated browser tests as user feedback. Preserve actual
failures and report any changes resulting from them.

| Date | Anonymous participant | Task outcome/time | Observed confusion | Consented feedback | Change made/retest |
| --- | --- | --- | --- | --- | --- |

There are currently zero completed external sessions. Populate this table only
from actual sessions, without personal information, secret keys, or invented
quotes. A failed or abandoned task is useful evidence too.
