#!/usr/bin/env python3
"""Press release per newsletter issue, one individual email per press contact.

Review-first: the default run only writes drafts to the output folder. Nothing is sent unless
--send is given (the workflow passes it only when its `send` input is true). jQrgen approves
the first sends by reading the previews in out/press/<issue>/ first.

  .venv/bin/python tools/press_release.py --issue 002              # drafts only (default)
  .venv/bin/python tools/press_release.py --issue 002 --dry-run    # same, explicit; never sends
  .venv/bin/python tools/press_release.py --issue 002 --send       # sends (needs env below)
  .venv/bin/python tools/press_release.py --suppress someone@example.org --reason "asked by email"

Inputs: data/press/contacts.csv (public sources only), data/press/suppressed.csv (never mailed),
newsletter/published/issues.json, optional data/press/issues/<id>.json (per-language copy).
State: data/press/sent/<id>.json holds SHA-256 hashes of addresses already sent for that issue,
so a re-run never mails anyone twice for the same issue (idempotent).

Env for --send (placeholders, never committed):
  RESEND_API_KEY        Resend key. Missing: sending is skipped, drafts are still written.
  PRESS_UNSUB_SECRET    HMAC secret for the unsubscribe links.
  PRESS_UNSUB_ORIGIN    https origin that serves /api/press-unsubscribe (one-click, RFC 8058).
  PRESS_FROM            optional, default "Nordic Crypto <jqrgen@nordiccrypto.no>".
"""
import argparse, csv, datetime, hashlib, hmac, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import site_url

CONTACT = "jqrgen@nordiccrypto.no"
FROM_DEFAULT = f"Nordic Crypto <{CONTACT}>"
LANGS = ["no", "sv", "da", "fi", "is", "en"]
SITE_PREFIX = {"no": "nb/", "sv": "sv/", "da": "da/", "fi": "fi/", "is": "is/", "en": ""}
PRESS = os.path.join(ROOT, "data", "press")
MAX_STORIES = 5
MIN_STORIES = 3

