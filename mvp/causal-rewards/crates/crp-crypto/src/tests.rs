//! Conformance tests: reproduce the golden vectors under `test-vectors/` and the
//! serialization.md constants byte-for-byte. If these pass, the on-chain hashing /
//! Merkle / seed-commitment logic agrees with the verifier reference (Invariant 2).

use super::*;
use serde_json::Value;
use std::path::PathBuf;

fn vectors_dir() -> PathBuf {
    // crates/crp-crypto -> ../../test-vectors
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("../../test-vectors");
    p
}

fn hex32(s: &str) -> [u8; 32] {
    let b = hex::decode(s).expect("hex");
    assert_eq!(b.len(), 32);
    let mut r = [0u8; 32];
    r.copy_from_slice(&b);
    r
}

#[test]
fn seed_commitment_all_zero_matches_vector() {
    let seed = [0u8; 32];
    let got = seed_commitment(&seed);
    // test-vectors/assignment/assign-01: seed_commitment for all-zero seed
    assert_eq!(
        hex::encode(got),
        "f2261eaa83213f94c8002ebf49daee8045fd34caa803c3d53b1d0aeb0fe6cd9c"
    );
}

#[test]
fn empty_tree_root_is_zeroes() {
    let empty: Vec<Vec<u8>> = vec![];
    assert_eq!(merkle_root(&empty, DOMAIN_ASSIGNMENT), EMPTY_ROOT);
}

#[test]
fn assignment_leaf_bytes_match_reference() {
    // From assign-01 vector: control / cohort-0001
    let b = assignment_leaf_bytes("control", "cohort-0001");
    assert_eq!(
        String::from_utf8(b.clone()).unwrap(),
        r#"{"arm":"control","cohort_id":"cohort-0001"}"#
    );
    assert_eq!(
        hex::encode(leaf_hash(DOMAIN_ASSIGNMENT, &b)),
        "51e3196d9f8ea5c6a41d5c9c67d38b1cfc3ee814496a65e9bf9b866de3ba5667"
    );
}

