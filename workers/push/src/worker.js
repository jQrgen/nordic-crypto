// Nordic Crypto browser push. Stores only a push subscription (endpoint, keys,
// language, chosen countries). No IP address, no user agent, no name, no email.
// One publish sends at most one notification per subscription.
import { COUNTRIES, LANGS, copyFor } from "./copy.js";
import { sendWebPush } from "./webpush.js";

const FEED_KEY = "feed:batches";
const MAX_BATCHES = 30;
const MAX_STORIES = 40;
const MAX_BODY = 48 * 1024;
const ORIGINS = new Set([
  "https://cryptonordic.no",
  "https://www.cryptonordic.no",
  "https://jqrgen.github.io",
]);

export function originAllowed(origin) {
  if (!origin) return false;
  if (ORIGINS.has(origin)) return true;
  return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(origin);
}

function json(data, status, origin, extra) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    ...(extra || {}),
  };
  if (origin && originAllowed(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }
  return new Response(JSON.stringify(data), { status, headers });
}

function clip(s, n) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  if (t.length <= n) return t;
  const cut = t.slice(0, n).replace(/\s+\S*$/, "");
  return (cut || t.slice(0, n)).replace(/[.,;:]+$/, "") + "…";
}

function pick(map, lang, fallback) {
  if (map && typeof map === "object") {
    const own = map[lang];
    if (typeof own === "string" && own.trim()) return own.trim();
    const en = map.en;
    if (typeof en === "string" && en.trim()) return en.trim();
  }
  return (fallback || "").trim();
}

export function notificationFor(stories, lang) {
  const copy = copyFor(lang);
  if (stories.length === 1) {
    const s = stories[0];
    const title = clip(pick(s.titles, lang, s.title), 120) || copy.one;
    const body = clip(pick(s.summaries, lang, s.summary), 200);
    return { title, body, url: s.url, lang, tag: "nordic-crypto-latest" };
  }
  const shown = stories.slice(0, 3).map((s) => clip(pick(s.titles, lang, s.title), 80)).filter(Boolean);
  let body = shown.join(" · ");
  if (stories.length > shown.length) body += (body ? " · " : "") + copy.more.replace("{n}", String(stories.length - shown.length));
  const home = lang === "en" ? "https://cryptonordic.no/" : `https://cryptonordic.no/${lang}/`;
  return {
    title: copy.many.replace("{n}", String(stories.length)),
    body: clip(body, 240),
    url: home,
    lang,
    tag: "nordic-crypto-latest",
  };
}

export function storiesFor(sub, stories) {
  const want = Array.isArray(sub.countries) ? sub.countries : [];
  if (!want.length) return stories.slice();
  const set = new Set(want);
  return stories.filter((s) => s.country && set.has(s.country));
}

function cleanStory(raw) {
  if (!raw || typeof raw !== "object") return null;
  const url = typeof raw.url === "string" ? raw.url.trim() : "";
  if (!/^https:\/\/[^\s]+$/.test(url) || url.length > 500) return null;
  const title = clip(raw.title, 180);
  if (!title) return null;
  const summary = clip(raw.summary, 280);
  const country = COUNTRIES.includes(raw.country) ? raw.country : null;
  const titles = {};
  const summaries = {};
  if (raw.titles && typeof raw.titles === "object") {
    for (const lang of LANGS) {
      if (typeof raw.titles[lang] === "string" && raw.titles[lang].trim()) titles[lang] = clip(raw.titles[lang], 180);
    }
  }
  if (!titles.en) titles.en = title;
  if (raw.summaries && typeof raw.summaries === "object") {
    for (const lang of LANGS) {
      if (typeof raw.summaries[lang] === "string" && raw.summaries[lang].trim()) summaries[lang] = clip(raw.summaries[lang], 280);
    }
  }
  if (summary && !summaries.en) summaries.en = summary;
  return { title, summary, url, country, titles, summaries };
}

