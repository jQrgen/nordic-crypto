// Texts for the newsletter emails and the worker's own small unsubscribe page, per site and language.
// Kryptonytt rule: Norwegian text never says "AI"/"KI" (none of these texts mention it at all).
// Placeholders: {name} publication name, {link} confirmation/unsubscribe link, {site} site URL.
import siteUrl from "../../site_url.json" with { type: "json" };
const SITE_BASE = siteUrl.base.endsWith("/") ? siteUrl.base : siteUrl.base + "/";
export const SITES = {
  "nordic-crypto": { name: "Nordic Crypto", base: SITE_BASE, page: "newsletter/",
    langs: { en: "", nn: "nn/", nb: "nb/", sv: "sv/", da: "da/", fi: "fi/", is: "is/" }, def: "en" },
  "kryptonytt": { name: "Kryptonytt Norge", base: "https://jqrgen.github.io/kryptonytt/", page: "nyhetsbrev/",
    langs: { nn: "", nb: "bm/", en: "en/" }, def: "nn" },
};
export const pageUrl = (site, lang) => { const s = SITES[site]; return s.base + (s.langs[lang] ?? "") + s.page; };

const T = {
  en: { cs: "Confirm your {name} newsletter subscription",
        cb: "Hi,\n\nSomeone (hopefully you) asked to receive the {name} newsletter at this address. Please confirm by opening this link within 7 days:\n\n{link}\n\nIf it wasn't you, just ignore this email: nothing more will be sent, and the address is deleted after 7 days.\n\n{name} – {site}\n",
        ws: "Welcome to the {name} newsletter",
        wb: "Thanks, your subscription is confirmed. You'll get a short weekly digest of the stories our editor has approved, with links to the original sources.\n\nYou can unsubscribe at any time with this link (it is also in every newsletter):\n{link}\n\n{name} – {site}\n",
        ut: "Unsubscribe", uq: "Unsubscribe from the {name} newsletter?", ub: "Yes, unsubscribe", ux: "This link is invalid." },
  nn: { cs: "Stadfest abonnementet på nyheitsbrevet frå {name}",
        cb: "Hei,\n\nNokon (forhåpentleg du) har bede om å få nyheitsbrevet frå {name} til denne adressa. Stadfest ved å opne denne lenkja innan 7 dagar:\n\n{link}\n\nVar det ikkje deg, kan du berre sjå bort frå denne e-posten: du får ikkje fleire, og adressa blir sletta etter 7 dagar.\n\n{name} – {site}\n",
        ws: "Velkomen til nyheitsbrevet frå {name}",
        wb: "Takk, abonnementet ditt er stadfesta. Du får eit kort samandrag kvar veke av sakene redaktøren vår har godkjent, med lenkjer til kjeldene.\n\nDu kan melde deg av når du vil med denne lenkja (ho står også i kvart nyheitsbrev):\n{link}\n\n{name} – {site}\n",
        ut: "Meld av", uq: "Vil du melde deg av nyheitsbrevet frå {name}?", ub: "Ja, meld meg av", ux: "Lenkja er ugyldig." },
  nb: { cs: "Bekreft abonnementet på nyhetsbrevet fra {name}",
        cb: "Hei,\n\nNoen (forhåpentligvis du) har bedt om å få nyhetsbrevet fra {name} til denne adressen. Bekreft ved å åpne denne lenken innen 7 dager:\n\n{link}\n\nVar det ikke deg, kan du bare se bort fra denne e-posten: du får ikke flere, og adressen slettes etter 7 dager.\n\n{name} – {site}\n",
        ws: "Velkommen til nyhetsbrevet fra {name}",
        wb: "Takk, abonnementet ditt er bekreftet. Du får et kort sammendrag hver uke av sakene redaktøren vår har godkjent, med lenker til kildene.\n\nDu kan melde deg av når du vil med denne lenken (den står også i hvert nyhetsbrev):\n{link}\n\n{name} – {site}\n",
        ut: "Meld av", uq: "Vil du melde deg av nyhetsbrevet fra {name}?", ub: "Ja, meld meg av", ux: "Lenken er ugyldig." },
  sv: { cs: "Bekräfta din prenumeration på nyhetsbrevet från {name}",
        cb: "Hej,\n\nNågon (förhoppningsvis du) har bett om att få nyhetsbrevet från {name} till den här adressen. Bekräfta genom att öppna länken inom 7 dagar:\n\n{link}\n\nVar det inte du kan du bortse från det här mejlet: inget mer skickas, och adressen raderas efter 7 dagar.\n\n{name} – {site}\n",
        ws: "Välkommen till nyhetsbrevet från {name}",
        wb: "Tack, din prenumeration är bekräftad. Du får en kort sammanfattning varje vecka av de nyheter som vår redaktör har godkänt, med länkar till källorna.\n\nDu kan avsluta prenumerationen när du vill med den här länken (den finns också i varje nyhetsbrev):\n{link}\n\n{name} – {site}\n",
        ut: "Avsluta prenumeration", uq: "Vill du avsluta prenumerationen på nyhetsbrevet från {name}?", ub: "Ja, avsluta", ux: "Länken är ogiltig." },
  da: { cs: "Bekræft dit abonnement på nyhedsbrevet fra {name}",
        cb: "Hej,\n\nNogen (forhåbentlig dig) har bedt om at få nyhedsbrevet fra {name} på denne adresse. Bekræft ved at åbne linket inden for 7 dage:\n\n{link}\n\nVar det ikke dig, kan du bare se bort fra denne e-mail: der sendes ikke mere, og adressen slettes efter 7 dage.\n\n{name} – {site}\n",
        ws: "Velkommen til nyhedsbrevet fra {name}",
        wb: "Tak, dit abonnement er bekræftet. Du får et kort ugentligt overblik over de historier, vores redaktør har godkendt, med links til kilderne.\n\nDu kan til enhver tid afmelde dig med dette link (det står også i hvert nyhedsbrev):\n{link}\n\n{name} – {site}\n",
        ut: "Afmeld", uq: "Vil du afmelde nyhedsbrevet fra {name}?", ub: "Ja, afmeld mig", ux: "Linket er ugyldigt." },
  fi: { cs: "Vahvista {name}-uutiskirjeen tilaus",
        cb: "Hei,\n\nJoku (toivottavasti sinä) on pyytänyt {name}-uutiskirjettä tähän osoitteeseen. Vahvista tilaus avaamalla tämä linkki 7 päivän kuluessa:\n\n{link}\n\nJos et tilannut uutiskirjettä, voit jättää tämän viestin huomiotta: muuta ei lähetetä, ja osoite poistetaan 7 päivän kuluttua.\n\n{name} – {site}\n",
        ws: "Tervetuloa {name}-uutiskirjeen tilaajaksi",
        wb: "Kiitos, tilauksesi on vahvistettu. Saat joka viikko lyhyen koosteen toimittajamme hyväksymistä uutisista ja linkit alkuperäisiin lähteisiin.\n\nVoit perua tilauksen milloin tahansa tällä linkillä (se on myös jokaisessa uutiskirjeessä):\n{link}\n\n{name} – {site}\n",
        ut: "Peru tilaus", uq: "Haluatko perua {name}-uutiskirjeen tilauksen?", ub: "Kyllä, peru tilaus", ux: "Linkki ei ole voimassa." },
  is: { cs: "Staðfestu áskrift að fréttabréfi {name}",
        cb: "Hæ,\n\nEinhver (vonandi þú) hefur beðið um að fá fréttabréf {name} á þetta netfang. Staðfestu með því að opna þennan tengil innan 7 daga:\n\n{link}\n\nEf þetta varst ekki þú geturðu hunsað þennan póst: ekkert fleira verður sent og netfanginu verður eytt eftir 7 daga.\n\n{name} – {site}\n",
        ws: "Velkomin(n) á fréttabréf {name}",
        wb: "Takk, áskriftin þín er staðfest. Þú færð stutta vikulega samantekt um fréttir sem ritstjórinn okkar hefur samþykkt, með tenglum á heimildirnar.\n\nÞú getur sagt upp áskriftinni hvenær sem er með þessum tengli (hann er líka í hverju fréttabréfi):\n{link}\n\n{name} – {site}\n",
        ut: "Segja upp áskrift", uq: "Viltu segja upp áskrift að fréttabréfi {name}?", ub: "Já, segja upp", ux: "Tengillinn er ógildur." },
};
export const LANG_KEYS = Object.keys(T);
const fill = (s, v) => s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m));
export function text(lang, key, vars) { return fill((T[lang] || T.en)[key], vars || {}); }
export function confirmEmail(site, lang, link) {
  const v = { name: SITES[site].name, site: SITES[site].base + (SITES[site].langs[lang] ?? ""), link };
  const subject = text(lang, "cs", v), body = text(lang, "cb", v);
  return { subject, text: body, ...(site === "nordic-crypto" ? { html: emailHtml(site, lang, { title: subject, body, link, cta: true }) } : {}) };
}
export function welcomeEmail(site, lang, link) {
  const v = { name: SITES[site].name, site: SITES[site].base + (SITES[site].langs[lang] ?? ""), link };
  let body = text(lang, "wb", v);
  if (site === "nordic-crypto" && !body.includes("The Nordic Crypto team")) body += "The Nordic Crypto team\n";
  const subject = text(lang, "ws", v);
  return { subject, text: body, ...(site === "nordic-crypto" ? { html: emailHtml(site, lang, { title: subject, body, link, cta: false }) } : {}) };
}

