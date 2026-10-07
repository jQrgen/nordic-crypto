"""Event NFT prototype (off unless NC_EVENT_NFT=1 or queue/approved.json features.event_nft).

Generates a deterministic card from public event facts, a placeholder treasury
for Nexa and Bitcoin Cash, and the HTML blocks the site shows. No keys, no
mainnet transactions, no wallet is opened.

The public card never includes a NexaID, a Bitcoin Cash address, an attendee
name, or any other personal data. See docs/event-nft-design.md.
"""
import hashlib
import html
import json
import os

import event_select

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "data", "event_nft_fixture.json")
CAPS = os.path.join(ROOT, "mintworker", "caps.json")
PLACEHOLDER_NEXA = "placeholder:nexa:nordic-crypto-minting-treasury"
PLACEHOLDER_BCH = "placeholder:bch:nordic-crypto-minting-treasury"
COUNTRY = {
    "NO": "Norway", "SE": "Sweden", "DK": "Denmark", "FI": "Finland", "IS": "Iceland",
    "NORDIC": "Nordic", "EU": "EU",
}
CHAINS = ("nexa", "bch")
KINDS = ("pre", "ongoing")

CSS = """
.nftmint{margin:8px 0 2px;padding-top:8px;border-top:1px solid var(--line);text-align:start}
.nftmint p,.nftmint h4,.nftmint dl,.nftmint dd{text-align:start}
.nftmint summary{cursor:pointer;display:inline-block;padding:8px 14px;background:var(--ink);color:#fff;font-weight:700;list-style:none}
.nftmint summary::-webkit-details-marker{display:none}
a.nftbtn{display:inline-block;padding:8px 14px;background:var(--ink);color:#fff;text-decoration:none;font-weight:700}
.nftdlg{margin:8px 0 4px;padding:10px 12px;border:1px solid var(--line);background:var(--soft);max-width:36rem;text-align:start}
.nftdlg img.art{width:180px;height:180px;display:block;background:#fff;border:1px solid var(--line)}
.nftdlg img.qr{width:112px;height:112px;display:block;background:#fff;border:1px solid var(--line);margin-top:8px}
.nftmint dt{font-weight:700;margin-top:6px}.nftmint dd{margin:0}
.trewrap{display:flex;flex-wrap:wrap;gap:28px;align-items:flex-start;justify-content:flex-start}
.trecol{flex:1 1 280px;max-width:440px;text-align:start}
.trecol img{width:168px;height:168px;display:block;background:#fff;border:1px solid var(--line)}
.placeholder{border:1px solid var(--warm);background:#fffbeb;padding:8px 10px;text-align:start}
"""


def enabled():
    """Public builds leave this off. NC_EVENT_NFT=1 is the local prototype switch."""
    if os.environ.get("NC_EVENT_NFT") == "1":
        return True
    path = os.path.join(ROOT, "queue", "approved.json")
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool((doc.get("features") or {}).get("event_nft"))


def load_fixture():
    doc = json.load(open(FIXTURE, encoding="utf-8"))
    if doc["nexa"]["address"] != PLACEHOLDER_NEXA or doc["bch"]["address"] != PLACEHOLDER_BCH:
        raise RuntimeError("event NFT fixture addresses must stay the documented placeholders")
    return doc


def load_caps():
    """Same numbers the mint Worker enforces. The page does not keep a second copy."""
    return json.load(open(CAPS, encoding="utf-8"))


def judge(balance, floor, low, total):
    """ok, low, or empty. Empty means one more mint would cross the floor or the fee."""
    if balance < total or balance <= floor:
        return "empty"
    if balance < low:
        return "low"
    return "ok"


