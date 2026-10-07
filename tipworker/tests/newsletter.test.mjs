// node --test tests/newsletter.test.mjs  – unit tests for signup validation, texts and the mailer guard (no network).
import test from "node:test"; import assert from "node:assert/strict";
import siteUrl from "../../site_url.json" with { type: "json" };
import { validateSignup } from "../src/newsletter.js";
import { SITES, LANG_KEYS, confirmEmail, welcomeEmail, text, pageUrl } from "../src/messages.js";
import { providerName, sendMail, TEST_OUTBOX } from "../src/mailer.js";

test("validateSignup", () => {
  assert.deepEqual(validateSignup({ email: " A@Example.org ", site: "kryptonytt" }), [{ email: "a@example.org", site: "kryptonytt", lang: "nn" }, null]);
  assert.equal(validateSignup({ email: "a@example.org", site: "nordic-crypto" })[0].lang, "en");
  for (const e of ["", "a", "a@b", "a@@b.no", "a b@c.no", "a..b@c.no", "<x>@c.no", "a@-c.no", "x".repeat(65) + "@c.no"])
    assert.equal(validateSignup({ email: e, site: "nordic-crypto" })[1], "email", e);
  assert.equal(validateSignup({ email: "a@c.no", site: "x" })[1], "site");
  assert.equal(validateSignup({ email: "a@c.no", site: "kryptonytt", lang: "fi" })[1], "lang");
  assert.equal(validateSignup({ email: 1, site: "kryptonytt" })[1], "invalid");
  assert.equal(validateSignup({ email: "a@c.no", site: "__proto__" })[1], "site");
});

test("every site language has all texts, with the link", () => {
  for (const [site, s] of Object.entries(SITES)) for (const lang of Object.keys(s.langs)) {
    assert.ok(LANG_KEYS.includes(lang), lang);
    const c = confirmEmail(site, lang, "https://x.test/c"), w = welcomeEmail(site, lang, "https://x.test/u");
    assert.ok(c.text.includes("https://x.test/c") && c.subject.includes(s.name), site + lang);
    assert.ok(w.text.includes("https://x.test/u"), site + lang);
    for (const k of ["ut", "uq", "ub", "ux"]) assert.ok(!text(lang, k, { name: s.name }).includes("{"), k);
  }
  assert.equal(pageUrl("kryptonytt", "nb"), "https://jqrgen.github.io/kryptonytt/bm/nyhetsbrev/");
  assert.equal(pageUrl("nordic-crypto", "en"), siteUrl.base + "newsletter/");
});

test("Norwegian texts never say AI or KI", () => {
  for (const lang of ["nn", "nb"]) for (const k of ["cs", "cb", "ws", "wb", "ut", "uq", "ub", "ux"])
    assert.doesNotMatch(text(lang, k, { name: "X", link: "L", site: "S" }), /(?<![\w-])(AI|KI)(?![\w])/, lang + k);
});

test("mailer sends nothing unless a provider AND MAIL_SEND_ENABLED=1 are set", async () => {
  assert.equal(providerName({}), "none");
  assert.equal(providerName({ MAIL_PROVIDER: "resend" }), "none");
  assert.equal(providerName({ MAIL_PROVIDER: "resend", MAIL_SEND_ENABLED: "1" }), "resend");
  assert.equal(providerName({ MAIL_PROVIDER: "test", MAIL_SEND_ENABLED: "1" }), "none");
  assert.equal(providerName({ MAIL_PROVIDER: "evil", MAIL_SEND_ENABLED: "1" }), "none");
  assert.equal(providerName({ SUBSCRIBE_TEST: "1", MAIL_PROVIDER: "resend", MAIL_SEND_ENABLED: "1" }), "test");
  const real = globalThis.fetch; let called = 0; globalThis.fetch = async () => { called++; return new Response("{}"); };
  try {
    assert.equal((await sendMail({}, { to: "a@b.no", site: "kryptonytt" })).sent, false);
    assert.equal((await sendMail({ MAIL_PROVIDER: "resend", MAIL_SEND_ENABLED: "1" }, { to: "a@b.no", site: "kryptonytt" })).sent, false); // no key/from
    assert.equal((await sendMail({ MAIL_PROVIDER: "webhook", MAIL_SEND_ENABLED: "1", MAIL_WEBHOOK_URL: "http://x" }, { to: "a", site: "kryptonytt" })).sent, false); // https only
    await sendMail({ SUBSCRIBE_TEST: "1" }, { to: "t@b.no", site: "kryptonytt" }); assert.equal(TEST_OUTBOX.at(-1).to, "t@b.no");
    assert.equal(called, 0);
  } finally { globalThis.fetch = real; }
});
