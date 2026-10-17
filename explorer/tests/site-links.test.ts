import assert from "node:assert/strict";
import test from "node:test";
import { newsSite, siteLinks } from "../lib/site-links";

test("footer links follow the front page, then the way back", () => {
  assert.deepEqual(
    siteLinks.map((link) => [link.label, link.href, link.note ?? ""]),
    [
      ["Follow", "https://nordiccrypto.no/newsletter/#signup", ""],
      ["Join on Telegram", "https://t.me/nordiccryptochat", ""],
      ["Follow on X", "https://x.com/nordiccryptobot", ""],
      ["Follow on Facebook", "https://www.facebook.com/profile.php?id=61595548315551", ""],
      ["Watch on YouTube", "https://www.youtube.com/@NordicCryptoTV", ""],
      ["Source code", "https://github.com/nordic-crypto-org/nordic-crypto/tree/main/explorer", ""],
      ["RSS", "https://nordiccrypto.no/rss.xml", ""],
    ],
  );
  assert.equal(siteLinks.find((link) => link.id === "x")?.title, "Nordic Crypto on X (@nordiccryptobot), the site's own account");
  assert.equal(siteLinks.find((link) => link.id === "telegram")?.title, "Nordic Crypto on Telegram (t.me/nordiccryptochat), the brand chat");
  assert.equal(newsSite.href, "https://nordiccrypto.no/");
  assert.equal(newsSite.label, "nordiccrypto.no");
});
