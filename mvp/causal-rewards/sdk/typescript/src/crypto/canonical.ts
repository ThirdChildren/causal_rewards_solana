/**
 * Canonical JSON (CJSON) + SHA-256 — the TypeScript leg of the protocol's single
 * canonical serialization (specs/serialization.md §2–§5, RATIFIED, spec-v1-frozen).
 *
 * This module is byte-for-byte identical to the verifier reference
 * (`verifier-cli/reference/canonical.py`) and the on-chain `crp-crypto` crate.
 * It is deliberately small and auditable. There is EXACTLY ONE canonical encoding
 * in this protocol; do not add a second one.
 *
 * Rules enforced (serialization.md §2–§5):
 *   - Canonical JSON is a strict subset of RFC 8785 (JCS): UTF-8, no insignificant
 *     whitespace, object keys sorted by UTF-16 code-unit order, minimal escaping.
 *   - NO JSON number tokens are permitted in a hashed artifact. Every numeric value
 *     MUST be carried as a string. `number`/`bigint` inputs are REJECTED so the rule
 *     is mechanical, not a convention a caller can forget (§2).
 *   - All string values and object keys are Unicode-NFC normalized before encoding.
 */

import { sha256 as nobleSha256 } from "@noble/hashes/sha256";

/** SHA-256 of the concatenation of the given byte chunks. 32-byte output. */
export function sha256(...parts: Uint8Array[]): Uint8Array {
  if (parts.length === 1) return nobleSha256(parts[0]);
  let total = 0;
  for (const p of parts) total += p.length;
  const joined = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    joined.set(p, off);
    off += p.length;
  }
  return nobleSha256(joined);
}

/** SHA-256 rendered as 64 lowercase hex characters (serialization.md §5). */
export function sha256Hex(...parts: Uint8Array[]): string {
  return toHex(sha256(...parts));
}

/** Lowercase-hex encode a byte array (serialization.md §5 display form). */
export function toHex(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += b.toString(16).padStart(2, "0");
  return s;
}

/** Decode a lowercase-hex string to bytes. Rejects odd-length / non-hex input. */
export function fromHex(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error(`hex string has odd length: ${hex.length}`);
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = hex.slice(i * 2, i * 2 + 2);
    if (!/^[0-9a-fA-F]{2}$/.test(byte)) throw new Error(`invalid hex byte: ${byte}`);
    out[i] = parseInt(byte, 16);
  }
  return out;
}

/**
 * Any value that may appear inside a canonical (hashed) JSON artifact.
 * Note the deliberate ABSENCE of `number` — bare numbers are forbidden (§2) and
 * carried as strings instead. `bigint` is likewise rejected at runtime.
 */
export type CJsonValue =
  | string
  | boolean
  | null
  | CJsonValue[]
  | { [key: string]: CJsonValue };

const ENC = new TextEncoder();

/**
 * Serialize `value` to canonical UTF-8 bytes (serialization.md §3).
 * Accepts only: object, array, string, boolean, null. Throws on number/bigint
 * (§2) and on any other type.
 */
export function canonicalJsonBytes(value: CJsonValue): Uint8Array {
  const parts: string[] = [];
  serialize(value, parts);
  return ENC.encode(parts.join(""));
}

/** Convenience: the canonical UTF-8 string (for debugging / vectors). */
export function canonicalJsonString(value: CJsonValue): string {
  const parts: string[] = [];
  serialize(value, parts);
  return parts.join("");
}

function serialize(o: unknown, out: string[]): void {
  if (o === true) {
    out.push("true");
  } else if (o === false) {
    out.push("false");
  } else if (o === null) {
    out.push("null");
  } else if (typeof o === "string") {
    serializeString(o, out);
  } else if (typeof o === "number" || typeof o === "bigint") {
    throw new TypeError(
      `numbers are forbidden in hashed artifacts (serialization.md §2); carry the ` +
        `value as a decimal / scaled-integer STRING instead (got ${String(o)})`,
    );
  } else if (Array.isArray(o)) {
    serializeArray(o, out);
  } else if (typeof o === "object") {
    serializeObject(o as Record<string, unknown>, out);
  } else {
    throw new TypeError(`unserializable type: ${typeof o}`);
  }
}

function serializeArray(a: unknown[], out: string[]): void {
  out.push("[");
  for (let i = 0; i < a.length; i++) {
    if (i > 0) out.push(",");
    serialize(a[i], out);
  }
  out.push("]");
}

function serializeObject(d: Record<string, unknown>, out: string[]): void {
  // NFC-normalize keys, reject duplicates, sort by UTF-16 code-unit order.
  const items: Array<[string, unknown]> = [];
  const seen = new Set<string>();
  for (const rawKey of Object.keys(d)) {
    const key = rawKey.normalize("NFC");
    if (seen.has(key)) {
      throw new Error(`duplicate object key after NFC normalization: ${key}`);
    }
    seen.add(key);
    items.push([key, d[rawKey]]);
  }
  // JS string comparison compares by UTF-16 code units, exactly the RFC 8785 order
  // (and it coincides with UTF-8 byte order for the ASCII-only keys this protocol
  // requires — serialization.md §3.3).
  items.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));

  out.push("{");
  for (let i = 0; i < items.length; i++) {
    if (i > 0) out.push(",");
    serializeString(items[i][0], out);
    out.push(":");
    serialize(items[i][1], out);
  }
  out.push("}");
}

// Two-char escapes required by RFC 8785 minimal escaping (serialization.md §4).
const SHORT_ESCAPES: Record<number, string> = {
  0x08: "\\b",
  0x09: "\\t",
  0x0a: "\\n",
  0x0c: "\\f",
  0x0d: "\\r",
  0x22: '\\"',
  0x5c: "\\\\",
};

function serializeString(s: string, out: string[]): void {
  const norm = s.normalize("NFC");
  let buf = '"';
  for (const ch of norm) {
    const cp = ch.codePointAt(0)!;
    const esc = SHORT_ESCAPES[cp];
    if (esc !== undefined) {
      buf += esc;
    } else if (cp < 0x20) {
      buf += "\\u" + cp.toString(16).padStart(4, "0"); // lowercase hex (§4)
    } else {
      buf += ch;
    }
  }
  buf += '"';
  out.push(buf);
}
