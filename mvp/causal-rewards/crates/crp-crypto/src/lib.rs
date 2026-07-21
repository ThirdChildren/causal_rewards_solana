//! Shared canonical hashing / Merkle / seed-commitment / assignment logic for the
//! Causal Rewards Protocol.
//!
//! This crate is the SINGLE on-chain implementation of the byte-level rules in
//! `specs/serialization.md` (RATIFIED, `spec-v1-frozen`). It is intentionally the
//! same construction as the verifier reference (`verifier-cli/reference/`) and is
//! unit-tested against the golden vectors under `test-vectors/`. Do NOT introduce a
//! second encoder anywhere; call into this crate.
//!
//! Determinism (Invariant 2): no floats, no wall-clock, no unseeded RNG. SHA-256 only.

#![allow(clippy::result_unit_err)]

use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// Hash primitive
// ---------------------------------------------------------------------------

/// SHA-256 of a single byte slice.
#[inline]
pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(data);
    let out = h.finalize();
    let mut r = [0u8; 32];
    r.copy_from_slice(&out);
    r
}

/// SHA-256 over the concatenation of several slices (no intermediate allocation).
#[inline]
pub fn sha256v(parts: &[&[u8]]) -> [u8; 32] {
    let mut h = Sha256::new();
    for p in parts {
        h.update(p);
    }
    let out = h.finalize();
    let mut r = [0u8; 32];
    r.copy_from_slice(&out);
    r
}

// ---------------------------------------------------------------------------
// Merkle tree (serialization.md §6)
// ---------------------------------------------------------------------------

pub const LEAF_PREFIX: u8 = 0x00;
pub const NODE_PREFIX: u8 = 0x01;
/// Root of an empty tree: 32 zero bytes (§6.4).
pub const EMPTY_ROOT: [u8; 32] = [0u8; 32];

// Per-tree domain tags (ASCII), distinct by construction (§6.1).
pub const DOMAIN_PARTICIPANT: &[u8] = b"CRP:participant:v1";
pub const DOMAIN_ASSIGNMENT: &[u8] = b"CRP:assignment:v1";
pub const DOMAIN_EVIDENCE: &[u8] = b"CRP:evidence:v1";
pub const DOMAIN_REWARD: &[u8] = b"CRP:reward:v1";

/// `leaf_hash = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes )`.
#[inline]
pub fn leaf_hash(domain: &[u8], canonical_bytes: &[u8]) -> [u8; 32] {
    sha256v(&[&[LEAF_PREFIX], domain, canonical_bytes])
}

/// `node_hash = SHA-256( 0x01 || left || right )`.
#[inline]
pub fn node_hash(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
    sha256v(&[&[NODE_PREFIX], left, right])
}

/// Build the Merkle root from an ORDERED list of already-canonical leaf byte strings.
/// Caller must have placed leaves in the tree's canonical order (§6.2/§6.5); this
/// function never reorders. Odd trailing node is PROMOTED unchanged (§6.3).
pub fn merkle_root(ordered_leaf_bytes: &[Vec<u8>], domain: &[u8]) -> [u8; 32] {
    if ordered_leaf_bytes.is_empty() {
        return EMPTY_ROOT;
    }
    let mut level: Vec<[u8; 32]> = ordered_leaf_bytes
        .iter()
        .map(|lb| leaf_hash(domain, lb))
        .collect();
    merkle_root_from_hashes(&mut level)
}

/// Reduce a level of leaf hashes to the root (promotion on odd count).
pub fn merkle_root_from_hashes(level: &mut Vec<[u8; 32]>) -> [u8; 32] {
    if level.is_empty() {
        return EMPTY_ROOT;
    }
    while level.len() > 1 {
        let mut next: Vec<[u8; 32]> = Vec::with_capacity(level.len().div_ceil(2));
        let mut i = 0;
        while i < level.len() {
            if i + 1 < level.len() {
                next.push(node_hash(&level[i], &level[i + 1]));
                i += 2;
            } else {
                next.push(level[i]); // promote unpaired trailing node
                i += 1;
            }
        }
        *level = next;
    }
    level[0]
}

/// One step of a Merkle inclusion proof.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ProofStep {
    pub sibling: [u8; 32],
    /// true  => sibling is the LEFT node (self is the right child)
    /// false => sibling is the RIGHT node (self is the left child)
    pub sibling_is_left: bool,
}

