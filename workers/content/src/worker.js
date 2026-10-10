// Nordic Crypto story and event review, and a read-only copy of the public API.
//
// The static site on GitHub Pages stays the public site. This Worker is optional.
// GET  /api/v1/news.json, /api/v1/news/:id.json
// GET  /api/v1/events.json, /api/v1/events/:id.json
// GET  /api/v1/sources.json
// GET  /api/review/pending          Authorization: Bearer EDITOR_TOKEN
// POST /api/review                  the same token; approve or reject in D1
//
// Teasers, match rules, reject reasons and the private term list are not returned.
// Nothing is logged. EDITOR_TOKEN and GITHUB_DISPATCH_TOKEN are Worker secrets.

export const PUBLIC_STORY_KEYS = [
  "id", "url", "title", "title_en", "title_i18n", "source", "source_name", "country",
  "language", "published", "topics", "summary", "summary_i18n", "paywall", "links", "status",
];

export const PUBLIC_EVENT_KEYS = [
  "id", "title", "title_orig", "start", "end", "place", "city", "country", "online",
  "organiser", "url", "source", "source_url", "paid", "sponsored", "note", "note_i18n",
  "description", "status",
];

const STORY_SELECT = "SELECT id, payload, review_status, item_status, reviewed_by, reviewed_at, review_note, summary, url, title, country, published_at, created_at FROM stories WHERE id = ?";
const EVENT_SELECT = "SELECT id, payload, review_status, item_status, reviewed_by, reviewed_at, review_note, url, title, country, start_at, created_at FROM events WHERE id = ?";

export function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const left = enc.encode(String(a || ""));
  const right = enc.encode(String(b || ""));
  const length = Math.max(left.length, right.length);
  let mismatch = left.length === right.length ? 0 : 1;
  for (let i = 0; i < length; i++) mismatch |= (left[i] || 0) ^ (right[i] || 0);
  return mismatch === 0;
}

export function editorAuthorized(request, token) {
  if (!token) return false;
  const header = request.headers.get("authorization") || "";
  const match = header.match(/^Bearer\s+(\S+)\s*$/i);
  if (!match) return false;
  return timingSafeEqual(match[1], token);
}

export function publicStory(payload) {
  if (!payload || payload.status !== "published") return null;
  if (!String(payload.summary || "").trim()) return null;
  const copy = { ...payload };
  if ((copy.summary_i18n_review || "approved") !== "approved") delete copy.summary_i18n;
  const out = { status: "published" };
  for (const key of PUBLIC_STORY_KEYS) {
    if (key === "status") continue;
    if (copy[key] !== undefined && copy[key] !== null) out[key] = copy[key];
  }
  return out;
}

export function publicEvent(payload, reviewStatus) {
  if (reviewStatus !== "approved" || !payload) return null;
  const out = { status: "published" };
  for (const key of PUBLIC_EVENT_KEYS) {
    if (key === "status") continue;
    if (payload[key] !== undefined && payload[key] !== null) out[key] = payload[key];
  }
  return out;
}

export function publicSource(payload) {
  const out = {};
  for (const key of ["id", "name", "country", "kind", "url", "enabled", "language", "paywall"]) {
    if (payload && payload[key] !== undefined && payload[key] !== null) out[key] = payload[key];
  }
  return out;
}

function parsePayload(row) {
  if (!row) return null;
  if (typeof row.payload === "string") return JSON.parse(row.payload);
  return row.payload || null;
}

export function applyStoryReview(row, body, actor, at) {
  const payload = parsePayload(row);
  if (!payload) return { error: "story has no payload", status: 500 };
  const action = body && body.action;
  if (action === "approve") {
    const summary = String(body.summary || "").trim();
    if (!summary) return { error: "a story approval needs a summary", status: 400 };
    payload.status = "published";
    payload.summary = summary;
    payload.approved_by = actor;
    payload.approved_at = at;
    delete payload.reject_reason;
    for (const key of ["title_en", "topics", "summary_i18n", "summary_i18n_source", "summary_i18n_review", "title_i18n", "title_i18n_source", "primary_source"]) {
      if (body[key] !== undefined && body[key] !== null) payload[key] = body[key];
    }
    return {
      payload,
      review_status: "approved",
      item_status: "published",
      summary,
      reviewed_by: actor,
      reviewed_at: at,
      review_note: null,
    };
  }
  if (action === "reject") {
    payload.status = "rejected";
    payload.summary = null;
    delete payload.approved_by;
    delete payload.approved_at;
    if (body.reason) payload.reject_reason = body.reason;
    return {
      payload,
      review_status: "rejected",
      item_status: "rejected",
      summary: null,
      reviewed_by: actor,
      reviewed_at: at,
      review_note: body.reason || null,
    };
  }
  return { error: "action must be approve or reject", status: 400 };
}

