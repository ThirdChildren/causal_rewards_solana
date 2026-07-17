---
name: feedback-commits
description: Commit-message convention for this repo — no author/co-author trailers, message only.
metadata:
  type: feedback
---

Commit messages contain the MESSAGE ONLY — no `Co-Authored-By` and no author trailers.

**Why:** User explicitly asked for this on the first commit (2026-07-17), overriding the
default Claude Code co-author trailer.

**How to apply:** When committing in this repo, omit the `Co-Authored-By: Claude ...` line and
any author attribution. Just the conventional-commit message body.