// ---- Branded HTML alternative (Langskip palette, see nordiccrypto.no/media). Table layout + inline CSS for email clients.
// The text/plain body above stays the canonical version; html is sent alongside it.
const C = { sail: "#F0F1EC", pine: "#1D1C1A", sea: "#1E3A45", gold: "#D9A034", foam: "#BFD3D3" };
const F = { sans: "'Schibsted Grotesk',Helvetica,Arial,sans-serif", serif: "'Cormorant Garamond',Georgia,'Times New Roman',serif",
  mono: "'IBM Plex Mono',Menlo,Consolas,monospace" };
const LOGO = SITE_BASE + "assets/brand/mark-192.png";   // PNG on the live site (no SVG in email)
const B = {
  en: { btn: "Confirm subscription", alt: "Or copy this link into your browser:", visit: "Visit the site" },
  nn: { btn: "Stadfest abonnementet", alt: "Eller kopier denne lenkja inn i nettlesaren:", visit: "Gå til nettstaden" },
  nb: { btn: "Bekreft abonnementet", alt: "Eller kopier denne lenken inn i nettleseren:", visit: "Gå til nettstedet" },
  sv: { btn: "Bekräfta prenumerationen", alt: "Eller kopiera länken till din webbläsare:", visit: "Besök webbplatsen" },
  da: { btn: "Bekræft abonnementet", alt: "Eller kopiér linket ind i din browser:", visit: "Besøg sitet" },
  fi: { btn: "Vahvista tilaus", alt: "Tai kopioi tämä linkki selaimeesi:", visit: "Siirry sivustolle" },
  is: { btn: "Staðfesta áskrift", alt: "Eða afritaðu tengilinn í vafrann:", visit: "Fara á vefinn" },
};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const para = (t) => `<p style="margin:0 0 16px;font-family:${F.sans};font-size:16px;line-height:1.55;color:${C.pine}">${esc(t).replace(/\n/g, "<br>")}</p>`;
const button = (href, label) => `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px"><tr>` +
  `<td bgcolor="${C.gold}" style="border-radius:6px;background:${C.gold}"><a href="${esc(href)}" style="display:inline-block;padding:16px 32px;font-family:${F.sans};font-size:18px;font-weight:700;color:${C.pine};text-decoration:none;border-radius:6px">${esc(label)} &rarr;</a></td></tr></table>`;
