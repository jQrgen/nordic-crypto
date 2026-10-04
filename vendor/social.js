// Reusable "follow me" links for Jørgen S. Notland (jQrgen): plain links, no icons from third parties, no scripts, no tracking.
//   const social = require("./social.js");        // from src/ (or require("../social.js") from src/orgchart/)
//   html: social.links({ lang: "no" | "en" })      -> a <nav class="social"> to put under the byline
//   css:  social.CSS                               -> add once to the page's <style> (already part of share.CSS)
// Default for articles: share.top({ url, title, lang }) in share.js renders these links plus the share bar.
// Only profiles confirmed from jQrgen's own sources are listed (see "source" on each entry). Do not add guessed handles.
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const PROFILES = [
  { key: "x", label: "X", href: "https://x.com/jqrgensn", source: "GitHub profile jQrgen (social account / twitter_username); his post links on the presentations home page" },
  { key: "github", label: "GitHub", href: "https://github.com/jQrgen", source: "personal site jqrgen.github.io; GitHub profile" },
  { key: "gitlab", label: "GitLab", href: "https://gitlab.com/jQrgen", source: "personal site jqrgen.github.io" },
  { key: "medium", label: "Medium", href: "https://jqrgen.medium.com/", source: "presentations home page (his articles are published under jqrgen.medium.com)" },
];
const LABELS = { no: { aria: "Jørgen på nett", follow: "Følg meg:" }, en: { aria: "Jørgen online", follow: "Follow me:" } };
function links({ lang = "en", only } = {}) {
  const L = LABELS[lang] || LABELS.en;
  const list = only ? PROFILES.filter((p) => only.includes(p.key)) : PROFILES;
  const a = list.map((p) => `<a class="social-${p.key}" href="${esc(p.href)}" rel="me noopener noreferrer" target="_blank">${esc(p.label)}</a>`).join("");
  return `<nav class="social" aria-label="${esc(L.aria)}"><span class="social-label">${esc(L.follow)}</span>${a}</nav>`;
}
const CSS = `
.social{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;margin:6px 0 0;font-size:13.5px}
.social-label{color:var(--muted,#4B5563)}
.social a{color:var(--ink,#000);text-decoration:underline;text-underline-offset:2px}
.social a:hover{text-decoration-thickness:2px}
.social a:focus-visible{outline:2px solid var(--ink,#000);outline-offset:2px}
`;
// Source-code link for sites built from a public repo (news sites): replaces the "Follow me" profile links there.
//   social.source({ lang, href }) -> <nav class="social social-source"> with a "Source code" label linking to the site's repo
const SOURCE_LABELS = { nn: "Kjeldekode", nb: "Kildekode", no: "Kildekode", da: "Kildekode", sv: "Källkod", fi: "Lähdekoodi", is: "Frumkóði", en: "Source code" };
function source({ lang = "en", href }) {
  const label = SOURCE_LABELS[lang] || SOURCE_LABELS.en;
  const text = String(href).replace(/^https?:\/\//, "").replace(/\.git$/, "").replace(/\/$/, "");
  return `<nav class="social social-source" aria-label="${esc(label)}"><span class="social-label">${esc(label)}:</span><a class="social-repo" href="${esc(href)}" rel="noopener noreferrer" target="_blank">${esc(text)}</a></nav>`;
}
module.exports = { links, source, CSS, PROFILES, SOURCE_LABELS };