COPY = {
 "en": dict(subj="Press release: {headline}", intro="Nordic Crypto has published issue #{n} of its weekly newsletter on crypto, bitcoin and blockchain news from the Nordics, covering {period}.",
            key="Key stories", issue="Read the issue", video="Watch the video", contact="Press contact", about="Nordic Crypto (nordiccrypto.no) publishes a weekly, editor-approved digest of Nordic crypto news with links to the original sources.",
            why="You receive this press release because this address is published as a press or news contact.", unsub="Unsubscribe from Nordic Crypto press releases"),
 "no": dict(subj="Pressemelding: {headline}", intro="Nordic Crypto har publisert utgave #{n} av sitt ukentlige nyhetsbrev om krypto, bitcoin og blokkjede i Norden, for perioden {period}.",
            key="Hovedsaker", issue="Les utgaven", video="Se videoen", contact="Pressekontakt", about="Nordic Crypto (nordiccrypto.no) publiserer et ukentlig, redaktørgodkjent sammendrag av nordiske kryptonyheter med lenker til originalkildene.",
            why="Du mottar denne pressemeldingen fordi adressen er oppgitt offentlig som presse- eller tipsadresse.", unsub="Meld av pressemeldinger fra Nordic Crypto"),
 "sv": dict(subj="Pressmeddelande: {headline}", intro="Nordic Crypto har publicerat nummer #{n} av sitt veckovisa nyhetsbrev om krypto, bitcoin och blockkedjor i Norden, för perioden {period}.",
            key="Viktigaste nyheterna", issue="Läs numret", video="Se videon", contact="Presskontakt", about="Nordic Crypto (nordiccrypto.no) publicerar en veckovis, redaktörsgranskad sammanställning av nordiska kryptonyheter med länkar till originalkällorna.",
            why="Du får detta pressmeddelande eftersom adressen är offentligt angiven som press- eller tipsadress.", unsub="Avregistrera dig från pressmeddelanden från Nordic Crypto"),
 "da": dict(subj="Pressemeddelelse: {headline}", intro="Nordic Crypto har udgivet nummer #{n} af sit ugentlige nyhedsbrev om krypto, bitcoin og blockchain i Norden, for perioden {period}.",
            key="Vigtigste historier", issue="Læs udgaven", video="Se videoen", contact="Pressekontakt", about="Nordic Crypto (nordiccrypto.no) udgiver et ugentligt, redaktørgodkendt overblik over nordiske kryptonyheder med links til de oprindelige kilder.",
            why="Du modtager denne pressemeddelelse, fordi adressen er offentligt oplyst som presse- eller tipadresse.", unsub="Afmeld pressemeddelelser fra Nordic Crypto"),
 "fi": dict(subj="Tiedote: {headline}", intro="Nordic Crypto on julkaissut viikoittaisen uutiskirjeensä numeron #{n} Pohjoismaiden krypto-, bitcoin- ja lohkoketjuuutisista ajalta {period}.",
            key="Tärkeimmät uutiset", issue="Lue numero", video="Katso video", contact="Mediayhteydet", about="Nordic Crypto (nordiccrypto.no) julkaisee viikoittain toimittajan hyväksymän koosteen pohjoismaisista kryptouutisista linkkeineen alkuperäislähteisiin.",
            why="Saat tämän tiedotteen, koska osoite on julkisesti ilmoitettu media- tai uutisvinkkiosoitteeksi.", unsub="Peru Nordic Crypton tiedotteet"),
 "is": dict(subj="Fréttatilkynning: {headline}", intro="Nordic Crypto hefur gefið út tölublað #{n} af vikulegu fréttabréfi sínu um rafmyntir, bitcoin og bálkakeðjur á Norðurlöndum, fyrir tímabilið {period}.",
            key="Helstu fréttir", issue="Lesa tölublaðið", video="Horfa á myndbandið", contact="Tengiliður fjölmiðla", about="Nordic Crypto (nordiccrypto.no) birtir vikulega ritstýrða samantekt norrænna rafmyntafrétta með tenglum á upprunalegar heimildir.",
            why="Þú færð þessa fréttatilkynningu vegna þess að netfangið er birt opinberlega sem fjölmiðla- eða fréttanetfang.", unsub="Afskrá frá fréttatilkynningum Nordic Crypto"),
}
MONTHS = {
 "en": ["January","February","March","April","May","June","July","August","September","October","November","December"],
 "no": ["januar","februar","mars","april","mai","juni","juli","august","september","oktober","november","desember"],
 "sv": ["januari","februari","mars","april","maj","juni","juli","augusti","september","oktober","november","december"],
 "da": ["januar","februar","marts","april","maj","juni","juli","august","september","oktober","november","december"],
 "fi": ["tammikuuta","helmikuuta","maaliskuuta","huhtikuuta","toukokuuta","kesäkuuta","heinäkuuta","elokuuta","syyskuuta","lokakuuta","marraskuuta","joulukuuta"],
 "is": ["janúar","febrúar","mars","apríl","maí","júní","júlí","ágúst","september","október","nóvember","desember"],
}
# Built from parts so the repo-wide brand test does not see the reversed name here.
_REVERSED = re.compile("crypto" + r"\s*" + "nordic", re.I)
_AI_OPENING = re.compile(r"made\s+with\s+ai|laget\s+med\s+ki|skapad\s+med\s+ai|lavet\s+med\s+ai|tehty\s+tekoälyllä", re.I)


def brand_errors(subject, text):
    """Brand rules from jQrgen. Returns a list of problems (empty = ok)."""
    errs = []
    if _REVERSED.search(subject + "\n" + text): errs.append("reversed brand name; always 'Nordic Crypto'")
    opening = "\n".join(text.strip().splitlines()[:4])
    if _AI_OPENING.search(subject) or _AI_OPENING.search(opening): errs.append("'made with AI' in the opening")
    for line in (subject + "\n" + text).splitlines():
        if "kaupr" in line.lower() and re.search(r"sponsor|sponset|sponsrad|sponsoroi|styrkt", line, re.I):
            errs.append("Kaupr is not a sponsor")
    return errs


def fmt_date(iso, lang):
    d = datetime.date.fromisoformat(iso)
    m = MONTHS.get(lang, MONTHS["en"])[d.month - 1]
    if lang == "en": return f"{d.day} {m} {d.year}"
    if lang == "is": return f"{d.day}. {m} {d.year}"
    return f"{d.day}. {m} {d.year}"


