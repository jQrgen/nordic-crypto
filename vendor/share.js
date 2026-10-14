// Reusable share buttons for article pages: plain links (no third-party scripts, no tracking, no counters).
//   const share = require("./share.js");          // from src/ (or require("../share.js") from src/orgchart/)
//   html: share.bar({ url, title, text?, lang, networks?, via? })   -> a <nav class="share"> with a native Share button
//         (shown on phones when navigator.share exists), then LinkedIn, X, Facebook, email (or the given networks), copy link.
//         X/Facebook/LinkedIn are ordinary <a target="_blank" rel="noopener"> intent links, not popups.
//   css:  share.CSS                                      -> add once to the page's <style>
//   js:   share.SCRIPT                                   -> add once before </body> (copy link and the native share button; the intent links work without it)
//   top:  share.top({ url, title, lang, networks? })  -> DEFAULT for the top of an article: the "Følg meg:"/"Follow me:" profile
//         links from social.js followed by the share bar (pass source: { href, lang? } to show a source-code repo link instead). Use share.bar (without social links) for the bar at the bottom.
//   share.CSS already includes social.CSS.
// Each bar carries its own url/title, so a page can have one bar per language.
const social = require("./social.js");
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const LABELS = {
  en: { aria: "Share this page", share: "Share:", native: "Share", email: "Email", copy: "Copy link", copied: "Link copied", body: "You might find this interesting:" },
  nn: { aria: "Del sida", share: "Del:", native: "Del", email: "E-post", copy: "Kopier lenke", copied: "Lenken er kopiert", body: "Kanskje interessant for deg:" },
  nb: { aria: "Del siden", share: "Del:", native: "Del", email: "E-post", copy: "Kopier lenke", copied: "Lenken er kopiert", body: "Kanskje interessant for deg:" },
  sv: { aria: "Dela sidan", share: "Dela:", native: "Dela", email: "E-post", copy: "Kopiera länk", copied: "Länken är kopierad", body: "Kanske intressant för dig:" },
  da: { aria: "Del siden", share: "Del:", native: "Del", email: "E-mail", copy: "Kopiér link", copied: "Linket er kopieret", body: "Måske interessant for dig:" },
  fi: { aria: "Jaa sivu", share: "Jaa:", native: "Jaa", email: "Sähköposti", copy: "Kopioi linkki", copied: "Linkki on kopioitu", body: "Tämä voi kiinnostaa sinua:" },
  is: { aria: "Deila síðunni", share: "Deila:", native: "Deila", email: "Tölvupóstur", copy: "Afrita tengil", copied: "Tengillinn er afritaður", body: "Kannski áhugavert fyrir þig:" },
  zh: { aria: "分享此页", share: "分享：", native: "分享", email: "电子邮件", copy: "复制链接", copied: "链接已复制", body: "也许你会感兴趣：" },
  hi: { aria: "यह पृष्ठ साझा करें", share: "साझा करें:", native: "साझा करें", email: "ईमेल", copy: "लिंक कॉपी करें", copied: "लिंक कॉपी हो गया", body: "शायद यह आपके लिए दिलचस्प हो:" },
  es: { aria: "Compartir esta página", share: "Compartir:", native: "Compartir", email: "Correo", copy: "Copiar enlace", copied: "Enlace copiado", body: "Quizá te interese:" },
  fr: { aria: "Partager cette page", share: "Partager :", native: "Partager", email: "E-mail", copy: "Copier le lien", copied: "Lien copié", body: "Cela pourrait vous intéresser :" },
  ar: { aria: "مشاركة هذه الصفحة", share: "مشاركة:", native: "مشاركة", email: "بريد", copy: "نسخ الرابط", copied: "تم نسخ الرابط", body: "قد يهمك هذا:" },
  bn: { aria: "এই পাতা শেয়ার করুন", share: "শেয়ার:", native: "শেয়ার", email: "ইমেল", copy: "লিঙ্ক কপি করুন", copied: "লিঙ্ক কপি হয়েছে", body: "হয়তো আপনার কাজে লাগবে:" },
  pt: { aria: "Partilhar esta página", share: "Partilhar:", native: "Partilhar", email: "E-mail", copy: "Copiar ligação", copied: "Ligação copiada", body: "Talvez lhe interesse:" },
  ru: { aria: "Поделиться страницей", share: "Поделиться:", native: "Поделиться", email: "Почта", copy: "Копировать ссылку", copied: "Ссылка скопирована", body: "Возможно, вам будет интересно:" },
  ur: { aria: "یہ صفحہ شیئر کریں", share: "شیئر:", native: "شیئر", email: "ای میل", copy: "لنک کاپی کریں", copied: "لنک کاپی ہو گیا", body: "شاید یہ آپ کے لیے دلچسپ ہو:" },
  id: { aria: "Bagikan halaman ini", share: "Bagikan:", native: "Bagikan", email: "Email", copy: "Salin tautan", copied: "Tautan disalin", body: "Mungkin menarik bagi Anda:" },
  de: { aria: "Diese Seite teilen", share: "Teilen:", native: "Teilen", email: "E-Mail", copy: "Link kopieren", copied: "Link kopiert", body: "Vielleicht interessant für Sie:" },
  ja: { aria: "このページを共有", share: "共有:", native: "共有", email: "メール", copy: "リンクをコピー", copied: "リンクをコピーしました", body: "興味があるかもしれません:" },
  sw: { aria: "Shiriki ukurasa huu", share: "Shiriki:", native: "Shiriki", email: "Barua pepe", copy: "Nakili kiungo", copied: "Kiungo kimenakiliwa", body: "Huenda ikakuvutia:" },
  mr: { aria: "हे पृष्ठ शेअर करा", share: "शेअर करा:", native: "शेअर करा", email: "ईमेल", copy: "लिंक कॉपी करा", copied: "लिंक कॉपी झाली", body: "कदाचित तुम्हाला हे आवडेल:" },
  fa: { aria: "این صفحه را هم‌رسانی کنید", share: "هم‌رسانی:", native: "هم‌رسانی", email: "ایمیل", copy: "رونوشت پیوند", copied: "پیوند رونوشت شد", body: "شاید برایتان جالب باشد:" },
  uk: { aria: "Поділитися сторінкою", share: "Поділитися:", native: "Поділитися", email: "Пошта", copy: "Копіювати посилання", copied: "Посилання скопійовано", body: "Можливо, вам буде цікаво:" },
};
LABELS.no = LABELS.nb;