/// Verify a Merkle inclusion proof: fold `leaf_hash` up through `proof` and
/// compare to `root`. Promotion levels contribute NO proof step (§6.3), so the
/// proof is exactly the siblings actually encountered.
pub fn verify_proof(leaf_hash: &[u8; 32], proof: &[ProofStep], root: &[u8; 32]) -> bool {
    let mut computed = *leaf_hash;
    for step in proof {
        computed = if step.sibling_is_left {
            node_hash(&step.sibling, &computed)
        } else {
            node_hash(&computed, &step.sibling)
        };
    }
    &computed == root
}

/// Produce the inclusion proof for `index` from an ordered list of leaf hashes.
/// (Used by SDK/tests to build proofs; not called on-chain.)
pub fn build_proof(leaf_hashes: &[[u8; 32]], index: usize) -> Option<Vec<ProofStep>> {
    if index >= leaf_hashes.len() {
        return None;
    }
    let mut proof = Vec::new();
    let mut level: Vec<[u8; 32]> = leaf_hashes.to_vec();
    let mut pos = index;
    while level.len() > 1 {
        let mut next: Vec<[u8; 32]> = Vec::with_capacity(level.len().div_ceil(2));
        let mut i = 0;
        while i < level.len() {
            if i + 1 < level.len() {
                if i == pos {
                    proof.push(ProofStep {
                        sibling: level[i + 1],
                        sibling_is_left: false,
                    });
                } else if i + 1 == pos {
                    proof.push(ProofStep {
                        sibling: level[i],
                        sibling_is_left: true,
                    });
                }
                next.push(node_hash(&level[i], &level[i + 1]));
                i += 2;
            } else {
                // promoted node: no proof step
                next.push(level[i]);
                i += 1;
            }
        }
        pos /= 2;
        level = next;
    }
    Some(proof)
}

// ---------------------------------------------------------------------------
// Seed commitment (serialization.md §7.2) — NO salt
// ---------------------------------------------------------------------------

pub const SEED_LEN: usize = 32;
pub const SEED_COMMIT_DOMAIN: &[u8] = b"CRP-seed-commit-v1";
pub const ASSIGN_PRF_DOMAIN: &[u8] = b"CRP-assign-v1";

/// `seed_commitment = SHA-256( "CRP-seed-commit-v1" || seed )`, seed is raw 32 bytes.
/// This is what `freeze_experiment` stores and `reveal_seed` re-checks on-chain.
#[inline]
pub fn seed_commitment(seed: &[u8; 32]) -> [u8; 32] {
    sha256v(&[SEED_COMMIT_DOMAIN, seed])
}

// ---------------------------------------------------------------------------
// Reward leaf (RATIFIED — serialization.md §6.6)
// ---------------------------------------------------------------------------

/// Fixed-width reward leaf content (48 bytes), RATIFIED unchanged in
/// `serialization.md` §6.6:
/// `recipient(32) || amount_base_units(u64 BE) || leaf_index(u64 BE)`.
/// leaf_hash = SHA-256(0x00 || "CRP:reward:v1" || content). Big-endian is fixed by
/// §6.6 for cross-language hash determinism (Invariant 2). §6.6 ratifies this exact
/// layout, so the encoding below is the canonical reward-leaf preimage the reward
/// tree and `claim_reward` prove against (the §6.2 reward-ordering deferral is
/// likewise resolved in §6.6: leaf position == `leaf_index`, contiguous from 0).
pub fn reward_leaf_content(recipient: &[u8; 32], amount_base_units: u64, leaf_index: u64) -> [u8; 48] {
    let mut out = [0u8; 48];
    out[0..32].copy_from_slice(recipient);
    out[32..40].copy_from_slice(&amount_base_units.to_be_bytes());
    out[40..48].copy_from_slice(&leaf_index.to_be_bytes());
    out
}

/// leaf_hash for a reward leaf, ready to feed into `verify_proof`.
pub fn reward_leaf_hash(recipient: &[u8; 32], amount_base_units: u64, leaf_index: u64) -> [u8; 32] {
    let content = reward_leaf_content(recipient, amount_base_units, leaf_index);
    leaf_hash(DOMAIN_REWARD, &content)
}

// ---------------------------------------------------------------------------
// Assignment derivation (serialization.md §7.3–§7.5) — OFF-CHAIN / host-test use.
// Not called by the on-chain programs (assignment is committed as cohort_root and
// verified off-chain by the verifier/challenger). Implemented + tested here so this
// crate is the single source of truth that agrees with the verifier reference.
// ---------------------------------------------------------------------------

pub const ARM_TREATMENT: &str = "treatment";
pub const ARM_CONTROL: &str = "control";
const PPM: u64 = 1_000_000;