def _chain_view(raw, chain, caps):
    spec = caps[chain]
    network, airdrop = int(spec["network"]), int(spec["airdrop"])
    total = network + airdrop
    floor, low = int(spec["reserve"]), int(spec["low_below"])
    target = int(spec["hot_balance_target"])
    balance = int(raw["balance_nex"] if chain == "nexa" else raw["balance_sats"])
    unit = spec["unit"]
    status = judge(balance, floor, low, total)
    address = raw["address"]
    return {
        "chain": chain,
        "status": status,
        "needs_funding": status in ("low", "empty"),
        "intentionally_small": True,
        "address": address,
        "refill_address": address,
        "address_placeholder": True,
        "balance": {"amount": balance, "unit": unit},
        "hot_balance_target": {"amount": target, "unit": unit},
        "above_target": balance > target,
        "floor": {"amount": floor, "unit": unit},
        "low_below": {"amount": low, "unit": unit},
        "per_event": int(spec["per_event"]),
        "per_day": int(spec["per_day"]),
        "per_identity": spec["per_identity"],
        "mints_paid": int(raw["mints_paid"]),
        "per_mint": {
            "network": {"amount": network, "unit": unit},
            "airdrop": {"amount": airdrop, "unit": unit},
            "total": {"amount": total, "unit": unit},
        },
    }


def treasury_document(page_url):
    """Public API body. Caps from mintworker/caps.json. Sample balances, not a chain lookup."""
    raw, caps = load_fixture(), load_caps()
    nexa, bch = _chain_view(raw["nexa"], "nexa", caps), _chain_view(raw["bch"], "bch", caps)
    rank = {"ok": 0, "low": 1, "empty": 2}
    worst = nexa if rank[nexa["status"]] >= rank[bch["status"]] else bch
    return {
        "feature": "event_nft",
        "prototype": True,
        "intentionally_small": True,
        "note": "Hot wallets are intentionally small and refilled by hand. The addresses are those hot wallets. These values are placeholders and sample balances, not a live chain lookup. Do not send funds.",
        "status": worst["status"],
        "needs_funding": worst["needs_funding"],
        "app_prompt": {
            "show": worst["needs_funding"],
            "rule": "Show a funding prompt only when needs_funding is true (status low or empty). Stay quiet when status is ok. Use nexa.needs_funding and bch.needs_funding to name the chain.",
        },
        "nexa": nexa,
        "bch": bch,
        "page": page_url,
    }


def _credit(event):
    name = (event.get("source") or "").strip()
    url = (event.get("source_url") or event.get("url") or "").strip()
    when = (event.get("found") or "").strip()
    if not name or not url:
        return None
    block = {"name": name, "url": url}
    if when:
        block["retrieved_at"] = when
    return block


def _registered(event):
    fact = event_select.attendees_fact(event)
    if not fact:
        return {
            "count": None,
            "source_name": None,
            "source_url": None,
            "retrieved_at": None,
            "note": "The source record does not state a number of registered participants.",
        }
    credit = fact["credit"]
    return {
        "count": fact["count"],
        "source_name": credit.get("name"),
        "source_url": credit.get("url"),
        "retrieved_at": credit.get("retrieved"),
        "note": None,
    }


def _facts(event, kind):
    """General event facts only. No attendee list and no minter identity."""
    country = event.get("country") or ""
    reg = _registered(event)
    return {
        "event_id": event.get("id"),
        "kind": kind,
        "kind_label": "I'm going" if kind == "pre" else "I was there",
        "title": event.get("title") or "",
        "start": event.get("start"),
        "end": event.get("end"),
        "venue": event.get("place") or None,
        "city": event.get("city") or None,
        "country_code": country or None,
        "country": COUNTRY.get(country, country or None),
        "organiser": event.get("organiser") or None,
        "event_url": event.get("url") or None,
        "source": _credit(event),
        "registered": reg,
    }