// Default set: LinkedIn, X, Facebook, email. Pass networks (keys, in order) to choose, e.g. ["x", "linkedin", "reddit", "hackernews"].
const DEFAULT_NETWORKS = ["linkedin", "x", "facebook", "email"];
// encodeURIComponent, not URLSearchParams: spaces stay %20 (not +) and "+" in the text stays %2B.
function query(params) {
  return Object.keys(params).filter((k) => params[k] != null && params[k] !== "")
    .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(String(params[k]))).join("&");
}
function links(url, title, lang = "en", networks = DEFAULT_NETWORKS, via) {
  const L = LABELS[lang] || LABELS.en;
  // twitter.com/intent/tweet is the universal link the X app opens on iPhone.
  // x.com/intent/post stays in Safari and asks for a web login even when the app is signed in.
  const all = {
    linkedin: ["linkedin", "LinkedIn", "https://www.linkedin.com/sharing/share-offsite/?" + query({ url })],
    x: ["x", "X", "https://twitter.com/intent/tweet?" + query({ text: title, url, via })],
    facebook: ["facebook", "Facebook", "https://www.facebook.com/sharer/sharer.php?" + query({ u: url })],
    reddit: ["reddit", "Reddit", "https://www.reddit.com/submit?" + query({ url, title })],
    hackernews: ["hackernews", "Hacker News", "https://news.ycombinator.com/submitlink?" + query({ u: url, t: title })],
    email: ["email", L.email, "mailto:?" + query({ subject: title, body: L.body + "\n" + url })],
  };
  return networks.map((k) => all[k]).filter(Boolean);
}

