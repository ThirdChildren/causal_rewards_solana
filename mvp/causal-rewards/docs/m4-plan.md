# M4 plan — pilot, hardening, release (wk 15–20)

**Status:** PLAN. Sequenced so that the at-scale benchmark and everything else consuming reward
policy lands *after* the v1.2 decision. Owner column distinguishes agent-executable work from
work only the project owner can do.

M4 acceptance (CLAUDE.md): tagged OSS release + public dashboard + benchmark report + resolved
review findings.

---

## 0. Gate status entering M4

- **M3 acceptance gate: MET and independently verified** — `crp-verify` returns ACCEPT (exit 0)
  on a real bundle, 33 tests pass, adversarial bundles rejected, goldens intact, no forked
  encoder. It is **formally unstamped only** because the milestone-gating rule bars M3
  acceptance while M2 is open.
- **M2: one open item** — devnet deploy + 18/18 integration re-run. Blocked on wallet funding.

Both stamps land together the moment devnet closes.

---

## 1. Devnet: computed costs

Verified on this machine, not estimated:

| Fact | Value |
|---|---|
| Deploy wallet | `yP8HDbBX5f1CP2YzbhHhQ6GT31zggaDiRmt5dDMVe2Q` |
| Is it the CLI default? | **Yes** — `solana address -k ~/.config/solana/id.json` matches, so `scripts/deploy-devnet.sh` needs no flags |
| Total program bytes | 1,231,920 (`experiment_registry` 384,984 · `settlement` 382,384 · `challenge` 294,232 · `evidence_registry` 170,320) |
| Rent-exempt for that size | **8.57505408 SOL** (`solana rent 1231920`) |
| Peak requirement | **~17.2 SOL** — during deploy the buffer account and the program-data account are rent-exempt simultaneously |
| Resident after deploy | ~8.58 SOL + transaction fees |

### Rent reclaim (asked explicitly)

- **`solana program close --buffers`** reclaims rent from **leaked buffer accounts** — buffers
  left behind when a deploy fails partway. On a clean deploy the buffer is consumed and there is
  nothing to reclaim. Run it after any failed or interrupted deploy; it is the cheap win.
- Reclaiming the **resident ~8.58 SOL** requires `solana program close <PROGRAM_ID>`, which
  **permanently retires that program ID** — it can never be redeployed to the same address. Do
  this only when finished with a program ID for good, never between test redeploys.
- **Redeploys are cheap**: `anchor deploy` to an existing program ID reuses the program-data
  account and pays only the transaction fees plus any rent delta if the binary grew. The ~8.58
  SOL is a one-time cost, not per-deploy.

Practical funding path: `solana airdrop 2` is rate-limited per request, so either repeat it or
use `faucet.solana.com` (GitHub auth, higher limits).

---

## 2. Task table

`#` matches the session task list. **USER** = not delegable to an agent.

| # | Task | Owner | Blocked by | Acceptance test |
|---|------|-------|-----------|-----------------|
| 1 | Fund devnet wallet | **USER** | — | `solana balance --url devnet` ≥ 17.5 SOL |
| 2 | Devnet deploy + 18/18 integration re-run | orchestrator (solana-program-engineer on failure) | 1 | 4 program IDs live on devnet; 18/18 pass against devnet |
| 3 | Stamp M2 + M3 acceptance | orchestrator | 2 | both recorded as formally ACCEPTED with evidence links |
| 4 | Public dashboard | frontend-engineer | — *(started)* | 5 views render from `golden-happy`; exported bundle passes `crp-verify` ACCEPT; invariants 5/6/7/8 upheld |
| 5 | Normalization audit + 4-way / floor / cap study | causal-inference-engineer | — *(started)* | written answer to (a)/(b)/(c); reward goldens `a9c35cf4`/`ea943182`/`b882c899` reproduce; study regenerates byte-identically |
| 6 | Spec-side allocation audit + v1.2 packaging | protocol-architect | — *(started)* | spec-vs-implementation verdict written; v1.2 is one coherent package; goldens `74e0bb82` / `901b08d5` unchanged |
| 7 | **DECISION: adopt or reject v1.2** | **USER** | 5, 6 | decision recorded in `project_state.md` + `CONTEXT_HANDOFF.txt` |
| 8 | Implement v1.2 migration | protocol-architect → causal-inference-engineer + verifier-reproducibility-engineer + sdk-engineer | 7 | new goldens computed, recorded, independently reproduced by `crp-verify`; all cross-impl vectors regenerated |
| 9 | Benchmark at target scale | causal-inference-engineer | 7, 8 | reproducible from committed seed + pinned container digest; two fresh runs identical |
| 10 | Security review + resolve findings | security-reviewer, then **USER** for external | 2 | written report; every finding fixed or explicitly accepted |
| 11 | **Pilot validation** | **USER** | — | 6 interview writeups · 2 written technical reviews · 1 external dataset reproduced by `crp-verify` |
| 12 | Docs (integration guide, dev docs, benchmark report, final report) | orchestrator + specialists | benchmark report ⇐ 9 | third party integrates from the guide alone; no doc overstates the causal claim |
| 13 | Tagged OSS release + public dashboard deploy | orchestrator | 4, 9, 10, 11, 12 | tag pushed; dashboard live on devnet; report published; findings closed |

---

## 3. Sequencing rationale

**The v1.2 decision (7) is the pivot.** Task 9 publishes exactly the reward-policy numbers under
debate, so running it before the decision means running it twice. Everything downstream of 9 —
the benchmark report in 12, and 13 — inherits that constraint.

**Task 4 is deliberately unblocked.** The dashboard reads committed state (manifest hashes, roots,
claim status, the audit bundle) and does not depend on the multiplicity ruling. Reward-policy
semantics stay behind a thin adapter so a v1.2 outcome cannot force a rewrite. This is the only
large M4 build that can safely run in parallel with the decision.

**Task 10 splits.** The internal `security-reviewer` pass can start as soon as programs are live
on devnet. The *external* review is a user-arranged engagement and should be started early
because its latency is outside our control.

---

## 4. USER-owned items — flag these every session

Same standing as the devnet item. Agents can prepare materials but cannot perform these.

1. **Devnet funding** (task 1) — blocks two milestone stamps.
2. **The v1.2 decision** (task 7) — blocks the at-scale benchmark.
3. **Pilot validation** (task 11) — 6 discovery interviews, 2 written technical reviews, 1
   external dataset replay. Agents can build the interview guide, the reviewer packet, and the
   replay harness; the engagements themselves are the owner's.
4. **External security review** (task 10) — arranging the external reviewer.

---

## 5. Standing constraints for all M4 work

- **Invariant 7:** devnet only. No mainnet, no token, no protocol fee. `deploy-devnet.sh` refuses
  any other cluster; keep it that way.
- **Invariant 8:** null results are valid outputs. The benchmark report publishes the
  causal-vs-baseline comparison honestly, including outcomes where causal allocation does not win.
  Nothing is tuned to make causal win.
- **Invariant 6:** no surface — dashboard, docs, or report — may imply the chain proves the causal
  effect. It verifies process, not truth.
- **Invariant 2:** determinism tests are mandatory for anything emitting an artifact. The audit
  export in task 4 is such an artifact.