function cleanCountries(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return [];
  const out = [];
  for (const c of raw) {
    if (c === "ALL") return [];
    if (COUNTRIES.includes(c) && !out.includes(c)) out.push(c);
  }
  return out;
}

function cleanLang(raw) {
  return LANGS.includes(raw) ? raw : "en";
}

async function sha256hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function subKey(endpoint) {
  return "sub:" + await sha256hex(endpoint);
}

function validEndpoint(endpoint) {
  if (typeof endpoint !== "string" || endpoint.length < 20 || endpoint.length > 2000) return false;
  try {
    const u = new URL(endpoint);
    return u.protocol === "https:";
  } catch {
    return false;
  }
}

function validKey(s, min, max) {
  return typeof s === "string" && /^[A-Za-z0-9_-]+$/.test(s) && s.length >= min && s.length <= max;
}

async function readJson(request) {
  const len = Number(request.headers.get("content-length") || 0);
  if (len > MAX_BODY) return { error: "too_large" };
  const text = await request.text();
  if (text.length > MAX_BODY) return { error: "too_large" };
  try { return { value: JSON.parse(text) }; }
  catch { return { error: "bad_json" }; }
}

async function tokensEqual(a, b) {
  const enc = new TextEncoder();
  const da = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(String(a))));
  const db = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(String(b))));
  let diff = 0;
  for (let i = 0; i < da.length; i++) diff |= da[i] ^ db[i];
  return diff === 0 && String(a).length > 0 && String(b).length > 0;
}

function bearer(request) {
  const h = request.headers.get("authorization") || "";
  const m = /^Bearer\s+(\S+)$/.exec(h);
  return m ? m[1] : "";
}

