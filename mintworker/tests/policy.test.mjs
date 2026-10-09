import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { evaluate } from "../src/policy.js";
import { keyFlags, loadHotKey, publicHealth } from "../src/secrets.js";

const caps = JSON.parse(readFileSync(new URL("../caps.json", import.meta.url)));
const empty = { claims: new Set(), eventCounts: {}, dayCounts: {} };

function req(over) {
  return { chain: "nexa", eventId: "evt", day: "2026-10-07", balance: 25000, identityHash: "abc", ...over };
}

test("a funded mint under the caps is allowed", () => {
  const d = evaluate(caps, empty, req());
  assert.equal(d.allow, true);
  assert.equal(d.needs_funding, false);
  assert.equal(d.draw, 1020);
});

test("below the reserve refuses and asks for funding", () => {
  const d = evaluate(caps, empty, req({ balance: 2000 }));
  assert.equal(d.allow, false);
  assert.equal(d.reason, "below_reserve");
  assert.equal(d.needs_funding, true);
  assert.equal(d.status, "empty");
});

test("a missing balance fails closed", () => {
  const d = evaluate(caps, empty, req({ balance: null }));
  assert.equal(d.allow, false);
  assert.equal(d.reason, "balance_unknown");
  assert.equal(d.needs_funding, true);
});

test("one NexaID per event, including a second card kind", () => {
  const state = { claims: new Set(["abc"]), eventCounts: {}, dayCounts: {} };
  const d = evaluate(caps, state, req());
  assert.equal(d.allow, false);
  assert.equal(d.reason, "identity_used");
  const other = evaluate(caps, state, req({ eventId: "other", identityHash: "def" }));
  assert.equal(other.allow, true);
});

test("event cap and day cap", () => {
  const eventFull = { claims: new Set(), eventCounts: { "nexa|evt": 20 }, dayCounts: {} };
  assert.equal(evaluate(caps, eventFull, req()).reason, "event_cap");
  const dayFull = { claims: new Set(), eventCounts: {}, dayCounts: { "nexa|2026-10-07": 15 } };
  assert.equal(evaluate(caps, dayFull, req()).reason, "day_cap");
});

test("bitcoin cash uses its own caps and the 0.002 BCH target", () => {
  assert.equal(caps.bch.hot_balance_target, 200000);
  const d = evaluate(caps, empty, req({ chain: "bch", balance: 120000 }));
  assert.equal(d.allow, true);
  assert.equal(d.above_target, false);
  const over = evaluate(caps, empty, req({ chain: "bch", balance: 250000 }));
  assert.equal(over.allow, true);
  assert.equal(over.above_target, true);
  const low = evaluate(caps, empty, req({ chain: "bch", balance: 20000 }));
  assert.equal(low.reason, "below_reserve");
});

test("the health view cannot see the secret", () => {
  const secret = "nexa-hot-key-material-not-for-logs-0123456789";
  const env = { NEXA_HOT_KEY: secret, BCH_HOT_KEY: "" };
  const health = publicHealth(env);
  assert.equal(health.keys.nexa, true);
  assert.equal(health.keys.bch, false);
  assert.equal(health.signs, false);
  assert.equal(JSON.stringify(health).includes(secret), false);
  assert.equal(JSON.stringify(keyFlags(env)).includes(secret), false);
  assert.equal(loadHotKey(env, "nexa"), secret);
});