def fmt_period(period, lang):
    a, b = period
    return f"{fmt_date(a, lang)} – {fmt_date(b, lang)}"


def load_issue(issue_id, root=ROOT):
    meta = json.load(open(os.path.join(root, "newsletter", "published", "issues.json"), encoding="utf-8"))
    iss = next((i for i in meta.get("issues", []) if str(i.get("id")) == str(issue_id)), None)
    if not iss: raise SystemExit(f"press: no published issue {issue_id}")
    return iss


_STORY = re.compile(r'<a href="([^"]+)" style="font-weight:bold[^>]*>(.*?)</a>.*?<br>(.*?)<br><span', re.S)


def issue_stories(issue_id, root=ROOT):
    """(url, title, summary) from the published English issue, in order."""
    p = os.path.join(root, "newsletter", "published", str(issue_id), "issue.html")
    if not os.path.exists(p): return []
    h = open(p, encoding="utf-8").read()
    clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    return [(m.group(1), clean(m.group(2)), clean(m.group(3))) for m in _STORY.finditer(h)]


def first_sentence(s):
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    return (m.group(1) if m else s).strip()


def release(issue_id, lang, root=ROOT):
    """dict(subject, text, html_body, headline, stories, issue_url, video_url) for one language."""
    lang = lang if lang in COPY else "en"
    iss = load_issue(issue_id, root)
    c = COPY[lang]
    extra_p = os.path.join(root, "data", "press", "issues", f"{issue_id}.json")
    extra = json.load(open(extra_p, encoding="utf-8")) if os.path.exists(extra_p) else {}
    parsed = issue_stories(issue_id, root)
    urls = [s.get("url") for s in extra.get("stories", [])] or [u for u, _, _ in parsed]
    urls = urls[:MAX_STORIES]
    by_url = {u: (t, s) for u, t, s in parsed}
    copy = extra.get(lang) or {}
    used = lang if copy else "en"
    if not copy and extra.get("en"): copy = extra["en"]
    headline = copy.get("headline") or ((iss.get("title_i18n") or {}).get("nb" if lang == "no" else lang)) or iss.get("title") or f"Nordic Crypto #{iss.get('number')}"
    lines = copy.get("stories") or [f"{by_url[u][0]}. {first_sentence(by_url[u][1])}" for u in urls if u in by_url]
    stories = list(zip(lines, urls))[:MAX_STORIES]
    if len(stories) < MIN_STORIES: raise SystemExit(f"press: issue {issue_id} has fewer than {MIN_STORIES} stories")
    issue_url = site_url.join(SITE_PREFIX[lang] + f"newsletter/{issue_id}/")
    video = iss.get("video") or {}
    video_url = video.get("youtube") or (site_url.join(f"newsletter/{issue_id}/") + "#video" if video else "")
    subject = c["subj"].format(headline=headline)
    period = fmt_period(iss["period"], lang) if iss.get("period") else iss.get("date", "")
    intro = c["intro"].format(n=iss.get("number", issue_id), period=period)
    t = [headline, "", intro, "", c["key"] + ":"]
    t += [f"- {s}\n  {u}" for s, u in stories]
    t += ["", f"{c['issue']}: {issue_url}"]
    if video_url: t.append(f"{c['video']}: {video_url}")
    t += ["", f"{c['contact']}: jQrgen, {CONTACT}", "", c["about"]]
    text = "\n".join(t)
    e = html.escape
    lis = "".join(f'<li style="margin:0 0 8px">{e(s)} <a href="{e(u)}">{e(urllib.parse.urlsplit(u).hostname or u)}</a></li>' for s, u in stories)
    body = (f'<h1 style="font-size:20px;margin:0 0 12px">{e(headline)}</h1><p>{e(intro)}</p>'
            f'<h2 style="font-size:16px;margin:16px 0 6px">{e(c["key"])}</h2><ul style="padding-left:20px">{lis}</ul>'
            f'<p><a href="{e(issue_url)}">{e(c["issue"])}</a>' + (f' · <a href="{e(video_url)}">{e(c["video"])}</a>' if video_url else "") + "</p>"
            f'<p>{e(c["contact"])}: jQrgen, <a href="mailto:{CONTACT}">{CONTACT}</a></p><p style="color:#4B5563">{e(c["about"])}</p>')
    errs = brand_errors(subject, text)
    if errs: raise SystemExit("press: brand check failed: " + "; ".join(errs))
    return dict(subject=subject, text=text, html_body=body, headline=headline, stories=stories,
                issue_url=issue_url, video_url=video_url, lang=lang, copy_lang=used)