const linkLine = (lang, href) => `<p style="margin:0 0 20px;font-family:${F.sans};font-size:13px;color:${C.sea}">${esc((B[lang] || B.en).alt)}<br>` +
  `<a href="${esc(href)}" style="font-family:${F.mono};font-size:12px;color:${C.sea};word-break:break-all">${esc(href)}</a></p>`;

export function emailHtml(site, lang, { title, body, link, cta }) {
  const s = SITES[site], home = s.base + (s.langs[lang] ?? ""), b = B[lang] || B.en;
  // Split the plain body: the bare link line becomes the button (or link block), the "{name} – {site}" sign-off goes to the footer.
  const blocks = body.trim().split(/\n\n+/).filter((p) => !p.startsWith(s.name + " – "));
  const inner = blocks.map((p) => {
    if (p.trim() === link) return cta ? button(link, b.btn) + linkLine(lang, link) : "";
    if (p.includes("\n" + link)) return para(p.replace("\n" + link, "")) + (cta ? "" : linkLine(lang, link).replace(esc(b.alt) + "<br>", ""));
    return para(p);
  }).join("");
  return `<!doctype html><html lang="${esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<meta name="color-scheme" content="light"><title>${esc(title)}</title></head>` +
    `<body style="margin:0;padding:0;background:${C.sail}">` +
    `<div style="display:none;max-height:0;overflow:hidden">${esc(title)}</div>` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="${C.sail}" style="background:${C.sail}"><tr><td align="center" style="padding:24px 12px">` +
    `<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid ${C.foam};border-radius:8px;overflow:hidden">` +
    // North Sea band with logo + wordmark
    `<tr><td bgcolor="${C.sea}" style="background:${C.sea};padding:22px 28px;border-bottom:4px solid ${C.gold}">` +
    `<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td style="padding-right:14px"><img src="${esc(LOGO)}" width="48" height="48" alt="" style="display:block;border:0"></td>` +
    `<td><div style="font-family:${F.serif};font-size:28px;font-weight:600;line-height:1;color:${C.sail}">${esc(s.name)}</div>` +
    `<div style="font-family:${F.mono};font-size:11px;letter-spacing:2px;text-transform:uppercase;color:${C.gold};padding-top:6px">Newsletter</div></td>` +
    `</tr></table></td></tr>` +
    `<tr><td style="padding:32px 28px 8px">` +
    `<h1 style="margin:0 0 20px;font-family:${F.serif};font-size:30px;line-height:1.15;font-weight:600;color:${C.pine}">${esc(title)}</h1>` +
    inner + `</td></tr>` +
    `<tr><td style="padding:0 28px"><div style="border-top:1px solid ${C.foam};font-size:0;line-height:0">&nbsp;</div></td></tr>` +
    `<tr><td style="padding:18px 28px 26px;font-family:${F.mono};font-size:12px;color:${C.sea}">` +
    `${esc(s.name)} &middot; <a href="${esc(home)}" style="color:${C.sea}">${esc(b.visit)}</a></td></tr>` +
    `</table></td></tr></table></body></html>`;
}
