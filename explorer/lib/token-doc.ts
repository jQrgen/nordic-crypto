"use client";

// Fetches a token's own metadata document from its document_url for display. Nothing is stored.
// The browser fetches directly; if that fails (usually CORS) it retries through the explorer's
// pass-through proxy (deploy/doc-proxy.mjs, served at /doc-proxy).

const MAX_BYTES = 256 * 1024;
export const DOC_PROXY = "/doc-proxy?url=";

export type TokenDoc = {
  url: string;
  via: "direct" | "proxy";
  json: unknown;
  meta: Record<string, unknown> | null;
  hash: "match" | "mismatch" | "unknown";
};

export function safeHttpUrl(value: unknown, base?: string): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim(), base);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

async function getText(url: string): Promise<string> {
  const res = await fetch(url, { signal: AbortSignal.timeout(8000), credentials: "omit", redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  if (buf.byteLength > MAX_BYTES) throw new Error("Document too large");
  return new TextDecoder().decode(buf);
}

// Nexa token documents are hashed over the bytes from the first "{" to the last "}".
// Rostrum reports document_hash as the SHA-256 hex; the raw OP_RETURN carries it byte-reversed.
async function checkHash(text: string, expected: string | null): Promise<TokenDoc["hash"]> {
  if (!expected || !/^[0-9a-f]{64}$/i.test(expected) || !globalThis.crypto?.subtle) return "unknown";
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start < 0 || end < start) return "mismatch";
  const bytes = new TextEncoder().encode(text.slice(start, end + 1));
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const hex = Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
  const rev = Array.from(digest.reverse(), (b) => b.toString(16).padStart(2, "0")).join("");
  const want = expected.toLowerCase();
  return hex === want || rev === want ? "match" : "mismatch";
}

export async function fetchTokenDoc(documentUrl: string | null, documentHash: string | null): Promise<TokenDoc | null> {
  const url = safeHttpUrl(documentUrl);
  if (!url) return null;
  let text: string;
  let via: TokenDoc["via"] = "direct";
  try {
    text = await getText(url);
  } catch {
    via = "proxy";
    text = await getText(DOC_PROXY + encodeURIComponent(url));
  }
  let json: unknown = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  const head = Array.isArray(json) ? json[0] : json;
  const meta = head && typeof head === "object" && !Array.isArray(head) ? (head as Record<string, unknown>) : null;
  return { url, via, json, meta, hash: await checkHash(text, documentHash) };
}
