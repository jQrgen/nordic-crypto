import test from "node:test";
import assert from "node:assert/strict";
import { applyEventReview, applyStoryReview, editorAuthorized, handle, publicEvent, publicSource, publicStory } from "../src/worker.js";

const TOKEN = "editor-token-for-tests";

function storyRow(extra = {}) {
  const payload = {
    id: "abc",
    url: "https://example.com/a",
    title: "Headline",
    status: "pending",
    summary: null,
    matched: ["\\bkrypto"],
    origin: "reader tip #4",
    reject_reason: "old",
    teaser_local_only: "do not publish this sentence",
    ...extra.payload,
  };
  return {
    id: "abc",
    url: payload.url,
    title: payload.title,
    payload: JSON.stringify(payload),
    review_status: "pending",
    item_status: "pending",
    ...extra.row,
  };
}

test("public story drops working fields", () => {
  const pub = publicStory({
    id: "abc",
    url: "https://example.com/a",
    title: "Headline",
    status: "published",
    summary: "Two sentences about the story. The second says what happened.",
    summary_i18n: { nn: "To setningar." },
    summary_i18n_review: "approved",
    matched: ["secret-pattern"],
    origin: "reader tip #4",
    reject_reason: "no",
    teaser_local_only: "copied teaser",
    approved_by: "Editor",
  });
  assert.equal(pub.summary.startsWith("Two"), true);
  assert.equal(pub.matched, undefined);
  assert.equal(pub.origin, undefined);
  assert.equal(pub.reject_reason, undefined);
  assert.equal(pub.teaser_local_only, undefined);
  assert.equal(pub.approved_by, undefined);
  assert.equal(publicStory({ status: "pending", summary: "x", id: "a" }), null);
  assert.equal(publicStory({
    status: "published",
    summary: "Kept.",
    summary_i18n: { nn: "Utkast." },
    summary_i18n_review: "pending",
    id: "a",
    title: "t",
  }).summary_i18n, undefined);
});

test("public event and source stay on the public fields", () => {
  const event = publicEvent({
    id: "e1",
    title: "Meetup",
    start: "2026-10-08T18:00:00+02:00",
    note: "Paid entry.",
    editor_title_en: "English",
    status: "pending",
  }, "approved");
  assert.equal(event.status, "published");
  assert.equal(event.note, "Paid entry.");
  assert.equal(event.editor_title_en, undefined);
  assert.equal(publicEvent({ id: "e1", title: "Meetup" }, "pending"), null);
  assert.deepEqual(publicSource({ id: "firi", name: "Firi", country: "NO", feed: "https://secret.example/rss", status: "ok" }), {
    id: "firi", name: "Firi", country: "NO",
  });
});

test("story approval needs a summary and records who and when", () => {
  const missing = applyStoryReview(storyRow(), { action: "approve", summary: "  " }, "Editor", "2026-10-10T12:00:00Z");
  assert.equal(missing.status, 400);
  const plan = applyStoryReview(storyRow(), {
    action: "approve",
    summary: "The company said it uses crypto mining. The letter is on the record.",
    title_en: "English headline",
  }, "Editor", "2026-10-10T12:00:00Z");
  assert.equal(plan.review_status, "approved");
  assert.equal(plan.reviewed_by, "Editor");
  assert.equal(plan.reviewed_at, "2026-10-10T12:00:00Z");
  assert.equal(plan.payload.status, "published");
  assert.equal(plan.payload.title_en, "English headline");
  assert.equal(plan.payload.reject_reason, undefined);
  assert.equal(plan.payload.matched[0], "\\bkrypto");
  const rejected = applyStoryReview(storyRow(), { action: "reject", reason: "Not Nordic." }, "Editor", "2026-10-10T12:00:00Z");
  assert.equal(rejected.review_status, "rejected");
  assert.equal(rejected.review_note, "Not Nordic.");
  assert.equal(rejected.payload.summary, null);
});

test("event rejection keeps the row and sets the audit fields", () => {
  const row = { id: "e1", payload: JSON.stringify({ id: "e1", title: "Meetup", status: "pending" }) };
  const plan = applyEventReview(row, { action: "reject", reason: "No Nordic link." }, "Editor", "2026-10-10T12:00:00Z");
  assert.equal(plan.review_status, "rejected");
  assert.equal(plan.item_status, "rejected");
  assert.equal(plan.reviewed_by, "Editor");
  assert.equal(plan.payload.reject_reason, "No Nordic link.");
});

