// Pure-JS Bitcoin Cash primitives. No WebAssembly: Workers reject WASM
// compiled from a byte array ("Wasm code generation disallowed by embedder"),
// which is how @bitauth/libauth v3 loads secp256k1 and the hash functions.

import { hmac } from "@noble/hashes/hmac.js";
import { ripemd160 } from "@noble/hashes/legacy.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { secp256k1 } from "@noble/curves/secp256k1";

const Point = secp256k1.ProjectivePoint;
const CURVE_N = secp256k1.CURVE.n;
const CURVE_P = secp256k1.CURVE.p;
const SCHNORR_ALGO = new TextEncoder().encode("Schnorr+SHA256  ");

const CASH_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";
const BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const CASH_GENERATOR = [0x98f2bc8e61n, 0x79b76d99e2n, 0xf33e5fb3c4n, 0xae2eabe2a8n, 0x1e4f43e470n];
const LENGTH_TO_BITS = { 20: 0, 24: 1, 28: 2, 32: 3, 40: 4, 48: 5, 56: 6, 64: 7 };
const BITS_TO_LENGTH = [20, 24, 28, 32, 40, 48, 56, 64];

export function concat(parts) {
  let n = 0;
  for (const p of parts) n += p.length;
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

export function reversed(bytes) {
  const out = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) out[i] = bytes[bytes.length - 1 - i];
  return out;
}