def info_text(facts):
    """Plain sentences for Wally's info field and for a CashTokens description."""
    bits = [facts["title"] + ".", facts["kind_label"] + "."]
    when = " – ".join(x for x in (facts.get("start"), facts.get("end")) if x)
    if when:
        bits.append(when + ".")
    venue = facts.get("venue") or ""
    where = ", ".join(x for x in (
        facts.get("venue"),
        facts.get("city") if facts.get("city") and facts["city"] not in venue else None,
        facts.get("country"),
    ) if x)
    if where:
        bits.append(where + ".")
    if facts.get("organiser"):
        bits.append("Organiser: " + facts["organiser"] + ".")
    if facts.get("event_url"):
        bits.append("Event page: " + facts["event_url"] + ".")
    src = facts.get("source") or {}
    if src.get("name"):
        line = "Data source: " + src["name"]
        if src.get("url"):
            line += " (" + src["url"] + ")"
        if src.get("retrieved_at"):
            line += ", retrieved " + src["retrieved_at"]
        bits.append(line + ".")
    reg = facts.get("registered") or {}
    if reg.get("count") is None:
        bits.append("Registered participants: not stated in the source record.")
    else:
        line = "Registered participants: " + str(reg["count"])
        if reg.get("source_name"):
            line += ". Count source: " + reg["source_name"]
            if reg.get("source_url"):
                line += " (" + reg["source_url"] + ")"
            if reg.get("retrieved_at"):
                line += ", retrieved " + reg["retrieved_at"]
        bits.append(line + ".")
    return " ".join(bits)


def nexa_metadata(event, kind, media):
    """info.json fields Wally Wallet reads. Identity is intentionally absent."""
    facts = _facts(event, kind)
    text = info_text(facts)
    year = (facts.get("start") or "")[:4]
    keywords = ", ".join(x for x in (
        "event", facts.get("city"), facts.get("country"), year, facts["kind_label"],
    ) if x)
    return {
        "niftyVer": "2.0",
        "title": facts["title"],
        "series": "Nordic Crypto · " + facts["kind_label"],
        "author": "Nordic Crypto",
        "keywords": keywords,
        "info": "<p>" + html.escape(text, quote=False) + "</p>",
        "license": "CC BY 4.0",
        "appuri": media["page"],
        "media": {"cardf": media["front"], "cardb": media["back"], "public": media["front"]},
        "data": facts,
    }


def bch_metadata(event, kind, media):
    """What a BCMR-aware wallet shows. The commitment is a content hash, not an identity."""
    facts = _facts(event, kind)
    text = info_text(facts)
    body = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    commitment = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "name": facts["title"],
        "series": "Nordic Crypto · " + facts["kind_label"],
        "description": text,
        "symbol": "NCEVENT",
        "is_nft": True,
        "kind": facts["kind_label"],
        "license": "CC BY 4.0",
        "uris": {"icon": media["front"], "web": media["page"]},
        "commitment_hex": commitment,
        "commitment_note": "SHA-256 of the public event facts. Not a person, not a NexaID, not a Bitcoin Cash address.",
        "data": facts,
    }


def file_stem(event_id, kind, chain):
    return f"{event_id}-{kind}-{chain}"


def media_urls(base, event_id, kind, chain):
    stem = file_stem(event_id, kind, chain)
    root = base.rstrip("/") + "/assets/nft/"
    return {
        "front": root + stem + "-front.png",
        "back": root + stem + "-back.png",
        "page": base.rstrip("/") + "/events/" + event_id + "/",
        "qr": root + stem + "-qr.png",
    }


def _font(size, bold=False):
    from PIL import ImageFont
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = "/usr/share/fonts/truetype/dejavu/" + name
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in (text or "").split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines[:5]


