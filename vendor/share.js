// Reusable share buttons for article pages: plain links (no third-party scripts, no tracking, no counters).
//   const share = require("./share.js");          // from src/ (or require("../share.js") from src/orgchart/)
//   html: share.bar({ url, title, lang: "no" | "en", networks? })   -> a <nav class="share"> with LinkedIn, X, Facebook, email (or the given networks), copy link
//   css:  share.CSS                                      -> add once to the page's <style>
//   js:   share.SCRIPT                                   -> add once before </body> (copy-link only; links work without it)
//   top:  share.top({ url, title, lang, networks? })  -> DEFAULT for the top of an article: the "Følg meg:"/"Follow me:" profile
//         links from social.js followed by the share bar (pass source: { href, lang? } to show a source-code repo link instead). Use share.bar (without social links) for the bar at the bottom.
//   share.CSS already includes social.CSS.
// Each bar carries its own url/title, so a page can have one bar per language.
const social = require("./social.js");
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const LABELS = {
  no: { aria: "Del artikkelen", share: "Del:", email: "E-post", copy: "Kopier lenke", copied: "Lenken er kopiert", body: "Kanskje interessant for deg:" },
  en: { aria: "Share this article", share: "Share:", email: "Email", copy: "Copy link", copied: "Link copied", body: "You might find this interesting:" },
};

// Default set: LinkedIn, X, Facebook, email. Pass networks (keys, in order) to choose, e.g. ["x", "linkedin", "reddit", "hackernews"].
const DEFAULT_NETWORKS = ["linkedin", "x", "facebook", "email"];
function links(url, title, lang = "en", networks = DEFAULT_NETWORKS) {
  const L = LABELS[lang] || LABELS.en, u = encodeURIComponent(url), t = encodeURIComponent(title);
  const all = {
    linkedin: ["linkedin", "LinkedIn", `https://www.linkedin.com/sharing/share-offsite/?url=${u}`],
    x: ["x", "X", `https://x.com/intent/post?text=${t}&url=${u}`],
    facebook: ["facebook", "Facebook", `https://www.facebook.com/sharer/sharer.php?u=${u}`],
    reddit: ["reddit", "Reddit", `https://www.reddit.com/submit?url=${u}&title=${t}`],
    hackernews: ["hackernews", "Hacker News", `https://news.ycombinator.com/submitlink?u=${u}&t=${t}`],
    email: ["email", L.email, `mailto:?subject=${t}&body=${encodeURIComponent(L.body + "\n" + url)}`],
  };
  return networks.map((k) => all[k]).filter(Boolean);
}

function bar({ url, title, lang = "en", networks }) {
  const L = LABELS[lang] || LABELS.en;
  const a = links(url, title, lang, networks).map(([k, label, href]) =>
    `<a class="share-${k}" href="${esc(href)}"${k === "email" ? "" : ' target="_blank" rel="noopener noreferrer"'}>${esc(label)}</a>`).join("");
  return `<nav class="share" aria-label="${esc(L.aria)}"><span class="share-label">${esc(L.share)}</span>${a}<button type="button" class="share-copy" data-url="${esc(url)}" data-done="${esc(L.copied)}">${esc(L.copy)}</button><span class="share-status" role="status" aria-live="polite"></span></nav>`;
}

// source: { href, lang? } -> show a link to the site's source code repo instead of the "Follow me" profile links (news sites).
function top({ url, title, lang = "en", networks, source }) {
  const head = source && source.href ? social.source({ lang: source.lang || lang, href: source.href }) : social.links({ lang });
  return head + "\n  " + bar({ url, title, lang, networks });
}

const CSS = social.CSS + `
.share{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin:14px 0}
.share-label{font-size:13px;color:var(--muted,#4B5563);margin-right:2px}
.share a,.share button{font:inherit;font-size:13.5px;line-height:1.2;color:var(--ink,#000);background:var(--paper,#fff);border:1px solid var(--line,#000);padding:5px 10px;text-decoration:none;cursor:pointer}
.share a:hover,.share button:hover{background:var(--band,#000);color:var(--band-ink,#fff)}
.share a:focus-visible,.share button:focus-visible{outline:2px solid var(--ink,#000);outline-offset:2px}
.share-status{font-size:13px;color:var(--muted,#4B5563)}
`;

// copy link: Clipboard API, falls back to a selected text field; no network calls
const SCRIPT = `<script>
document.addEventListener("click", function (e) {
  var b = e.target.closest && e.target.closest(".share-copy"); if (!b) return;
  var url = b.getAttribute("data-url"), st = b.parentNode.querySelector(".share-status");
  var done = function () { if (st) { st.textContent = b.getAttribute("data-done"); setTimeout(function () { st.textContent = ""; }, 2500); } };
  var fallback = function () { var i = document.createElement("input"); i.value = url; document.body.appendChild(i); i.select(); try { document.execCommand("copy"); done(); } catch (x) { window.prompt("", url); } i.remove(); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, fallback); else fallback();
});
</script>`;

module.exports = { top, bar, links, CSS, SCRIPT, LABELS };