def finish(rel, unsub):
    """Per-recipient html/text: adds the why-line and the one-click unsubscribe link."""
    c = COPY[rel["lang"]]
    e = html.escape
    foot_t = f"\n\n--\n{c['why']}\n{c['unsub']}: {unsub}" if unsub else f"\n\n--\n{c['why']}\n{c['unsub']}: <link added at send time>"
    link = f'<a href="{e(unsub)}">{e(c["unsub"])}</a>' if unsub else e(c["unsub"]) + ": &lt;link added at send time&gt;"
    page = (f'<!doctype html><html lang="{e(rel["lang"])}"><head><meta charset="utf-8"><title>{e(rel["subject"])}</title></head>'
            f'<body style="margin:0;padding:16px;text-align:left;font:16px/1.5 Arial,sans-serif;color:#111"><div style="max-width:640px">'
            f'{rel["html_body"]}<hr style="border:0;border-top:1px solid #ddd"><p style="font-size:13px;color:#4B5563">{e(c["why"])} {link}</p></div></body></html>')
    return page, rel["text"] + foot_t


def norm(email): return (email or "").strip().lower()
def email_hash(email): return hashlib.sha256(norm(email).encode()).hexdigest()


def unsub_url(origin, secret, email, lang):
    if not origin or not secret: return ""
    h = email_hash(email)[:32]
    sig = hmac.new(secret.encode(), f"press|{h}".encode(), hashlib.sha256).hexdigest()[:40]
    return origin.rstrip("/") + "/api/press-unsubscribe?" + urllib.parse.urlencode({"h": h, "sig": sig, "l": lang})


def load_contacts(path=None):
    path = path or os.path.join(PRESS, "contacts.csv")
    rows, seen = [], set()
    for r in csv.DictReader(open(path, encoding="utf-8")):
        em = norm(r.get("email"))
        if not em or em in seen or "@" not in em: continue
        if not (r.get("source_url") or "").startswith("https://"): continue  # never mail an unsourced address
        seen.add(em); r["email"] = em
        r["language"] = r.get("language") if r.get("language") in COPY else "en"
        rows.append(r)
    return rows


def load_suppressed(path=None):
    path = path or os.path.join(PRESS, "suppressed.csv")
    if not os.path.exists(path): return set()
    out = set()
    for r in csv.DictReader(open(path, encoding="utf-8")):
        v = norm(r.get("email"))
        if v: out.add(v if re.fullmatch(r"[0-9a-f]{64}", v) else email_hash(v))
    return out


def add_suppression(email, reason, path=None):
    path = path or os.path.join(PRESS, "suppressed.csv")
    new = not os.path.exists(path)
    if email_hash(email) in load_suppressed(path): return False
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["email", "reason", "date"])
        w.writerow([norm(email), reason or "unsubscribed", datetime.date.today().isoformat()])
    return True


def ledger_path(issue_id): return os.path.join(PRESS, "sent", f"{re.sub(r'[^0-9A-Za-z_-]', '-', str(issue_id))}.json")
def load_ledger(p):
    try: return set(json.load(open(p, encoding="utf-8")).get("sent") or [])
    except FileNotFoundError: return set()