function fakeDb(seed) {
  const stories = new Map(seed.stories || []);
  const events = new Map(seed.events || []);
  const sources = seed.sources || [];
  const audits = [];
  function prepare(sql) {
    const state = { sql, params: [] };
    const api = {
      bind(...params) {
        state.params = params;
        return api;
      },
      async first() {
        if (state.sql.includes("FROM stories")) return stories.get(state.params[0]) || null;
        if (state.sql.includes("FROM events")) return events.get(state.params[0]) || null;
        return null;
      },
      async all() {
        if (state.sql.includes("FROM stories") && state.sql.includes("review_status = 'approved'")) {
          return { results: [...stories.values()].filter((row) => row.review_status === "approved").map((row) => ({ payload: row.payload })) };
        }
        if (state.sql.includes("FROM stories") && state.sql.includes("item_status = 'pending'")) {
          return { results: [...stories.values()].filter((row) => row.review_status === "pending" && row.item_status === "pending").map((row) => ({ id: row.id, title: row.title, country: row.country, url: row.url })) };
        }
        if (state.sql.includes("FROM events") && state.sql.includes("review_status = 'approved'")) {
          return { results: [...events.values()].filter((row) => row.review_status === "approved") };
        }
        if (state.sql.includes("FROM events") && state.sql.includes("item_status = 'pending'")) {
          return { results: [...events.values()].filter((row) => row.review_status === "pending" && row.item_status === "pending") };
        }
        if (state.sql.includes("FROM sources")) return { results: sources };
        return { results: [] };
      },
      async run() {
        if (state.sql.startsWith("UPDATE stories")) {
          const id = state.params[state.params.length - 1];
          const row = stories.get(id);
          row.payload = state.params[0];
          row.review_status = state.params[2];
          row.item_status = state.params[3];
          row.summary = state.params[4];
          row.reviewed_by = state.params[5];
          row.reviewed_at = state.params[6];
        } else if (state.sql.startsWith("UPDATE events")) {
          const id = state.params[state.params.length - 1];
          const row = events.get(id);
          row.payload = state.params[0];
          row.review_status = state.params[1];
          row.item_status = state.params[2];
          row.reviewed_by = state.params[3];
          row.reviewed_at = state.params[4];
        } else if (state.sql.startsWith("INSERT INTO review_audit")) {
          audits.push(state.params);
        }
        return { success: true };
      },
    };
    return api;
  }
  return { prepare, stories, events, audits };
}

function request(method, path, { token, body } = {}) {
  const headers = new Headers();
  if (token) headers.set("authorization", "Bearer " + token);
  if (body) headers.set("content-type", "application/json");
  return new Request("https://content.example" + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
}

test("the review API refuses a missing or wrong token and does not publish teasers", async () => {
  const db = fakeDb({
    stories: [["abc", storyRow()]],
    events: [["e1", {
      id: "e1",
      payload: JSON.stringify({ id: "e1", title: "Meetup", start: "2026-11-01T18:00:00+02:00", teaser_local_only: "hidden" }),
      review_status: "approved",
      item_status: "published",
    }]],
  });
  const env = { DB: db, EDITOR_TOKEN: TOKEN, GITHUB_REPOSITORY: "jQrgen/nordic-crypto" };
  assert.equal((await handle(request("GET", "/api/review/pending"), env)).status, 401);
  assert.equal((await handle(request("GET", "/api/review/pending", { token: "nope" }), env)).status, 401);
  assert.equal((await handle(request("POST", "/api/review", { token: TOKEN, body: { kind: "story", id: "abc", action: "approve" } }), env)).status, 400);
  const pending = await handle(request("GET", "/api/review/pending", { token: TOKEN }), env);
  const pendingBody = await pending.json();
  assert.equal(pendingBody.stories.length, 1);
  assert.equal(JSON.stringify(pendingBody).includes("do not publish"), false);
  const approved = await handle(request("POST", "/api/review", {
    token: TOKEN,
    body: { kind: "story", id: "abc", action: "approve", summary: "Own words. What the story says.", by: "Editor" },
  }), env);
  const approvedBody = await approved.json();
  assert.equal(approvedBody.review_status, "approved");
  assert.equal(approvedBody.redeploy, "scheduled");
  assert.equal(db.stories.get("abc").reviewed_by, "Editor");
  assert.equal(db.audits.length, 1);
  const news = await (await handle(request("GET", "/api/v1/news.json"), env)).json();
  assert.equal(news.items.length, 1);
  assert.equal(JSON.stringify(news).includes("teaser_local_only"), false);
  assert.equal(JSON.stringify(news).includes("reader tip"), false);
  const events = await (await handle(request("GET", "/api/v1/events.json"), env)).json();
  assert.equal(events.events[0].title, "Meetup");
  assert.equal(JSON.stringify(events).includes("hidden"), false);
});

test("a configured dispatch token is not required for the approval to stick", () => {
  assert.equal(editorAuthorized(request("GET", "/api/review/pending", { token: TOKEN }), TOKEN), true);
  assert.equal(editorAuthorized(request("GET", "/api/review/pending"), TOKEN), false);
  assert.equal(editorAuthorized(request("GET", "/api/review/pending", { token: TOKEN }), ""), false);
});