function bar({ url, title, text, lang = "en", networks, via, shareTitle } = {}) {
  const L = LABELS[lang] || LABELS.en;
  const message = text || title || "";
  const sheetTitle = shareTitle || title || message;
  const a = links(url, message, lang, networks, via).map(([k, label, href]) =>
    `<a class="share-${k}" href="${esc(href)}"${k === "email" ? "" : ' target="_blank" rel="noopener"'}>${esc(label)}</a>`).join("");
  // hidden until the script sees a phone with navigator.share. The X link stays as the fallback.
  const native = `<button type="button" class="share-native" hidden data-url="${esc(url)}" data-title="${esc(sheetTitle)}" data-text="${esc(message)}">${esc(L.native)}</button>`;
  return `<nav class="share" aria-label="${esc(L.aria)}"><span class="share-label">${esc(L.share)}</span>${native}${a}<button type="button" class="share-copy" data-url="${esc(url)}" data-done="${esc(L.copied)}">${esc(L.copy)}</button><span class="share-status" role="status" aria-live="polite"></span></nav>`;
}

// source: { href, lang? } -> show a link to the site's source code repo instead of the "Follow me" profile links (news sites).
function top({ url, title, text, lang = "en", networks, source, via }) {
  const head = source && source.href ? social.source({ lang: source.lang || lang, href: source.href }) : social.links({ lang });
  return head + "\n  " + bar({ url, title, text, lang, networks, via });
}

const CSS = social.CSS + `
.share{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-start;text-align:start;gap:6px 8px;margin:14px 0;width:fit-content;max-width:100%}
.share-label{font-size:13px;color:var(--muted,#4B5563);margin-right:2px}
.share a,.share button{font:inherit;font-size:13.5px;line-height:1.2;color:var(--ink,#000);background:var(--paper,#fff);border:1px solid var(--line,#000);padding:5px 10px;text-decoration:none;cursor:pointer}
.share a:hover,.share button:hover{background:var(--band,#000);color:var(--band-ink,#fff)}
.share a:focus-visible,.share button:focus-visible{outline:2px solid var(--ink,#000);outline-offset:2px}
.share button.share-native{background:var(--ink,#000);color:var(--paper,#fff)}
.share button.share-native:hover,.share button.share-native:focus-visible{background:var(--band,#000);color:var(--band-ink,#fff)}
.share button.share-native[hidden]{display:none}
.share.has-native .share-label{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.share-status{font-size:13px;color:var(--muted,#4B5563)}
`;

// Copy link, and the system share sheet on phones. Intent links are real anchors: no window.open, no about:blank.
const SCRIPT = `<script>
document.addEventListener("click", function (e) {
  var n = e.target.closest && e.target.closest(".share-native");
  // share-offsite is not an iOS universal link, so the LinkedIn anchor would open Safari,
  // ask for a web login, and land on the feed. On a phone, that click opens the system sheet instead.
  var linkedin = e.target.closest && e.target.closest("a.share-linkedin");
  var phone = window.matchMedia("(pointer: coarse)").matches || window.matchMedia("(max-width: 860px)").matches;
  var sheet = (n || (linkedin && phone && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey)) && navigator.share;
  if (sheet) {
    var root = (n || linkedin).closest(".share");
    var src = root && root.querySelector(".share-native");
    if (src) {
      if (linkedin) e.preventDefault();
      var data = { title: src.getAttribute("data-title") || "", text: src.getAttribute("data-text") || "", url: src.getAttribute("data-url") || "" };
      try { navigator.share(data).catch(function () {}); } catch (err) {}
      return;
    }
  }
  var b = e.target.closest && e.target.closest(".share-copy"); if (!b) return;
  var url = b.getAttribute("data-url"), st = b.parentNode.querySelector(".share-status");
  var done = function () { if (st) { st.textContent = b.getAttribute("data-done"); setTimeout(function () { st.textContent = ""; }, 2500); } };
  var fallback = function () { var i = document.createElement("input"); i.value = url; document.body.appendChild(i); i.select(); try { document.execCommand("copy"); done(); } catch (x) { window.prompt("", url); } i.remove(); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, fallback); else fallback();
});
(function () {
  if (!navigator.share) return;
  var mobile = window.matchMedia("(pointer: coarse)").matches || window.matchMedia("(max-width: 860px)").matches;
  if (!mobile) return;
  var nodes = document.querySelectorAll(".share-native");
  for (var i = 0; i < nodes.length; i++) { nodes[i].hidden = false; if (nodes[i].parentNode) nodes[i].parentNode.classList.add("has-native"); }
})();
</script>`;

module.exports = { top, bar, links, CSS, SCRIPT, LABELS };