/// prf_u64 per §7.3 (length-prefixed, big-endian).
pub fn cohort_prf(seed: &[u8; 32], experiment_id: &str, cohort_id: &str) -> u64 {
    let exp = experiment_id.as_bytes();
    let coh = cohort_id.as_bytes();
    let mut h = Sha256::new();
    h.update(ASSIGN_PRF_DOMAIN);
    h.update(seed);
    h.update((exp.len() as u32).to_be_bytes());
    h.update(exp);
    h.update((coh.len() as u32).to_be_bytes());
    h.update(coh);
    let d = h.finalize();
    let mut first8 = [0u8; 8];
    first8.copy_from_slice(&d[0..8]);
    u64::from_be_bytes(first8)
}

/// Canonical assignment leaf bytes: CJSON of `{"arm":..,"cohort_id":..}`.
/// `arm` (`treatment`/`control`) and `cohort_id` (`^[a-z0-9_-]{1,64}$`) are ASCII
/// with no characters needing escaping, and keys sort `arm` < `cohort_id`, so the
/// canonical bytes are built directly — byte-identical to the CJSON serializer.
pub fn assignment_leaf_bytes(arm: &str, cohort_id: &str) -> Vec<u8> {
    let mut v = Vec::with_capacity(24 + arm.len() + cohort_id.len());
    v.extend_from_slice(b"{\"arm\":\"");
    v.extend_from_slice(arm.as_bytes());
    v.extend_from_slice(b"\",\"cohort_id\":\"");
    v.extend_from_slice(cohort_id.as_bytes());
    v.extend_from_slice(b"\"}");
    v
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CohortAssignment {
    pub cohort_id: String,
    pub arm: &'static str,
    pub prf_u64: u64,
}

/// Sort key matching the reference: UTF-16-BE code-unit order of the id.
fn utf16be_key(s: &str) -> Vec<u8> {
    let mut out = Vec::new();
    for u in s.encode_utf16() {
        out.extend_from_slice(&u.to_be_bytes());
    }
    out
}

pub fn derive_assignment_bernoulli(
    seed: &[u8; 32],
    experiment_id: &str,
    cohort_ids: &[String],
    treat_fraction_ppm: u64,
) -> Vec<CohortAssignment> {
    let mut out: Vec<CohortAssignment> = cohort_ids
        .iter()
        .map(|cid| {
            let prf = cohort_prf(seed, experiment_id, cid);
            let arm = if prf % PPM < treat_fraction_ppm {
                ARM_TREATMENT
            } else {
                ARM_CONTROL
            };
            CohortAssignment {
                cohort_id: cid.clone(),
                arm,
                prf_u64: prf,
            }
        })
        .collect();
    out.sort_by(|a, b| utf16be_key(&a.cohort_id).cmp(&utf16be_key(&b.cohort_id)));
    out
}

pub fn derive_assignment_fixed_count(
    seed: &[u8; 32],
    experiment_id: &str,
    cohort_ids: &[String],
    treatment_count: usize,
) -> Vec<CohortAssignment> {
    let mut with_prf: Vec<(String, u64)> = cohort_ids
        .iter()
        .map(|cid| (cid.clone(), cohort_prf(seed, experiment_id, cid)))
        .collect();
    // rank by (prf_u64, cohort_id) ascending; first k are treatment.
    let mut ranked = with_prf.clone();
    ranked.sort_by(|a, b| a.1.cmp(&b.1).then_with(|| a.0.cmp(&b.0)));
    let treated: std::collections::HashSet<String> =
        ranked.iter().take(treatment_count).map(|x| x.0.clone()).collect();
    // canonical leaf order: cohort_id ascending (UTF-16-BE)
    with_prf.sort_by(|a, b| utf16be_key(&a.0).cmp(&utf16be_key(&b.0)));
    with_prf
        .into_iter()
        .map(|(cid, prf)| {
            let arm = if treated.contains(&cid) {
                ARM_TREATMENT
            } else {
                ARM_CONTROL
            };
            CohortAssignment {
                cohort_id: cid,
                arm,
                prf_u64: prf,
            }
        })
        .collect()
}

/// Compute the assignment Merkle root from an ordered assignment list.
pub fn assignment_root(assignments: &[CohortAssignment]) -> [u8; 32] {
    let leaves: Vec<Vec<u8>> = assignments
        .iter()
        .map(|a| assignment_leaf_bytes(a.arm, &a.cohort_id))
        .collect();
    merkle_root(&leaves, DOMAIN_ASSIGNMENT)
}

#[cfg(test)]
mod tests;
