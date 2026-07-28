/**
 * A deterministic ZIP writer (STORE only — no compression).
 *
 * The audit export is an artifact, so it is held to the same determinism bar as every other
 * artifact-producing code path in this repo: the same inputs must produce byte-identical
 * output, forever, on any machine.
 *
 * How determinism is achieved:
 *  - No compression. DEFLATE output varies with library version and level; STORE does not,
 *    and it keeps every bundle file byte-identical to what `crp-verify` will read.
 *  - Fixed timestamp. Every entry is stamped 1980-01-01 00:00:00 (the DOS epoch), not the
 *    wall clock. Nothing here reads `Date.now()`.
 *  - Fixed entry order. Entries are written in the order given; `buildAuditZip` sorts them
 *    by path first.
 *  - No extra fields, no data descriptors, no UTF-8 name flag beyond the fixed one, no
 *    "created by" version drift.
 */

export interface ZipEntry {
  /** POSIX-relative path inside the archive. */
  path: string;
  bytes: Uint8Array;
}

const DOS_TIME = 0; // 00:00:00
const DOS_DATE = 0x0021; // 1980-01-01
const VERSION_MADE_BY = 20; // 2.0, MS-DOS — fixed, not derived from any runtime
const VERSION_NEEDED = 20;
const FLAG_UTF8 = 0x0800;
const METHOD_STORE = 0;

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    c = (CRC_TABLE[(c ^ bytes[i]!) & 0xff]! ^ (c >>> 8)) >>> 0;
  }
  return (c ^ 0xffffffff) >>> 0;
}

class ByteWriter {
  private parts: Uint8Array[] = [];
  length = 0;
  push(b: Uint8Array): void {
    this.parts.push(b);
    this.length += b.length;
  }
  u16(v: number): void {
    this.push(new Uint8Array([v & 0xff, (v >>> 8) & 0xff]));
  }
  u32(v: number): void {
    this.push(new Uint8Array([v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]));
  }
  concat(): Uint8Array {
    const out = new Uint8Array(this.length);
    let o = 0;
    for (const p of this.parts) {
      out.set(p, o);
      o += p.length;
    }
    return out;
  }
}

/**
 * Write a ZIP archive. Entry order is preserved exactly as given — sort before calling if you
 * want a canonical archive (`buildAuditZip` does).
 */
export function writeZip(entries: readonly ZipEntry[]): Uint8Array {
  const enc = new TextEncoder();
  const out = new ByteWriter();
  const central: Array<{ header: Uint8Array; offset: number }> = [];

  for (const entry of entries) {
    if (entry.path.length === 0) throw new Error("zip entry path must not be empty");
    if (entry.path.startsWith("/") || entry.path.includes("..")) {
      throw new Error(`unsafe zip entry path: ${entry.path}`);
    }
    const name = enc.encode(entry.path);
    const crc = crc32(entry.bytes);
    const size = entry.bytes.length;
    const offset = out.length;

    out.u32(0x04034b50); // local file header
    out.u16(VERSION_NEEDED);
    out.u16(FLAG_UTF8);
    out.u16(METHOD_STORE);
    out.u16(DOS_TIME);
    out.u16(DOS_DATE);
    out.u32(crc);
    out.u32(size);
    out.u32(size);
    out.u16(name.length);
    out.u16(0); // extra field length
    out.push(name);
    out.push(entry.bytes);

    const c = new ByteWriter();
    c.u32(0x02014b50); // central directory header
    c.u16(VERSION_MADE_BY);
    c.u16(VERSION_NEEDED);
    c.u16(FLAG_UTF8);
    c.u16(METHOD_STORE);
    c.u16(DOS_TIME);
    c.u16(DOS_DATE);
    c.u32(crc);
    c.u32(size);
    c.u32(size);
    c.u16(name.length);
    c.u16(0); // extra
    c.u16(0); // comment
    c.u16(0); // disk number start
    c.u16(0); // internal attrs
    c.u32(0o100644 << 16); // external attrs: regular file, 0644 — fixed, not from the fs
    c.u32(offset);
    c.push(name);
    central.push({ header: c.concat(), offset });
  }

  const centralStart = out.length;
  for (const c of central) out.push(c.header);
  const centralSize = out.length - centralStart;

  out.u32(0x06054b50); // end of central directory
  out.u16(0);
  out.u16(0);
  out.u16(central.length);
  out.u16(central.length);
  out.u32(centralSize);
  out.u32(centralStart);
  out.u16(0); // no archive comment
  return out.concat();
}