export function applyEventReview(row, body, actor, at) {
  const payload = parsePayload(row);
  if (!payload) return { error: "event has no payload", status: 500 };
  const action = body && body.action;
  if (action === "approve") {
    if (body.note !== undefined) payload.note = body.note;
    if (body.note_i18n !== undefined) payload.note_i18n = body.note_i18n;
    return {
      payload,
      review_status: "approved",
      item_status: "published",
      reviewed_by: actor,
      reviewed_at: at,
      review_note: null,
    };
  }
  if (action === "reject") {
    payload.status = "rejected";
    if (body.reason) payload.reject_reason = body.reason;
    return {
      payload,
      review_status: "rejected",
      item_status: "rejected",
      reviewed_by: actor,
      reviewed_at: at,
      review_note: body.reason || null,
    };
  }
  return { error: "action must be approve or reject", status: 400 };
}

function json(data, status, extra) {
  const headers = {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "cache-control": extra && extra.cache ? extra.cache : "no-store",
  };
  return new Response(JSON.stringify(data), { status, headers });
}

function storyIdFrom(pathname) {
  const match = pathname.match(/^\/api\/v1\/news\/([A-Za-z0-9]+)(?:\.json)?$/);
  return match ? match[1] : null;
}

function eventIdFrom(pathname) {
  const match = pathname.match(/^\/api\/v1\/events\/([A-Za-z0-9]+)(?:\.json)?$/);
  return match ? match[1] : null;
}

async function listNews(db) {
  const out = await db.prepare(
    "SELECT payload FROM stories WHERE review_status = 'approved' AND item_status = 'published' ORDER BY published_at DESC"
  ).all();
  const items = [];
  for (const row of out.results || []) {
    const pub = publicStory(JSON.parse(row.payload));
    if (pub) items.push(pub);
  }
  return items;
}

async function listEvents(db) {
  const out = await db.prepare(
    "SELECT payload, review_status FROM events WHERE review_status = 'approved' ORDER BY start_at"
  ).all();
  const events = [];
  for (const row of out.results || []) {
    const pub = publicEvent(JSON.parse(row.payload), row.review_status);
    if (pub) events.push(pub);
  }
  return events;
}

