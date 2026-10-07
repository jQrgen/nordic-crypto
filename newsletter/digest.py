#!/usr/bin/env python3
"""Weekly newsletter digest for Nordic Crypto, generated ONLY from editor-approved stories: it reads data/news.json of a
PUBLIC build (default site/; refuses a preview build), so nothing pending or rejected can end up in a newsletter.
Writes Markdown (paste into the Substack editor), plain text and simple email HTML to newsletter/out/ (gitignored).
Sends nothing.
Usage: .venv/bin/python newsletter/digest.py [--lang en|nn|nb|sv|da|fi|is] [--days 7] [--until YYYY-MM-DD] [--site-dir site]
Language rule: Norwegian (nn/nb) text says «kunstig intelligens», never AI or KI (checked before writing)."""
import argparse, datetime as dt, html, json, os, re, sys
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import i18n
import site_url
BASE = site_url.BASE; OSLO = ZoneInfo("Europe/Oslo")
T = {
 "en": dict(h="Nordic Crypto weekly", intro="The week’s crypto, bitcoin and blockchain stories from the Nordics that our editor has approved. Each item links to the original source.",
            orig="original", more="All stories, the calendar and the who’s who", none="No approved stories this week.",
            foot="Nordic Crypto is run by Jørgen S. Notland (jQrgen), Oslo. Made with the help of artificial intelligence, with human editors (jQrgen and the Nordic Crypto editor). Not investment advice.",
            why="You get this email because you subscribed to the Nordic Crypto newsletter."),
 "nn": dict(h="Nordic Crypto – veka som gjekk", intro="Saker om krypto, bitcoin og blokkjede frå Norden som redaktøren vår har godkjent denne veka. Kvar sak lenkjer til kjelda.",
            orig="original", more="Alle sakene, kalenderen og kven er kven", none="Ingen godkjende saker denne veka.",
            foot="Nordic Crypto blir driven av Jørgen S. Notland (jQrgen), Oslo. Laga med hjelp av kunstig intelligens, med menneskelege redaktørar (jQrgen og Nordic Crypto-redaktøren). Ikkje investeringsråd.",
            why="Du får denne e-posten fordi du har abonnert på nyheitsbrevet frå Nordic Crypto."),
 "nb": dict(h="Nordic Crypto – uka som gikk", intro="Saker om krypto, bitcoin og blokkjede fra Norden som redaktøren vår har godkjent denne uka. Hver sak lenker til kilden.",
            orig="original", more="Alle sakene, kalenderen og hvem er hvem", none="Ingen godkjente saker denne uka.",
            foot="Nordic Crypto drives av Jørgen S. Notland (jQrgen), Oslo. Laget med hjelp av kunstig intelligens, med menneskelige redaktører (jQrgen og Nordic Crypto-redaktøren). Ikke investeringsråd.",
            why="Du får denne e-posten fordi du har abonnert på nyhetsbrevet fra Nordic Crypto."),
 "sv": dict(h="Nordic Crypto – veckan som gick", intro="Veckans nyheter om krypto, bitcoin och blockkedjor från Norden som vår redaktör har godkänt. Varje nyhet länkar till källan.",
            orig="original", more="Alla nyheter, kalendern och vem är vem", none="Inga godkända nyheter den här veckan.",
            foot="Nordic Crypto drivs av Jørgen S. Notland (jQrgen), Oslo. Gjort med hjälp av artificiell intelligens, med mänskliga redaktörer (jQrgen och Nordic Crypto-redaktören). Inga investeringsråd.",
            why="Du får det här mejlet eftersom du prenumererar på Nordic Cryptos nyhetsbrev."),
 "da": dict(h="Nordic Crypto – ugen der gik", intro="Ugens historier om krypto, bitcoin og blockchain fra Norden, som vores redaktør har godkendt. Hver historie linker til kilden.",
            orig="original", more="Alle historier, kalenderen og hvem er hvem", none="Ingen godkendte historier i denne uge.",
            foot="Nordic Crypto drives af Jørgen S. Notland (jQrgen), Oslo. Lavet med hjælp fra kunstig intelligens, med menneskelige redaktører (jQrgen og Nordic Crypto-redaktøren). Ikke investeringsrådgivning.",
            why="Du får denne e-mail, fordi du abonnerer på Nordic Cryptos nyhedsbrev."),
 "fi": dict(h="Nordic Crypto – viikon uutiset", intro="Viikon krypto-, bitcoin- ja lohkoketjuuutiset Pohjoismaista, jotka toimittajamme on hyväksynyt. Jokainen uutinen linkittää lähteeseen.",
            orig="alkuperäinen", more="Kaikki uutiset, kalenteri ja kuka on kuka", none="Tällä viikolla ei hyväksyttyjä uutisia.",
            foot="Nordic Cryptoa pitää Jørgen S. Notland (jQrgen), Oslo. Tehty tekoälyn avulla, ihmistoimittajina jQrgen ja Nordic Crypton toimittaja. Ei sijoitusneuvontaa.",
            why="Saat tämän viestin, koska olet tilannut Nordic Crypton uutiskirjeen."),
 "is": dict(h="Nordic Crypto – vikan sem leið", intro="Fréttir vikunnar um kriptó, bitcoin og bálkakeðjur frá Norðurlöndum sem ritstjórinn okkar hefur samþykkt. Hver frétt tengir á heimildina.",
            orig="upprunalegt", more="Allar fréttir, dagatalið og hver er hver", none="Engar samþykktar fréttir þessa vikuna.",
            foot="Nordic Crypto er rekið af Jørgen S. Notland (jQrgen), Osló. Unnið með aðstoð gervigreindar, með mannlegum ritstjórum (jQrgen og ritstjóra Nordic Crypto). Ekki fjárfestingarráðgjöf.",
            why="Þú færð þennan póst vegna þess að þú ert áskrifandi að fréttabréfi Nordic Crypto."),
}
NO_AIKI = re.compile(r"(?<![\w-])(?:AI|KI)(?![\w])")
COUNTRY_ORDER = ["NO", "SE", "DK", "FI", "IS", "NORDIC", "EU"]

