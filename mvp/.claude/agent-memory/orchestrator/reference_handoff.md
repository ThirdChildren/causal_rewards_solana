---
name: reference-handoff
description: Location + purpose of the cold-start recovery document CONTEXT_HANDOFF.txt.
metadata:
  type: reference
---

Cold-start recovery document: `CONTEXT_HANDOFF.txt` at the REPO ROOT
(`/home/stephl0xff/personale/grant_blk/causal_rewards_solana/CONTEXT_HANDOFF.txt`).

Holds: project one-liner, milestone ledger (M1-M4 with acceptance tests + how verified),
ratified hashes read verbatim from disk, frozen-artifact + git state, the 4 resolved M1
open questions, the carried-discrepancies table, interface/serialization decisions,
what is not done, and a "how to resume" checklist.

**How to apply:** A fresh session with no context should read this file first. Update it at
the end of every milestone and whenever a ratified hash, frozen artifact, or carried
discrepancy changes. It is a deliverable, not a note. Hashes in it must be re-read from
disk, never transcribed from conversation.
