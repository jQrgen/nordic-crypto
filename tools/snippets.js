// Renders the reused share/social snippets (vendor/share.js, vendor/social.js copied from jQrgen/presentations src/) as JSON for build.py
//   node tools/snippets.js <url> <title> [lang] [text]   one page, from argv
//   node tools/snippets.js --lines                     one JSON [url, title, lang, text?] per stdin line -> one JSON object per stdout line
const share = require("../vendor/share.js");
const VIA = "nordiccryptobot";
// Share bar only. The repo link is the last line of the site footer (build.py), not a line in the page body.
// text, when set, is the prefilled message (an event's title, date and city). Otherwise the page title is used.
const render = (url, title, lang = "en", text) => {
  const bar = share.bar({ url, title, text: text || undefined, lang, via: VIA });
  return JSON.stringify({ top: bar, bar, css: share.CSS, script: share.SCRIPT });
};
if (process.argv[2] === "--lines") {
  // a bad line (e.g. a lone surrogate, which makes encodeURIComponent throw) answers {error} and must not end the shared process
  require("readline").createInterface({ input: process.stdin }).on("line", (line) => {
    let out;
    try { out = render(...JSON.parse(line)); } catch (e) { out = JSON.stringify({ error: String(e) }); }
    process.stdout.write(out + "\n");
  });
} else process.stdout.write(render(...process.argv.slice(2)));
