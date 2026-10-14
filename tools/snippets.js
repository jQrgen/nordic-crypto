// Renders the reused share/social snippets (vendor/share.js, vendor/social.js copied from jQrgen/presentations src/) as JSON for build.py
//   node tools/snippets.js <url> <title> [lang]   one page, from argv
//   node tools/snippets.js --lines                one JSON [url, title, lang] per stdin line -> one JSON object per stdout line (build.py keeps one process for the whole build)
const share = require("../vendor/share.js");
// Share bar only. The repo link is the last line of the site footer (build.py), not a line in the page body.
// lang stays in the protocol (build.py sends [url, title, lang]) and is unused here: the bar was always English.
const render = (url, title, _lang = "en") => JSON.stringify({ top: share.bar({ url, title, lang: "en" }), bar: share.bar({ url, title, lang: "en" }), css: share.CSS, script: share.SCRIPT });
if (process.argv[2] === "--lines") {
  // a bad line (e.g. a lone surrogate, which makes encodeURIComponent throw) answers {error} and must not end the shared process
  require("readline").createInterface({ input: process.stdin }).on("line", (line) => {
    let out;
    try { out = render(...JSON.parse(line)); } catch (e) { out = JSON.stringify({ error: String(e) }); }
    process.stdout.write(out + "\n");
  });
} else process.stdout.write(render(...process.argv.slice(2)));