async function dispatchRedeploy(env) {
  if (!env.GITHUB_DISPATCH_TOKEN || !env.GITHUB_REPOSITORY) return "scheduled";
  const response = await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/dispatches`, {
    method: "POST",
    headers: {
      authorization: "Bearer " + env.GITHUB_DISPATCH_TOKEN,
      accept: "application/vnd.github+json",
      "content-type": "application/json",
      "user-agent": "nordic-crypto-content",
    },
    body: JSON.stringify({ event_type: "d1-approved" }),
  });
  return response.ok ? "dispatched" : "scheduled";
}

export async function handle(request, env) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "authorization, content-type",
        "access-control-max-age": "86400",
      },
    });
  }
  if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
    return json({ ok: true, service: "nordic-crypto-content" }, 200, { cache: "no-store" });
  }
  const db = env.DB;
  if (!db) return json({ error: "database is not bound" }, 500);

  if (request.method === "GET" && url.pathname === "/api/v1/news.json") {
    return json({ items: await listNews(db) }, 200, { cache: "public, max-age=300" });
  }
  const storyId = storyIdFrom(url.pathname);
  if (request.method === "GET" && storyId) {
    const row = await db.prepare(STORY_SELECT).bind(storyId).first();
    const pub = row && row.review_status === "approved" ? publicStory(JSON.parse(row.payload)) : null;
    if (!pub) return json({ error: "not found" }, 404);
    return json(pub, 200, { cache: "public, max-age=300" });
  }
  if (request.method === "GET" && url.pathname === "/api/v1/events.json") {
    return json({ events: await listEvents(db) }, 200, { cache: "public, max-age=300" });
  }
  const eventId = eventIdFrom(url.pathname);
  if (request.method === "GET" && eventId) {
    const row = await db.prepare(EVENT_SELECT).bind(eventId).first();
    const pub = row ? publicEvent(JSON.parse(row.payload), row.review_status) : null;
    if (!pub) return json({ error: "not found" }, 404);
    return json(pub, 200, { cache: "public, max-age=300" });
  }
  if (request.method === "GET" && url.pathname === "/api/v1/sources.json") {
    const out = await db.prepare(
      "SELECT payload FROM sources WHERE review_status = 'approved' ORDER BY kind, id"
    ).all();
    const sources = (out.results || []).map((row) => publicSource(JSON.parse(row.payload)));
    return json({ sources }, 200, { cache: "public, max-age=300" });
  }

  if (url.pathname === "/api/review/pending" || url.pathname === "/api/review") {
    if (!env.EDITOR_TOKEN) return json({ error: "editor token is not set" }, 503);
    if (!editorAuthorized(request, env.EDITOR_TOKEN)) return json({ error: "unauthorized" }, 401);
  }

  if (request.method === "GET" && url.pathname === "/api/review/pending") {
    const stories = await db.prepare(
      "SELECT id, title, country, url, published_at FROM stories WHERE review_status = 'pending' AND item_status = 'pending' ORDER BY published_at DESC"
    ).all();
    const events = await db.prepare(
      "SELECT id, title, country, url, start_at FROM events WHERE review_status = 'pending' AND item_status = 'pending' ORDER BY start_at"
    ).all();
    return json({ stories: stories.results || [], events: events.results || [] }, 200);
  }

  if (request.method === "POST" && url.pathname === "/api/review") {
    let body;
    try {
      body = await request.json();
    } catch (err) {
      return json({ error: "body must be JSON" }, 400);
    }
    if (!body || (body.kind !== "story" && body.kind !== "event") || !body.id) {
      return json({ error: "kind (story or event) and id are required" }, 400);
    }
    const actor = String(body.by || "Nordic Crypto redaktør");
    const at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    if (body.kind === "story") {
      const row = await db.prepare(STORY_SELECT).bind(body.id).first();
      if (!row) return json({ error: "no story" }, 404);
      const plan = applyStoryReview(row, body, actor, at);
      if (plan.error) return json({ error: plan.error }, plan.status);
      const text = JSON.stringify(plan.payload);
      await db.prepare(
        "UPDATE stories SET payload = ?, content_hash = ?, review_status = ?, item_status = ?, summary = ?, reviewed_by = ?, reviewed_at = ?, review_note = ?, updated_at = ?, title = ?, url = ? WHERE id = ?"
      ).bind(
        text, "", plan.review_status, plan.item_status, plan.summary, plan.reviewed_by, plan.reviewed_at,
        plan.review_note, at, plan.payload.title || null, plan.payload.url || row.url, body.id,
      ).run();
      await db.prepare(
        "INSERT INTO review_audit (kind, item_id, action, actor, at, detail) VALUES ('story', ?, ?, ?, ?, ?)"
      ).bind(body.id, body.action, actor, at, plan.review_status).run();
      let redeploy = "scheduled";
      try {
        redeploy = await dispatchRedeploy(env);
      } catch (err) {
        redeploy = "scheduled";
      }
      return json({ ok: true, kind: "story", id: body.id, review_status: plan.review_status, redeploy }, 200);
    }
    const row = await db.prepare(EVENT_SELECT).bind(body.id).first();
    if (!row) return json({ error: "no event" }, 404);
    const plan = applyEventReview(row, body, actor, at);
    if (plan.error) return json({ error: plan.error }, plan.status);
    const text = JSON.stringify(plan.payload);
    await db.prepare(
      "UPDATE events SET payload = ?, review_status = ?, item_status = ?, reviewed_by = ?, reviewed_at = ?, review_note = ?, updated_at = ?, title = ? WHERE id = ?"
    ).bind(
      text, plan.review_status, plan.item_status, plan.reviewed_by, plan.reviewed_at, plan.review_note, at,
      plan.payload.title || null, body.id,
    ).run();
    await db.prepare(
      "INSERT INTO review_audit (kind, item_id, action, actor, at, detail) VALUES ('event', ?, ?, ?, ?, ?)"
    ).bind(body.id, body.action, actor, at, plan.review_status).run();
    let redeploy = "scheduled";
    try {
      redeploy = await dispatchRedeploy(env);
    } catch (err) {
      redeploy = "scheduled";
    }
    return json({ ok: true, kind: "event", id: body.id, review_status: plan.review_status, redeploy }, 200);
  }

  return json({ error: "not found" }, 404);
}

export default { fetch: (request, env) => handle(request, env) };
