// Renders the reused share/social snippets (vendor/share.js, vendor/social.js copied from jQrgen/presentations src/) as JSON for build.py
const share = require("../vendor/share.js");
const SOURCE = "https://github.com/jQrgen/nordic-crypto"; // origin of this repo (git remote)
const [url, title, lang = "en"] = process.argv.slice(2); // lang: page language, used for the source-code label only (share bar stays as before)
process.stdout.write(JSON.stringify({ top: share.top({ url, title, lang: "en", source: { href: SOURCE, lang } }), bar: share.bar({ url, title, lang: "en" }), css: share.CSS, script: share.SCRIPT }));