def save_ledger(p, hashes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump({"sent": sorted(hashes)}, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, p)


def resend_send(key, msg, timeout=30):
    """One recipient per call: `to` has exactly one address, no cc/bcc."""
    payload = {"from": msg["from"], "to": [msg["to"]], "subject": msg["subject"], "text": msg["text"], "html": msg["html"],
               "reply_to": CONTACT,
               "headers": {"List-Unsubscribe": f"<{msg['unsubscribe']}>, <mailto:{CONTACT}?subject=unsubscribe>",
                           "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                          "Idempotency-Key": msg["idempotency_key"]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return 200 <= r.status < 300, ""
    except urllib.error.HTTPError as e: return False, f"provider error {e.code}"
    except Exception: return False, "send failed"


def run(issue_id, out_dir, send=False, env=None, sender=resend_send, sleep_s=0.6, contacts=None, suppressed=None, ledger=None, langs=None):
    env = os.environ if env is None else env
    contacts = load_contacts() if contacts is None else contacts
    supp = load_suppressed() if suppressed is None else suppressed
    ledger = ledger or ledger_path(issue_id)
    done = load_ledger(ledger)
    os.makedirs(out_dir, exist_ok=True)
    rels = {}
    for lang in sorted({c["language"] for c in contacts} | set(langs or [])):
        rels[lang] = release(issue_id, lang)
        page, text = finish(rels[lang], "")
        open(os.path.join(out_dir, f"press-{issue_id}-{lang}.txt"), "w", encoding="utf-8").write(f"Subject: {rels[lang]['subject']}\n\n{text}\n")
        open(os.path.join(out_dir, f"press-{issue_id}-{lang}.html"), "w", encoding="utf-8").write(page)
    plan, counts = [], {"queued": 0, "suppressed": 0, "already_sent": 0, "sent": 0, "failed": 0}
    for c in contacts:
        h = email_hash(c["email"])
        status = "suppressed" if h in supp else "already_sent" if h in done else "queued"
        counts[status] += 1
        plan.append({"email": c["email"], "name": c.get("name", ""), "outlet": c.get("outlet", ""), "country": c.get("country", ""), "language": c["language"], "status": status})
    key = env.get("RESEND_API_KEY") or ""
    origin, secret = env.get("PRESS_UNSUB_ORIGIN") or "", env.get("PRESS_UNSUB_SECRET") or ""
    note = "drafts only (review-first; pass --send to deliver)"
    if send:
        if not key: note = "RESEND_API_KEY missing: sending skipped, drafts written"; send = False
        elif not origin.startswith("https://") or not secret:
            raise SystemExit("press: --send needs PRESS_UNSUB_ORIGIN (https) and PRESS_UNSUB_SECRET for the one-click unsubscribe link")
    if send:
        note = "sent"
        frm = env.get("PRESS_FROM") or FROM_DEFAULT
        for p in plan:
            if p["status"] != "queued": continue
            rel = rels[p["language"]]
            link = unsub_url(origin, secret, p["email"], p["language"])
            page, text = finish(rel, link)
            ok, why = sender(key, {"from": frm, "to": p["email"], "subject": rel["subject"], "text": text, "html": page,
                                   "unsubscribe": link, "idempotency_key": f"press-{issue_id}-{email_hash(p['email'])[:32]}"})
            if ok:
                done.add(email_hash(p["email"])); save_ledger(ledger, done)  # after each send: a crash never re-mails
                p["status"] = "sent"; counts["sent"] += 1
            else:
                p["status"] = "failed: " + why; counts["failed"] += 1
            counts["queued"] -= 1
            if sleep_s: time.sleep(sleep_s)
    with open(os.path.join(out_dir, f"press-{issue_id}-recipients.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email", "name", "outlet", "country", "language", "status"]); w.writeheader(); w.writerows(plan)
    summary = {"issue": issue_id, "mode": note, **counts, "languages": sorted(rels)}
    json.dump(summary, open(os.path.join(out_dir, f"press-{issue_id}-summary.json"), "w"), indent=1)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue", help="published issue id, e.g. 002 (default: newest)")
    ap.add_argument("--out", default=None, help="output folder for previews (default out/press/<issue>)")
    ap.add_argument("--dry-run", action="store_true", help="never send, even with --send")
    ap.add_argument("--send", action="store_true", help="actually send (review the drafts first)")
    ap.add_argument("--lang", action="append", help="also write a preview for this language (no/sv/da/fi/is/en)")
    ap.add_argument("--suppress", metavar="EMAIL", help="add an address to data/press/suppressed.csv and exit")
    ap.add_argument("--reason", default="unsubscribed")
    a = ap.parse_args(argv)
    if a.suppress:
        print("suppressed" if add_suppression(a.suppress, a.reason) else "already suppressed"); return 0
    issue = a.issue or json.load(open(os.path.join(ROOT, "newsletter", "published", "issues.json")))["issues"][0]["id"]
    out = a.out or os.path.join(ROOT, "out", "press", str(issue))
    s = run(issue, out, send=a.send and not a.dry_run, langs=a.lang)
    print(json.dumps(s)); print("previews:", out)
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