export function hexToBytes(hex) {
  const s = String(hex).replace(/^0x/i, "").trim();
  if (s.length % 2 !== 0 || /[^0-9a-fA-F]/.test(s)) {
    const err = new Error("bad_hex");
    err.code = "bad_hex";
    throw err;
  }
  const out = new Uint8Array(s.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = Number.parseInt(s.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export function bytesToHex(bytes) {
  let s = "";
  for (const b of bytes) s += b.toString(16).padStart(2, "0");
  return s;
}

export function sha256d(bytes) {
  return sha256(sha256(bytes));
}

export function hash160(bytes) {
  return ripemd160(sha256(bytes));
}

export function u32le(n) {
  const v = Number(n) >>> 0;
  return Uint8Array.of(v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255);
}

export function u64le(n) {
  let v = BigInt(n);
  const out = new Uint8Array(8);
  for (let i = 0; i < 8; i++) {
    out[i] = Number(v & 255n);
    v >>= 8n;
  }
  return out;
}

export function compactUint(value) {
  const v = BigInt(value);
  if (v < 0n) {
    const err = new Error("bad_compact");
    err.code = "bad_compact";
    throw err;
  }
  if (v <= 252n) return Uint8Array.of(Number(v));
  if (v <= 65535n) return Uint8Array.of(253, Number(v & 255n), Number((v >> 8n) & 255n));
  if (v <= 4294967295n) return concat([Uint8Array.of(254), u32le(Number(v))]);
  return concat([Uint8Array.of(255), u64le(v)]);
}

function pushData(data) {
  if (data.length < 76) return concat([Uint8Array.of(data.length), data]);
  if (data.length <= 0xff) return concat([Uint8Array.of(0x4c, data.length), data]);
  return concat([Uint8Array.of(0x4d, data.length & 255, (data.length >> 8) & 255), data]);
}

export function p2pkhLock(hash) {
  return concat([Uint8Array.of(0x76, 0xa9, 0x14), hash, Uint8Array.of(0x88, 0xac)]);
}

export function lockingBytecode(typeBits, hash) {
  const token = typeBits === 2 || typeBits === 3;
  const p2sh = typeBits === 1 || typeBits === 3;
  if (!p2sh && hash.length === 20) return p2pkhLock(hash);
  if (p2sh && hash.length === 20) return concat([Uint8Array.of(0xa9, 0x14), hash, Uint8Array.of(0x87)]);
  if (p2sh && hash.length === 32) return concat([Uint8Array.of(0xaa, 0x20), hash, Uint8Array.of(0x87)]);
  const err = new Error("bad_address");
  err.code = "bad_address";
  err.token = token;
  throw err;
}

function convertBits(data, from, to, pad) {
  let acc = 0;
  let bits = 0;
  const out = [];
  const maxv = (1 << to) - 1;
  for (const value of data) {
    if (value < 0 || value >> from !== 0) return null;
    acc = (acc << from) | value;
    bits += from;
    while (bits >= to) {
      bits -= to;
      out.push((acc >> bits) & maxv);
    }
  }
  if (pad) {
    if (bits > 0) out.push((acc << (to - bits)) & maxv);
  } else if (bits >= from || ((acc << (to - bits)) & maxv) !== 0) {
    return null;
  }
  return out;
}

function cashPolymod(values) {
  let c = 1n;
  for (const d of values) {
    const c0 = c >> 35n;
    c = ((c & 0x07ffffffffn) << 5n) ^ BigInt(d);
    for (let i = 0; i < 5; i++) {
      if ((c0 >> BigInt(i)) & 1n) c ^= CASH_GENERATOR[i];
    }
  }
  return c ^ 1n;
}

function prefixExpand(prefix) {
  const out = [];
  for (const ch of prefix) out.push(ch.charCodeAt(0) & 31);
  out.push(0);
  return out;
}

export function encodeCashAddr(prefix, typeBits, payload) {
  const sizeBits = LENGTH_TO_BITS[payload.length];
  if (sizeBits === undefined || typeBits < 0 || typeBits > 15) {
    const err = new Error("bad_address");
    err.code = "bad_address";
    throw err;
  }
  const version = (typeBits << 3) | sizeBits;
  const data = convertBits([version, ...payload], 8, 5, true);
  const checksum = cashPolymod([...prefixExpand(prefix), ...data, 0, 0, 0, 0, 0, 0, 0, 0]);
  const words = data.slice();
  for (let i = 0; i < 8; i++) words.push(Number((checksum >> BigInt(5 * (7 - i))) & 31n));
  let body = "";
  for (const w of words) body += CASH_CHARSET[w];
  return prefix + ":" + body;
}

export function decodeCashAddr(address) {
  const raw = String(address).trim();
  const lower = raw.toLowerCase();
  const colon = lower.indexOf(":");
  if (colon < 1) return null;
  const prefix = lower.slice(0, colon);
  const body = lower.slice(colon + 1);
  if (!body || body !== raw.slice(colon + 1).toLowerCase()) return null;
  const data = [];
  for (const ch of body) {
    const v = CASH_CHARSET.indexOf(ch);
    if (v < 0) return null;
    data.push(v);
  }
  if (cashPolymod([...prefixExpand(prefix), ...data]) !== 0n) return null;
  const payload = convertBits(data.slice(0, -8), 5, 8, false);
  if (!payload || payload.length < 2) return null;
  const version = payload[0];
  if (version & 0x80) return null;
  const typeBits = (version >>> 3) & 15;
  const sizeBits = version & 7;
  const hash = Uint8Array.from(payload.slice(1));
  if (BITS_TO_LENGTH[sizeBits] !== hash.length) return null;
  return { prefix, typeBits, hash };
}

function base58Decode(text) {
  let num = 0n;
  for (const ch of text) {
    const v = BASE58_ALPHABET.indexOf(ch);
    if (v < 0) return null;
    num = num * 58n + BigInt(v);
  }
  let hex = num.toString(16);
  if (hex.length % 2) hex = "0" + hex;
  const bytes = hex === "0" ? new Uint8Array() : hexToBytes(hex);
  let zeros = 0;
  for (const ch of text) {
    if (ch !== "1") break;
    zeros += 1;
  }
  const out = new Uint8Array(zeros + bytes.length);
  out.set(bytes, zeros);
  return out;
}

export function decodeWif(text) {
  const decoded = base58Decode(String(text).trim());
  if (!decoded || decoded.length < 5) return null;
  const data = decoded.subarray(0, decoded.length - 4);
  const check = decoded.subarray(decoded.length - 4);
  const hash = sha256d(data);
  for (let i = 0; i < 4; i++) if (hash[i] !== check[i]) return null;
  const version = data[0];
  const payload = data.subarray(1);
  const compressed = payload.length === 33 && payload[32] === 1;
  const privateKey = compressed ? payload.subarray(0, 32) : payload;
  if (privateKey.length !== 32) return null;
  if (version !== 0x80 && version !== 0xef) return null;
  return privateKey;
}

export function compressedPublicKey(privateKey) {
  return secp256k1.getPublicKey(privateKey, true);
}

function mod(a, m) {
  const r = a % m;
  return r >= 0n ? r : r + m;
}

function bytesToNum(bytes) {
  return BigInt("0x" + bytesToHex(bytes));
}

function numTo32(n) {
  return hexToBytes(mod(n, 1n << 256n).toString(16).padStart(64, "0"));
}

function legendre(y) {
  let e = (CURVE_P - 1n) / 2n;
  let base = mod(y, CURVE_P);
  let r = 1n;
  while (e > 0n) {
    if (e & 1n) r = (r * base) % CURVE_P;
    base = (base * base) % CURVE_P;
    e >>= 1n;
  }
  if (r === 1n) return 1;
  if (r === CURVE_P - 1n) return -1;
  return 0;
}

function hmacSha256(key, data) {
  return hmac(sha256, key, data);
}

function rfc6979Nonce(privateKey, messageHash) {
  let v = new Uint8Array(32).fill(1);
  let k = new Uint8Array(32);
  const bx = concat([privateKey, messageHash, SCHNORR_ALGO]);
  k = hmacSha256(k, concat([v, Uint8Array.of(0), bx]));
  v = hmacSha256(k, v);
  k = hmacSha256(k, concat([v, Uint8Array.of(1), bx]));
  v = hmacSha256(k, v);
  for (;;) {
    v = hmacSha256(k, v);
    const cand = bytesToNum(v);
    if (cand > 0n && cand < CURVE_N) return cand;
    k = hmacSha256(k, concat([v, Uint8Array.of(0)]));
    v = hmacSha256(k, v);
  }
}

// Bitcoin Cash Schnorr (May 2019), not BIP340. OP_CHECKSIG treats a 65-byte
// signature as this scheme: e = SHA256(r || compressed_pubkey || sighash).
export function schnorrSign(messageHash, privateKey) {
  const d = bytesToNum(privateKey);
  const pub = Point.BASE.multiply(d).toRawBytes(true);
  let k = rfc6979Nonce(privateKey, messageHash);
  let R = Point.BASE.multiply(k).toAffine();
  if (legendre(R.y) !== 1) {
    k = mod(-k, CURVE_N);
    R = { x: R.x, y: mod(-R.y, CURVE_P) };
  }
  const Br = numTo32(R.x);
  const e = mod(bytesToNum(sha256(concat([Br, pub, messageHash]))), CURVE_N);
  const s = mod(k + e * d, CURVE_N);
  return concat([Br, numTo32(s)]);
}

export function schnorrVerify(signature, messageHash, publicKey) {
  if (signature.length !== 64 || publicKey.length !== 33) return false;
  const r = bytesToNum(signature.subarray(0, 32));
  const s = bytesToNum(signature.subarray(32));
  if (r <= 0n || r >= CURVE_P || s >= CURVE_N) return false;
  let point;
  try {
    point = Point.fromHex(publicKey);
  } catch {
    return false;
  }
  const e = mod(bytesToNum(sha256(concat([signature.subarray(0, 32), point.toRawBytes(true), messageHash]))), CURVE_N);
  const R = Point.BASE.multiply(s).add(point.multiply(mod(-e, CURVE_N)));
  if (R.equals(Point.ZERO)) return false;
  const aff = R.toAffine();
  return aff.x === r && legendre(aff.y) === 1;
}

export function ecdsaRecoverable(messageHash, privateKey) {
  const sig = secp256k1.sign(messageHash, privateKey, { lowS: true });
  return { recovery: sig.recovery, compact: sig.toCompactRawBytes() };
}

export function recoverCompressed(compact, recovery, messageHash) {
  const sig = secp256k1.Signature.fromCompact(compact).addRecoveryBit(recovery);
  return sig.recoverPublicKey(messageHash).toRawBytes(true);
}

export function pushScript(items) {
  return concat(items.map(pushData));
}

export function bytesToBase64(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

export function base64ToBytes(text) {
  const bin = atob(String(text).trim());
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function randomPrivateKey() {
  return secp256k1.utils.randomPrivateKey();
}