fn run_assignment_vector(dir: &str) {
    let mut p = vectors_dir();
    p.push("assignment");
    p.push(dir);
    p.push("vector.json");
    let raw = std::fs::read_to_string(&p).unwrap_or_else(|_| panic!("read {:?}", p));
    let v: Value = serde_json::from_str(&raw).unwrap();

    let inputs = &v["inputs"];
    let experiment_id = inputs["experiment_id"].as_str().unwrap();
    let seed = hex32(inputs["seed_hex"].as_str().unwrap());
    let cohort_ids: Vec<String> = inputs["cohort_ids"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_str().unwrap().to_string())
        .collect();
    let design = inputs["design"].as_str().unwrap();

    // step1 seed commitment
    let want_commit = v["step1_seed_commitment"]["seed_commitment_hex"]
        .as_str()
        .unwrap();
    assert_eq!(hex::encode(seed_commitment(&seed)), want_commit, "{dir}: seed_commitment");

    // derive
    let assignments = match design {
        "bernoulli" => {
            let ppm: u64 = inputs["params"]["treat_fraction_ppm"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap();
            derive_assignment_bernoulli(&seed, experiment_id, &cohort_ids, ppm)
        }
        "fixed_count" => {
            let k: usize = inputs["params"]["treatment_count"]
                .as_str()
                .unwrap()
                .parse()
                .unwrap();
            derive_assignment_fixed_count(&seed, experiment_id, &cohort_ids, k)
        }
        other => panic!("unknown design {other}"),
    };

    // step2 prf values
    for pv in v["step2_cohort_prf"]["values"].as_array().unwrap() {
        let cid = pv["cohort_id"].as_str().unwrap();
        let want: u64 = pv["prf_u64"].as_str().unwrap().parse().unwrap();
        let got = cohort_prf(&seed, experiment_id, cid);
        assert_eq!(got, want, "{dir}: prf for {cid}");
    }

    // step4 leaves: bytes + hash, in order
    let want_leaves = v["step4_leaves"]["leaves"].as_array().unwrap();
    assert_eq!(assignments.len(), want_leaves.len(), "{dir}: leaf count");
    for (a, wl) in assignments.iter().zip(want_leaves.iter()) {
        assert_eq!(a.cohort_id, wl["cohort_id"].as_str().unwrap(), "{dir}: order");
        assert_eq!(a.arm, wl["arm"].as_str().unwrap(), "{dir}: arm {}", a.cohort_id);
        let lb = assignment_leaf_bytes(a.arm, &a.cohort_id);
        assert_eq!(
            String::from_utf8(lb.clone()).unwrap(),
            wl["leaf_canonical_bytes_utf8"].as_str().unwrap(),
            "{dir}: leaf bytes {}",
            a.cohort_id
        );
        assert_eq!(
            hex::encode(leaf_hash(DOMAIN_ASSIGNMENT, &lb)),
            wl["leaf_hash_hex"].as_str().unwrap(),
            "{dir}: leaf hash {}",
            a.cohort_id
        );
    }

    // step5 root
    let want_root = v["step5_assignment_root"]["assignment_root_hex"]
        .as_str()
        .unwrap();
    assert_eq!(hex::encode(assignment_root(&assignments)), want_root, "{dir}: root");
}

#[test]
fn assignment_vector_01_bernoulli_p50() {
    run_assignment_vector("assign-01-bernoulli-p50");
}

#[test]
fn assignment_vector_02_fixed_count_2of5() {
    run_assignment_vector("assign-02-fixed-count-2of5");
}

#[test]
fn assignment_vector_03_bernoulli_p25() {
    run_assignment_vector("assign-03-bernoulli-p25");
}

#[test]
fn merkle_proof_roundtrip_all_indices() {
    // Build a reward tree of odd size (exercises promotion) and verify each proof.
    let n = 7usize;
    let recipients: Vec<[u8; 32]> = (0..n).map(|i| [i as u8; 32]).collect();
    let leaf_hashes: Vec<[u8; 32]> = recipients
        .iter()
        .enumerate()
        .map(|(i, r)| reward_leaf_hash(r, (1000 + i as u64) * 7, i as u64))
        .collect();
    let mut level = leaf_hashes.clone();
    let root = merkle_root_from_hashes(&mut level);
    for i in 0..n {
        let proof = build_proof(&leaf_hashes, i).unwrap();
        assert!(verify_proof(&leaf_hashes[i], &proof, &root), "index {i} verify");
        // tamper: wrong root must fail
        let mut bad = root;
        bad[0] ^= 0xff;
        assert!(!verify_proof(&leaf_hashes[i], &proof, &bad), "index {i} tamper root");
        // tamper: wrong amount produces different leaf hash -> fail against real root
        let bad_leaf = reward_leaf_hash(&recipients[i], 1, i as u64);
        assert!(!verify_proof(&bad_leaf, &proof, &root), "index {i} tamper leaf");
    }
}

#[test]
fn merkle_promotion_not_duplication() {
    // Three leaves: promotion (not Bitcoin-style duplication). Verify against a
    // hand-computed root using the documented formulas.
    let l: Vec<Vec<u8>> = vec![vec![1], vec![2], vec![3]];
    let h0 = leaf_hash(DOMAIN_REWARD, &l[0]);
    let h1 = leaf_hash(DOMAIN_REWARD, &l[1]);
    let h2 = leaf_hash(DOMAIN_REWARD, &l[2]);
    let n01 = node_hash(&h0, &h1);
    // h2 promoted unchanged to the next level, then combined with n01
    let expected = node_hash(&n01, &h2);
    assert_eq!(merkle_root(&l, DOMAIN_REWARD), expected);
    // duplication would instead give node_hash(&n01, &node_hash(&h2,&h2)); ensure different
    let dup = node_hash(&n01, &node_hash(&h2, &h2));
    assert_ne!(expected, dup);
}