def render_card(event, kind, chain, face, size=640):
    """Square card. Geometry comes from the event id. No photographs and no people."""
    from PIL import Image, ImageDraw
    facts = _facts(event, kind)
    accent = "#0f5ea8" if chain == "nexa" else "#0b7a4b"
    im = Image.new("RGB", (size, size), "#ffffff")
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, 12, size], fill=accent)
    seed = hashlib.sha256(f"{event.get('id')}|{kind}|{chain}|{face}".encode()).digest()
    for i in range(7):
        h = 24 + (seed[i] % 70)
        y = 96 + i * 72
        dr.rectangle([size - 40, y, size - 18, min(size - 24, y + h)], fill=accent if seed[i + 8] % 2 == 0 else "#111111")
    brand = _font(18, True)
    dr.text((28, 22), "NORDIC CRYPTO", font=brand, fill=accent)
    label = "I'M GOING" if kind == "pre" else "I WAS THERE"
    if face == "back":
        label = "CARD BACK · " + label
    dr.text((28, 52), label, font=_font(28, True), fill="#111111")
    chain_name = "NEXA" if chain == "nexa" else "BITCOIN CASH"
    dr.text((28, 92), chain_name, font=_font(16, True), fill=accent)
    y = 140
    title_font = _font(32, True)
    for line in _wrap(dr, facts["title"], title_font, size - 88):
        dr.text((28, y), line, font=title_font, fill="#111111")
        y += 40
    y += 8
    body = _font(18)
    when = " – ".join(x for x in ((facts.get("start") or "")[:16], (facts.get("end") or "")[:16]) if x)
    where = ", ".join(x for x in (facts.get("city"), facts.get("country")) if x)
    for line in (when, where, facts.get("organiser") or ""):
        if not line:
            continue
        dr.text((28, y), line[:72], font=body, fill="#4B5563")
        y += 28
    dr.text((28, size - 36), "General event facts only", font=_font(14), fill="#4B5563")
    return im


def render_qr(url, path):
    import segno
    segno.make(url, error="m").save(path, scale=6, border=2, dark="#111111")


