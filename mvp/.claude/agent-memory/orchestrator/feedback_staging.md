---
name: feedback-staging
description: Do not use git add -A while a background agent is editing; stage specific paths.
metadata:
  type: feedback
---

When committing while one or more background agents are still running, do NOT `git add -A`.
Stage only the specific paths for the deliverable being committed (`git add <path> ...`).

**Why:** `git add -A` repeatedly swept mid-edit WIP from running subagents into unrelated
commits (crp-crypto WIP, SDK partials, and architect spec edits — 3 times by 2026-07-23).
Harmless to runtime (agents read the working tree, not commits) but it pollutes history and can
snapshot an inconsistent intermediate spec.

**How to apply:** Before any commit, check whether an agent is still running. If so, `git add`
only the files the just-finished agent produced; leave the other agent's paths untracked/unstaged.
Re-verify hashes (manifest 74e0bb82…, evidence 901b08d5…) after any commit that touches specs/.
Relates to [[feedback-commits]].
