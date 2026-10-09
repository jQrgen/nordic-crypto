// Admin requests carry Authorization: Bearer <ADMIN_TOKEN>. The compare hashes
// both strings and then walks every digest byte, so it does not stop at the
// first mismatch. A missing or short secret fails closed.

const MIN_TOKEN = 16;

export async function tokensEqual(expected, presented) {
  const enc = new TextEncoder();
  const raw = String(presented ?? "");
  const tooLong = raw.length > 256;
  const [leftBuf, rightBuf] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(String(expected ?? ""))),
    crypto.subtle.digest("SHA-256", enc.encode(tooLong ? raw.slice(0, 256) : raw)),
  ]);
  const left = new Uint8Array(leftBuf);
  const right = new Uint8Array(rightBuf);
  let diff = tooLong ? 1 : 0;
  for (let i = 0; i < left.length; i++) diff |= left[i] ^ right[i];
  return diff === 0;
}

export function presentedToken(req) {
  const header = (req && req.headers && req.headers.get("Authorization")) || "";
  const match = /^Bearer\s+(\S+)\s*$/i.exec(header);
  return match ? match[1] : "";
}

export async function adminAuthorized(env, req) {
  const secret = env && typeof env.ADMIN_TOKEN === "string" ? env.ADMIN_TOKEN.trim() : "";
  if (secret.length < MIN_TOKEN) return false;
  return tokensEqual(secret, presentedToken(req));
}
