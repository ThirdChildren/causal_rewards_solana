# Integration Guide — Causal Rewards Protocol

**Status:** SCAFFOLD (M4 deliverable). The full guide — end-to-end wiring, SDK walkthroughs, and the
reference pilot — lands in M4 (owner: orchestrator + `sdk-engineer`, per `docs/m4-plan.md` task 12).
This scaffold exists now to carry one boundary an integrator MUST read before wiring the protocol to
real incentives (owner ruling, 2026-07-30).

---

## What the protocol guarantees, and what it does not

The protocol is a **measurement and settlement layer**. It enforces *process* — commitments,
determinism, conservative payouts, and settlement integrity — but it does not certify the *truth* of
a causal estimate (Invariant 6). Before you connect it to a live reward budget, understand this
limit precisely.

### No concentration bound and no waste bound (read this before wiring live incentives)

The chain enforces the reward-curve **shape** deterministically. Given the frozen `reward_curve` and
the conservative per-cohort effects, every independent party recomputes the identical allocation
(Invariant 2). That is the whole of what is guaranteed about how money is distributed.

The protocol does **NOT** guarantee either of the following:

- **A concentration bound** — there is no protocol-enforced ceiling on how much of the budget a
  single cohort can absorb. If the frozen curve values one cohort highly and few cohorts clear the
  conservative test, that one cohort can take a large share of the budget. Under a true null the
  protocol correctly pays ~0 *in aggregate relative to budget* and recovers the remainder (Invariant
  8) — but concentration on a single chance cohort is a **calibration property of the chosen curve**,
  not something the chain limits.
- **A waste bound** — there is no protocol-enforced ceiling on how much budget can flow to cohorts
  that added no real additional value. The conservative lower bound (`max(0, effect − z·SE)`) and the
  minimum-sample gate reduce over-payment, but they do not bound expected wasted spend, which depends
  on the true (unknown) effect distribution.

**Why not.** The chain **cannot certify targeting** — that spend went to genuinely additional
cohorts — without assuming the very causal truth it is forbidden to assume (Invariant 6: the chain
verifies process, not truth). It can enforce a curve *shape* (an exposure control it can check
byte-for-byte); it cannot enforce that the shape aimed money correctly (a targeting property that
depends on ground truth).

**What you can do about it.** Concentration is controllable at the *manifest* level, not the protocol
level. A manifest author who wants a concentration ceiling can freeze a **saturating `reward_curve`**
(a curve shape — it needs no new frozen field and moves no protocol golden). The **recommended
default** — a calibrated curve plus a saturating per-cohort cap — is published guidance
(`specs/multiplicity-recommendation.md` §4), which each experiment freezes for itself. It is a
recommendation, not a protocol-enforced constant, and it is tunable per experiment.

**Bottom line for integrators.** If your deployment needs a hard concentration or waste guarantee,
you must supply it yourself — via curve calibration, a saturating cap, a budget ceiling, or off-chain
controls. **The protocol does not provide one, and no on-chain check will catch a mis-calibrated
curve.** This is an honest boundary, disclosed up front so you can design around it.
