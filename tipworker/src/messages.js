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
  return { subject: text(lang, "cs", v), text: text(lang, "cb", v) };
}
export function welcomeEmail(site, lang, link) {
  const v = { name: SITES[site].name, site: SITES[site].base + (SITES[site].langs[lang] ?? ""), link };
  return { subject: text(lang, "ws", v), text: text(lang, "wb", v) };
}