def prepare(site, base, events, now):
    """Write shared card images once per build. Safe to skip when the flag is off."""
    if not enabled():
        return
    folder = os.path.join(site, "assets", "nft")
    os.makedirs(folder, exist_ok=True)
    raw = load_fixture()
    for chain, addr in (("nexa", raw["nexa"]["address"]), ("bch", raw["bch"]["address"])):
        render_qr(addr, os.path.join(folder, f"treasury-{chain}.png"))
    for event in events or []:
        if event_select.classify(event, now) not in ("upcoming", "ongoing"):
            continue
        eid = event.get("id")
        if not eid:
            continue
        for kind in KINDS:
            for chain in CHAINS:
                stem = file_stem(eid, kind, chain)
                urls = media_urls(base, eid, kind, chain)
                render_card(event, kind, chain, "front").save(os.path.join(folder, stem + "-front.png"), "PNG")
                render_card(event, kind, chain, "back").save(os.path.join(folder, stem + "-back.png"), "PNG")
                render_qr(urls["page"] + "#prototype-" + chain + "-" + kind, os.path.join(folder, stem + "-qr.png"))
                doc = {
                    "nexa": nexa_metadata(event, kind, urls),
                    "bch": bch_metadata(event, kind, urls),
                }
                json.dump(doc, open(os.path.join(folder, stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _status_label(t, status):
    return t({"ok": "tre_ok", "low": "tre_low", "empty": "tre_empty"}[status])


def _one_chain(event, kind, chain, view, root, rel, t, E):
    """One mint control. Empty treasuries link to the treasury page and do not open a mint panel."""
    eid = event.get("id") or ""
    stem = file_stem(eid, kind, chain)
    art = f"{root}assets/nft/{stem}-front.png"
    qr = f"{root}assets/nft/{stem}-qr.png"
    label_key = {("pre", "nexa"): "nft_pre_nexa", ("pre", "bch"): "nft_pre_bch",
                 ("ongoing", "nexa"): "nft_mint_nexa", ("ongoing", "bch"): "nft_mint_bch"}[(kind, chain)]
    chain_name = "Nexa" if chain == "nexa" else "Bitcoin Cash"
    head = t("nft_going") if kind == "pre" else t("nft_was")
    parts = [f'<p class="meta"><b>{E(head)}</b> · {E(chain_name)}</p>']
    if view["status"] == "empty":
        parts.append(f'<p><a class="nftbtn" href="{E(rel)}treasury/">{E(t("nft_empty"))}</a></p>')
        return "\n".join(parts)
    urls = media_urls("https://nordiccrypto.no/", eid, kind, chain)
    meta = nexa_metadata(event, kind, urls) if chain == "nexa" else bch_metadata(event, kind, urls)
    show = t("nft_wally") if chain == "nexa" else t("nft_bch_show")
    amount = view["per_mint"]["airdrop"]["amount"]
    air_key = "nft_airdrop_nexa" if chain == "nexa" else "nft_airdrop_bch"
    one_key = "nft_one_nexa" if chain == "nexa" else "nft_one_bch"
    low = ""
    if view["status"] == "low":
        low = f'<p class="meta">{E(t("nft_low"))} <a href="{E(rel)}treasury/">{E(t("nav_treasury"))}</a></p>'
    info = meta["info"] if chain == "nexa" else ("<p>" + html.escape(meta["description"], quote=False) + "</p>")
    # info is our own escaped paragraph. Keep it as HTML we produced, not as visitor input.
    parts.append(f'''<details>
<summary>{E(t(label_key))}</summary>
<div class="nftdlg">
<img class="art" src="{E(art)}" alt="{E(t("nft_preview_alt"))}" width="180" height="180">
<p class="meta">{E(t("nft_same"))}</p>
<h4>{E(show)}</h4>
<dl>
<dt>title</dt><dd>{E(meta["title"] if chain == "nexa" else meta["name"])}</dd>
<dt>series</dt><dd>{E(meta.get("series") or meta.get("kind") or "")}</dd>
<dt>author</dt><dd>{E(meta.get("author") or "Nordic Crypto")}</dd>
<dt>info</dt><dd>{info}</dd>
<dt>license</dt><dd>{E(meta.get("license") or "CC BY 4.0")}</dd>
</dl>
<p>{E(t(air_key, n=amount))}</p>
<p>{E(t(one_key))}</p>
<img class="qr" src="{E(qr)}" alt="{E(t("nft_qr_alt"))}" width="112" height="112">
<p class="meta">{E(t("nft_link"))}</p>
<p class="meta">{E(t("nft_stub"))}</p>
{low}
<p class="meta"><a href="{E(rel)}treasury/">{E(t("nav_treasury"))}</a></p>
</div>
</details>''')
    return "\n".join(parts)


def mint_blocks(event, phase, root, rel, t, E, link_page=True):
    """Both chains, for the phase this card is in. The other phase stays in the page for the clock script."""
    if not enabled():
        return ""
    doc = treasury_document("https://nordiccrypto.no/treasury/")
    blocks = []
    for kind, want in (("ongoing", "ongoing"), ("pre", "upcoming")):
        hidden = "" if phase == want else " hidden"
        inner = "\n".join(_one_chain(event, kind, chain, doc[chain], root, rel, t, E) for chain in CHAINS)
        blocks.append(f'<div class="nftmint" data-nft="{kind}"{hidden}>\n{inner}\n</div>')
    if link_page:
        blocks.append(f'<p class="meta"><a href="{E(rel)}events/{E(event.get("id") or "")}/">{E(t("nft_page"))}</a></p>')
    return "\n".join(blocks)


def clock_script(now_iso):
    """Show the pre-event card before the start and the ongoing card while it runs."""
    fixed = json.dumps(now_iso)
    return """<script>(function(){var FIXED=%s,now=FIXED?new Date(FIXED):new Date(),t=now.getTime();
document.querySelectorAll('[data-nft-start]').forEach(function(box){
 var s=new Date(box.getAttribute('data-nft-start')).getTime(),e=new Date(box.getAttribute('data-nft-end')||'').getTime();
 var mode=(s<=t&&!isNaN(e)&&t<=e)?'ongoing':(s>t?'pre':'');
 box.querySelectorAll('[data-nft]').forEach(function(el){el.hidden=el.getAttribute('data-nft')!==mode});
});})();</script>""" % fixed


def treasury_body(doc, root, t, E):
    def col(key, heading):
        row = doc[key]
        unit = row["balance"]["unit"]
        qr = f"{root}assets/nft/treasury-{key}.png"
        per = row["per_mint"]
        return f'''<div class="trecol">
<h2>{E(heading)}</h2>
<p class="placeholder"><b>{E(t("tre_ph"))}</b><br><code>{E(row["address"])}</code></p>
<img src="{E(qr)}" alt="{E(t("nft_qr_alt"))}" width="168" height="168">
<p><b>{E(t("tre_status"))}:</b> {E(_status_label(t, row["status"]))}</p>
<p>{E(t("tre_small"))}</p>
<p class="meta">{E(t("tre_refill"))}</p>
<p><b>{E(t("tre_balance"))}:</b> {row["balance"]["amount"]} {E(unit)}</p>
<p><b>{E(t("tre_target"))}:</b> {row["hot_balance_target"]["amount"]} {E(unit)}</p>
<p><b>{E(t("tre_mints"))}:</b> {row["mints_paid"]}</p>
<p><b>{E(t("tre_cost"))}:</b> {per["network"]["amount"]} {E(unit)}</p>
<p><b>{E(t("tre_air"))}:</b> {per["airdrop"]["amount"]} {E(unit)}</p>
<p><b>{E(t("tre_total"))}:</b> {per["total"]["amount"]} {E(unit)}</p>
<p><b>{E(t("tre_event_cap"))}:</b> {row["per_event"]}</p>
<p><b>{E(t("tre_day_cap"))}:</b> {row["per_day"]}</p>
<p class="meta">{E(t("tre_floor"))}</p>
</div>'''
    return f'''<h1>{E(t("tre_title"))}</h1>
<p class="lead">{E(t("tre_lead"))}</p>
<p class="placeholder">{E(t("tre_proto"))}</p>
<div class="trewrap">
{col("nexa", t("tre_nexa_h"))}
{col("bch", t("tre_bch_h"))}
</div>
<h2>{E(t("tre_how_h"))}</h2>
<p>{E(t("tre_how"))}</p>
<p>{E(t("tre_app"))}</p>
<p class="meta">{E(t("tre_api"))}: <a href="{E(root)}api/v1/treasury.json">/api/v1/treasury.json</a></p>'''


def event_body(event, phase, root, rel, t, E, when, place):
    wrap = (
        f'<div id="nft-event" data-nft-start="{E(event.get("start") or "")}" data-nft-end="{E(event.get("end") or "")}">'
        + mint_blocks(event, phase, root, rel, t, E, link_page=False)
        + "</div>"
    )
    return f'''<h1>{E(event.get("title") or "")}</h1>
<p class="lead">{E(t("nft_event_lead"))}</p>
<p class="meta">{E(when)}</p>
<p>{E(place)}</p>
<p class="meta">{E(t("organiser"))}: {E(event.get("organiser") or "")}</p>
<p class="meta"><a href="{E(event.get("url") or "")}" rel="noopener">{E(event.get("source") or "")}</a></p>
{wrap}
<p class="meta"><a href="{E(rel)}calendar/">{E(t("nav_calendar"))}</a> · <a href="{E(rel)}treasury/">{E(t("nav_treasury"))}</a></p>'''


def faucet_redirect(site, lang):
    folder = os.path.join(site, "" if lang == "en" else lang, "faucet")
    os.makedirs(folder, exist_ok=True)
    html_doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url=../treasury/">'
        '<link rel="canonical" href="../treasury/"><title>Moved</title></head>'
        '<body><p>This page has moved to <a href="../treasury/">treasury</a>.</p></body></html>'
    )
    open(os.path.join(folder, "index.html"), "w", encoding="utf-8").write(html_doc)