def pick(items, since, until):
    out = []
    for i in items:
        if i.get("status") != "published" or not (i.get("summary") or "").strip(): continue
        d = dt.datetime.fromisoformat(i["published"]).astimezone(OSLO).date()
        if since <= d <= until: out.append(dict(i, _d=d))
    return sorted(out, key=lambda i: (COUNTRY_ORDER.index(i["country"]) if i["country"] in COUNTRY_ORDER else 99, -i["_d"].toordinal()))

def render(items, lang, since, until):
    s = T[lang]; home = BASE + ("" if lang == "en" else lang + "/")
    rng = f"{i18n.short_dm(lang, since)}–{i18n.short_date(lang, until)}"
    md = [f"# {s['h']}", f"*{rng}*", "", s["intro"], ""]; tx = [s["h"], rng, "", s["intro"], ""]
    hm = [f'<h1 style="font-size:24px;margin:0 0 4px">{html.escape(s["h"])}</h1><p style="color:#4B5563;margin:0 0 12px">{html.escape(rng)}</p><p>{html.escape(s["intro"])}</p>']
    cur = None
    for i in items:
        if i["country"] != cur:
            cur = i["country"]; cn = i18n.t(lang, "c_" + cur)
            md += [f"## {cn}", ""]; tx += [cn.upper(), ""]; hm.append(f'<h2 style="font-size:18px;margin:20px 0 6px">{html.escape(cn)}</h2>')
        title = i.get("title_en") if lang == "en" and i.get("title_en") else i["title"]
        summ = (i.get("summary_i18n") or {}).get(lang) if lang != "en" else None
        summ = summ or i["summary"]
        meta = [i["source_name"], i18n.short_date(lang, i["_d"])]
        if i.get("paywall") is True: meta.append(i18n.t(lang, "paywall"))
        orig = f" ({s['orig']}: {i['title']})" if title != i["title"] else ""
        lg = (i.get("source_logo") or {}).get("file") if isinstance(i.get("source_logo"), dict) else None
        logo = (f'<img src="{html.escape(BASE + lg)}" alt="" height="18" style="height:18px;width:auto;max-width:96px;object-fit:contain;vertical-align:middle;margin:0 6px 0 0;background:#fff">' if lg else "")
        md += [f"**[{title}]({i['url']})**{orig}  ", f"{summ}  ", f"*{' · '.join(meta)}*", ""]
        tx += [title + orig, summ, " · ".join(meta), i["url"], ""]
        hm.append(f'<p style="margin:0 0 14px;text-align:left"><a href="{html.escape(i["url"])}" style="font-weight:bold;color:#0f5ea8">{html.escape(title)}</a>{html.escape(orig)}<br>{html.escape(summ)}<br><span style="color:#4B5563;font-size:13px;text-align:left">{logo}{html.escape(" · ".join(meta))}</span></p>')
    if not items: md += [s["none"], ""]; tx += [s["none"], ""]; hm.append(f"<p>{html.escape(s['none'])}</p>")
    md += [f"[{s['more']}]({home})", "", "---", "", s["foot"], "", f"*{s['why']}*", ""]
    tx += [f"{s['more']}: {home}", "", "--", s["foot"], "", s["why"], "{{unsubscribe}}", ""]
    hm.append(f'<p><a href="{home}">{html.escape(s["more"])}</a></p><hr style="border:0;border-top:1px solid #d1d5db">'
              f'<p style="font-size:13px;color:#4B5563">{html.escape(s["foot"])}</p><p style="font-size:13px;color:#4B5563">{html.escape(s["why"])} <a href="{{{{unsubscribe}}}}">Unsubscribe</a></p>')
    page = f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{html.escape(s["h"])}</title></head><body style="margin:0;padding:20px;font:16px/1.5 Arial,sans-serif;color:#111"><div style="max-width:640px;margin:0 auto">{"".join(hm)}</div></body></html>\n'
    return "\n".join(md), "\n".join(tx), page

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--lang", default="en", choices=list(T)); a.add_argument("--days", type=int, default=7)
    a.add_argument("--until"); a.add_argument("--site-dir", default=os.path.join(ROOT, "site")); a.add_argument("--out", default=os.path.join(ROOT, "newsletter", "out"))
    o = a.parse_args(argv)
    if os.path.exists(os.path.join(o.site_dir, ".preview")): raise SystemExit("digest: refusing a preview build – run ./build.sh (public) first")
    news = json.load(open(os.path.join(o.site_dir, "data", "news.json"), encoding="utf-8"))
    if news.get("preview"): raise SystemExit("digest: refusing preview data")
    until = dt.date.fromisoformat(o.until) if o.until else dt.datetime.now(OSLO).date(); since = until - dt.timedelta(days=o.days - 1)
    items = pick(news["items"], since, until); md, tx, hp = render(items, o.lang, since, until)
    if o.lang in ("nn", "nb"):
        bad = [m.group(0) for m in NO_AIKI.finditer(re.sub(r"https?://\S+", "", md))]
        own = [b for b in bad if not any(b in i["title"] for i in items)]   # external headlines stay as published
        if own: raise SystemExit(f"digest: «AI»/«KI» in our own Norwegian text: {own}")
    os.makedirs(o.out, exist_ok=True); stem = os.path.join(o.out, f"digest-{until:%Y-%m-%d}-{o.lang}")
    for ext, body in (("md", md), ("txt", tx), ("html", hp)): open(f"{stem}.{ext}", "w", encoding="utf-8").write(body)
    print(f"digest: {len(items)} approved stories {since}–{until} ({o.lang}) -> {stem}.md/.txt/.html")
    return stem

if __name__ == "__main__": main()