async function eachSub(kv, fn) {
  let cursor;
  do {
    const page = await kv.list({ prefix: "sub:", cursor, limit: 200 });
    for (const key of page.keys) {
      const raw = await kv.get(key.name);
      if (!raw) continue;
      let sub;
      try { sub = JSON.parse(raw); } catch { continue; }
      await fn(key.name, sub);
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
}

async function saveBatch(kv, stories) {
  let prev = [];
  const raw = await kv.get(FEED_KEY);
  if (raw) {
    try { prev = JSON.parse(raw).batches || []; } catch { prev = []; }
  }
  const batch = {
    id: crypto.randomUUID(),
    published_at: new Date().toISOString(),
    stories,
  };
  const batches = [batch, ...prev].slice(0, MAX_BATCHES);
  await kv.put(FEED_KEY, JSON.stringify({ batches }));
  return batch;
}

export function feedDocument(batches) {
  return {
    service: "nordic-crypto-push",
    generated_from: "the same list sent as one browser notification per publish",
    apns: "not implemented",
    note: "An iOS app can poll this feed. Apple Push Notification service (APNs) is out of scope. Safari on iOS 16.4 or newer can use the website's browser notifications after the site is added to the Home Screen; that path is Web Push, not APNs.",
    privacy: "This feed is the public story list only. Push subscriptions are not included.",
    batches: batches || [],
  };
}

async function handlePublish(request, env) {
  if (!env.PUBLISH_TOKEN || !(await tokensEqual(bearer(request), env.PUBLISH_TOKEN))) {
    return json({ ok: false, error: "unauthorized" }, 401, null);
  }
  if (!env.VAPID_PUBLIC_KEY || !env.VAPID_PRIVATE_KEY || !env.VAPID_SUBJECT) {
    return json({ ok: false, error: "not_configured" }, 503, null);
  }
  const parsed = await readJson(request);
  if (parsed.error) return json({ ok: false, error: parsed.error }, 400, null);
  const list = Array.isArray(parsed.value && parsed.value.stories) ? parsed.value.stories : null;
  if (!list) return json({ ok: false, error: "stories_required" }, 400, null);
  const stories = [];
  for (const raw of list) {
    if (stories.length >= MAX_STORIES) break;
    const s = cleanStory(raw);
    if (s) stories.push(s);
  }
  if (!stories.length) return json({ ok: false, error: "no_stories" }, 400, null);
  const batch = await saveBatch(env.SUBSCRIPTIONS, stories);
  let sent = 0;
  let skipped = 0;
  let removed = 0;
  let failed = 0;
  await eachSub(env.SUBSCRIPTIONS, async (key, sub) => {
    const mine = storiesFor(sub, stories);
    if (!mine.length) { skipped++; return; }
    const note = notificationFor(mine, cleanLang(sub.lang));
    const bytes = new TextEncoder().encode(JSON.stringify(note));
    try {
      const res = await sendWebPush(sub, bytes, env);
      if (res.status === 404 || res.status === 410) {
        await env.SUBSCRIPTIONS.delete(key);
        removed++;
      } else if (res.ok) sent++;
      else failed++;
    } catch {
      failed++;
    }
  });
  return json({
    ok: true,
    batch_id: batch.id,
    stories: stories.length,
    sent,
    skipped,
    removed,
    failed,
  }, 200, null);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("origin");
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      if (!originAllowed(origin)) return new Response(null, { status: 403 });
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": origin,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Max-Age": "86400",
          Vary: "Origin",
        },
      });
    }

    if (request.method === "GET" && (path === "/api/push/health" || path === "/health")) {
      return json({ ok: true, service: "nordic-crypto-push" }, 200, origin);
    }

    if (request.method === "GET" && path === "/api/push/config") {
      if (!env.VAPID_PUBLIC_KEY) return json({ ok: false, error: "not_configured" }, 503, origin);
      return json({
        ok: true,
        vapid_public_key: env.VAPID_PUBLIC_KEY,
        countries: COUNTRIES,
      }, 200, origin);
    }

    if (request.method === "GET" && (path === "/api/push/feed.json" || path === "/api/push/feed")) {
      let batches = [];
      if (env.SUBSCRIPTIONS) {
        const raw = await env.SUBSCRIPTIONS.get(FEED_KEY);
        if (raw) {
          try { batches = JSON.parse(raw).batches || []; } catch { batches = []; }
        }
      }
      return json(feedDocument(batches), 200, origin);
    }

    if (request.method === "POST" && path === "/api/push/subscribe") {
      if (origin && !originAllowed(origin)) return json({ ok: false, error: "origin" }, 403, null);
      if (!origin) return json({ ok: false, error: "origin" }, 403, null);
      const parsed = await readJson(request);
      if (parsed.error) return json({ ok: false, error: parsed.error }, 400, origin);
      const body = parsed.value || {};
      const endpoint = body.endpoint;
      const keys = body.keys || {};
      if (!validEndpoint(endpoint) || !validKey(keys.p256dh, 80, 120) || !validKey(keys.auth, 16, 32)) {
        return json({ ok: false, error: "bad_subscription" }, 400, origin);
      }
      const record = {
        endpoint,
        keys: { p256dh: keys.p256dh, auth: keys.auth },
        lang: cleanLang(body.lang),
        countries: cleanCountries(body.countries),
        updated_at: new Date().toISOString(),
      };
      await env.SUBSCRIPTIONS.put(await subKey(endpoint), JSON.stringify(record));
      return json({ ok: true }, 200, origin);
    }

    if (request.method === "POST" && path === "/api/push/unsubscribe") {
      if (!origin || !originAllowed(origin)) return json({ ok: false, error: "origin" }, 403, null);
      const parsed = await readJson(request);
      if (parsed.error) return json({ ok: false, error: parsed.error }, 400, origin);
      const endpoint = parsed.value && parsed.value.endpoint;
      if (!validEndpoint(endpoint)) return json({ ok: false, error: "bad_subscription" }, 400, origin);
      await env.SUBSCRIPTIONS.delete(await subKey(endpoint));
      return json({ ok: true }, 200, origin);
    }

    if (request.method === "POST" && path === "/api/push/publish") {
      return handlePublish(request, env);
    }

    return json({ ok: false, error: "not_found" }, 404, origin);
  },
};
