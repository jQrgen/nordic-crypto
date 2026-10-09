#!/usr/bin/env python3
"""Country explainer videos (regulation-videos/) for Nordic Crypto, called by build.py.

Five slots (NO, SE, DK, FI, IS). An MP4 in regulation-videos/media/ is embedded with the
HTML5 player (poster + WebVTT when those files exist). Otherwise the slot is a placeholder:
title, narrator notes from the script, and sources.

Institution names and legal sources come from rules.json (editor-approved). Narrator lines are
the spoken lines of regulation-videos/scripts/, which were written from that file and the
org-chart regulation notes. This module does not add legal claims of its own.

Iceland is EEA, not EU. Seðlabanki Íslands houses Fjármálaeftirlit — the page says so.
Layout: one start-aligned column; each slot is a hairline section with a quiet label line (flag, country, route, length),
the poster or video, the institutions in hairline rows, and the narrator notes folded in a <details>. No centered slot.
Brand: Nordic Crypto. Sign-off: The Nordic Crypto team. No Kaupr sponsor line.
The opener does not say the films were made with artificial intelligence.
"""
import datetime, json, os, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import site_css  # noqa: E402

STR = {
"en": dict(
    title="How crypto rules are decided — videos",
    desc="Five Nordic Crypto explainers on how crypto rules are decided and enforced in Norway, Sweden, Denmark, Finland and Iceland. A video plays here when the file exists. Until then each slot shows the title, narrator notes and sources.",
    lead="Five short explainers on how crypto and bitcoin rules are decided and enforced in each Nordic country. They follow the same sourced map as How the rules are made.",
    soon="The films are not rendered yet. When an MP4 is added for a country, that slot plays it on this page. Until then you get the title, the narrator notes and the sources.",
    soon_some="Some films are not rendered yet. A slot plays its MP4 when the file is in place. The others show the title, the narrator notes and the sources.",
    not_advice="Simplified overview, not legal advice.",
    signoff="The Nordic Crypto team",
    back="← How the rules are made",
    jump="Countries",
    slot_title="How crypto rules are decided in {country}",
    coming="Video coming soon",
    coming_p="The script and storyboard are ready. This slot plays the MP4 here when the file is in place.",
    poster_alt="Poster for the {country} explainer. The film is not rendered yet.",
    narrator="Narrator notes",
    notes_en="The narrator notes are in English.",
    sources="Sources",
    parliament="Parliament", ministry="Ministry", supervisor="Supervisor", fiu="FIU", tax="Tax authority",
    law="National act", route="Route", eea="EEA", eu="EU member", chart="org chart",
    is_note="Iceland is in the European Economic Area, not the EU. Seðlabanki Íslands houses Fjármálaeftirlit, the financial supervisor that licences crypto-asset service providers under MiCA.",
    video_note="The video plays from this website, with no third-party player.",
    video_fallback="Your browser can't play the video here.",
    subs="English subtitles (WebVTT)",
    checked="Institutions and sources follow the editor-approved rules page, checked {d}.",
    minutes="About {m} min",
    placeholder="This page is being prepared and is awaiting editor review. Meanwhile, see how the rules are made.",
),
"nb": dict(
    title="Slik blir kryptoreglene avgjort — videoer",
    desc="Fem forklaringer fra Nordic Crypto om hvordan kryptoregler blir avgjort og håndhevet i Norge, Sverige, Danmark, Finland og Island. En video spilles av her når filen finnes. Inntil da viser hver plass tittel, fortellernotater og kilder.",
    lead="Fem korte forklaringer av hvordan kryptoregler og bitcoin-regler blir avgjort og håndhevet i hvert nordisk land. De følger det samme kartet med kilder som Slik blir reglene til.",
    soon="Filmene er ikke laget ennå. Når en MP4 blir lagt til for et land, spiller den plassen den av på denne siden. Inntil da får du tittel, fortellernotater og kildene.",
    soon_some="Noen filmer er ikke laget ennå. En plass spiller av MP4-filen når den ligger klar. De andre viser tittel, fortellernotater og kildene.",
    not_advice="Forenklet oversikt, ikke juridisk rådgivning.",
    signoff="The Nordic Crypto team",
    back="← Slik blir reglene til",
    jump="Land",
    slot_title="Slik blir kryptoreglene avgjort i {country}",
    coming="Videoen kommer",
    coming_p="Manus og storyboard er klare. Denne plassen spiller av MP4-filen her når den ligger klar.",
    poster_alt="Plakat for forklaringen om {country}. Filmen er ikke laget ennå.",
    narrator="Fortellernotater",
    notes_en="Fortellernotatene er på engelsk.",
    sources="Kilder",
    parliament="Nasjonalforsamling", ministry="Departement", supervisor="Tilsyn", fiu="FIU", tax="Skattemyndighet",
    law="Nasjonal lov", route="Vei", eea="EØS", eu="EU-medlem", chart="hvem er hvem",
    is_note="Island er i Det europeiske økonomiske samarbeidsområdet (EØS), ikke i EU. Seðlabanki Íslands huser Fjármálaeftirlit, tilsynet som gir tillatelse til tilbydere av kryptoeiendelstjenester under MiCA.",
    video_note="Videoen spilles av fra dette nettstedet, uten en tredjepartsspiller.",
    video_fallback="Nettleseren din kan ikke spille av videoen her.",
    subs="Engelske undertekster (WebVTT)",
    checked="Institusjoner og kilder følger den redaktørgodkjente reglesiden, kontrollert {d}.",
    minutes="Omtrent {m} min",
    placeholder="Denne siden er under arbeid og venter på redaktørens gjennomgang. Se Slik blir reglene til i mellomtiden.",
),
"nn": dict(
    title="Slik blir kryptoreglane avgjorde — videoar",
    desc="Fem forklaringar frå Nordic Crypto om korleis kryptoreglar blir avgjorde og handheva i Noreg, Sverige, Danmark, Finland og Island. Ein video blir spelt av her når fila finst. Til då viser kvar plass tittel, forteljarnotat og kjelder.",
    lead="Fem korte forklaringar av korleis kryptoreglar og bitcoin-reglar blir avgjorde og handheva i kvart nordisk land. Dei følgjer det same kartet med kjelder som Slik blir reglane til.",
    soon="Filmane er ikkje laga enno. Når ein MP4 blir lagd til for eit land, spelar den plassen han av på denne sida. Til då får du tittel, forteljarnotat og kjeldene.",
    soon_some="Nokre filmar er ikkje laga enno. Ein plass spelar av MP4-fila når ho ligg klar. Dei andre viser tittel, forteljarnotat og kjeldene.",
    not_advice="Forenkla oversikt, ikkje juridisk rådgiving.",
    signoff="The Nordic Crypto team",
    back="← Slik blir reglane til",
    jump="Land",
    slot_title="Slik blir kryptoreglane avgjorde i {country}",
    coming="Videoen kjem",
    coming_p="Manus og storyboard er klare. Denne plassen spelar av MP4-fila her når ho ligg klar.",
    poster_alt="Plakat for forklaringa om {country}. Filmen er ikkje laga enno.",
    narrator="Forteljarnotat",
    notes_en="Forteljarnotata er på engelsk.",
    sources="Kjelder",
    parliament="Nasjonalforsamling", ministry="Departement", supervisor="Tilsyn", fiu="FIU", tax="Skattestyresmakt",
    law="Nasjonal lov", route="Veg", eea="EØS", eu="EU-medlem", chart="kven er kven",
    is_note="Island er i Det europeiske økonomiske samarbeidsområdet (EØS), ikkje i EU. Seðlabanki Íslands husar Fjármálaeftirlit, tilsynet som gir løyve til tilbydarar av kryptoeigedelstenester under MiCA.",
    video_note="Videoen blir spelt av frå denne nettstaden, utan ein tredjepartsspelar.",
    video_fallback="Nettlesaren din kan ikkje spele av videoen her.",
    subs="Engelske undertekstar (WebVTT)",
    checked="Institusjonar og kjelder følgjer den redaktørgodkjende reglesida, kontrollert {d}.",
    minutes="Om lag {m} min",
    placeholder="Denne sida er under arbeid og ventar på gjennomgang frå redaktøren. Sjå Slik blir reglane til i mellomtida.",
),
"sv": dict(
    title="Så avgörs kryptoreglerna — videor",
    desc="Fem förklaringar från Nordic Crypto om hur kryptoregler avgörs och upprätthålls i Norge, Sverige, Danmark, Finland och Island. En video spelas upp här när filen finns. Tills dess visar varje plats titel, berättarnoteringar och källor.",
    lead="Fem korta förklaringar av hur kryptoregler och bitcoinregler avgörs och upprätthålls i varje nordiskt land. De följer samma karta med källor som Så blir reglerna till.",
    soon="Filmerna är inte gjorda än. När en MP4 läggs till för ett land spelar den platsen upp den på den här sidan. Tills dess får du titel, berättarnoteringar och källorna.",
    soon_some="Vissa filmer är inte gjorda än. En plats spelar upp sin MP4 när filen finns. De andra visar titel, berättarnoteringar och källorna.",
    not_advice="Förenklad översikt, inte juridisk rådgivning.",
    signoff="The Nordic Crypto team",
    back="← Så blir reglerna till",
    jump="Länder",
    slot_title="Så avgörs kryptoreglerna i {country}",
    coming="Videon kommer",
    coming_p="Manus och storyboard är klara. Den här platsen spelar upp MP4-filen här när den finns.",
    poster_alt="Affisch för förklaringen om {country}. Filmen är inte gjord än.",
    narrator="Berättarnoteringar",
    notes_en="Berättarnoteringarna är på engelska.",
    sources="Källor",
    parliament="Parlament", ministry="Departement", supervisor="Tillsyn", fiu="FIU", tax="Skattemyndighet",
    law="Nationell lag", route="Väg", eea="EES", eu="EU-medlem", chart="vem är vem",
    is_note="Island ingår i Europeiska ekonomiska samarbetsområdet, inte i EU. Seðlabanki Íslands rymmer Fjármálaeftirlit, den tillsynsmyndighet som ger tillstånd till leverantörer av kryptotillgångstjänster enligt MiCA.",
    video_note="Videon spelas upp från den här webbplatsen, utan en tredjepartsspelare.",
    video_fallback="Din webbläsare kan inte spela upp videon här.",
    subs="Engelska undertexter (WebVTT)",
    checked="Institutioner och källor följer den redaktörsgodkända regelsidan, kontrollerad {d}.",
    minutes="Ungefär {m} min",
    placeholder="Den här sidan håller på att tas fram och väntar på redaktörens granskning. Se under tiden Så blir reglerna till.",
),
"da": dict(
    title="Sådan bliver kryptoreglerne afgjort — videoer",
    desc="Fem forklaringer fra Nordic Crypto om, hvordan kryptoregler bliver afgjort og håndhævet i Norge, Sverige, Danmark, Finland og Island. En video afspilles her, når filen findes. Indtil da viser hver plads titel, fortællernoter og kilder.",
    lead="Fem korte forklaringer af, hvordan kryptoregler og bitcoinregler bliver afgjort og håndhævet i hvert nordisk land. De følger det samme kort med kilder som Sådan bliver reglerne til.",
    soon="Filmene er ikke lavet endnu. Når en MP4 bliver lagt til for et land, afspiller den plads den på denne side. Indtil da får du titel, fortællernoter og kilderne.",
    soon_some="Nogle film er ikke lavet endnu. En plads afspiller sin MP4, når filen ligger klar. De andre viser titel, fortællernoter og kilderne.",
    not_advice="Forenklet overblik, ikke juridisk rådgivning.",
    signoff="The Nordic Crypto team",
    back="← Sådan bliver reglerne til",
    jump="Lande",
    slot_title="Sådan bliver kryptoreglerne afgjort i {country}",
    coming="Videoen kommer",
    coming_p="Manuskript og storyboard er klar. Denne plads afspiller MP4-filen her, når den ligger klar.",
    poster_alt="Plakat til forklaringen om {country}. Filmen er ikke lavet endnu.",
    narrator="Fortællernoter",
    notes_en="Fortællernoterne er på engelsk.",
    sources="Kilder",
    parliament="Parlament", ministry="Ministerium", supervisor="Tilsyn", fiu="FIU", tax="Skattemyndighed",
    law="National lov", route="Vej", eea="EØS", eu="EU-medlem", chart="hvem er hvem",
    is_note="Island er i Det Europæiske Økonomiske Samarbejdsområde, ikke i EU. Seðlabanki Íslands huser Fjármálaeftirlit, tilsynet der giver tilladelse til udbydere af kryptoaktivtjenester efter MiCA.",
    video_note="Videoen afspilles fra dette websted, uden en tredjepartsafspiller.",
    video_fallback="Din browser kan ikke afspille videoen her.",
    subs="Engelske undertekster (WebVTT)",
    checked="Institutioner og kilder følger den redaktørgodkendte regelside, kontrolleret {d}.",
    minutes="Omkring {m} min",
    placeholder="Denne side er under udarbejdelse og afventer redaktørens gennemgang. Se imens Sådan bliver reglerne til.",
),
"fi": dict(
    title="Näin kryptosäännöistä päätetään — videot",
    desc="Viisi Nordic Crypton selitystä siitä, miten kryptosäännöistä päätetään ja miten niitä pannaan täytäntöön Norjassa, Ruotsissa, Tanskassa, Suomessa ja Islannissa. Video toistetaan täällä, kun tiedosto on olemassa. Siihen asti jokainen paikka näyttää otsikon, kertojan muistiinpanot ja lähteet.",
    lead="Viisi lyhyttä selitystä siitä, miten krypto- ja bitcoin-säännöistä päätetään ja miten niitä pannaan täytäntöön kussakin Pohjoismaassa. Ne seuraavat samaa lähteistettyä karttaa kuin Näin säännöt syntyvät.",
    soon="Videoita ei ole vielä tehty. Kun maalle lisätään MP4, se paikka toistaa sen tällä sivulla. Siihen asti näet otsikon, kertojan muistiinpanot ja lähteet.",
    soon_some="Osaa videoista ei ole vielä tehty. Paikka toistaa MP4-tiedoston, kun se on paikallaan. Muut näyttävät otsikon, kertojan muistiinpanot ja lähteet.",
    not_advice="Yksinkertaistettu katsaus, ei oikeudellista neuvontaa.",
    signoff="The Nordic Crypto team",
    back="← Näin säännöt syntyvät",
    jump="Maat",
    slot_title="{country}: näin kryptosäännöistä päätetään",
    coming="Video tulossa",
    coming_p="Käsikirjoitus ja kuvakäsikirjoitus ovat valmiit. Tämä paikka toistaa MP4-tiedoston täällä, kun se on paikallaan.",
    poster_alt="Juliste maalle {country}. Videota ei ole vielä tehty.",
    narrator="Kertojan muistiinpanot",
    notes_en="Kertojan muistiinpanot ovat englanniksi.",
    sources="Lähteet",
    parliament="Parlamentti", ministry="Ministeriö", supervisor="Valvoja", fiu="FIU", tax="Veroviranomainen",
    law="Kansallinen laki", route="Reitti", eea="ETA", eu="EU-jäsen", chart="toimijahakemisto",
    is_note="Islanti kuuluu Euroopan talousalueeseen, ei Euroopan unioniin. Seðlabanki Íslands pitää sisällään Fjármálaeftirlitin, valvojan, joka myöntää toimiluvat kryptovarapalvelujen tarjoajille MiCA-asetuksen nojalla.",
    video_note="Video toistetaan tältä sivustolta, ilman kolmannen osapuolen soitinta.",
    video_fallback="Selaimesi ei voi toistaa videota täällä.",
    subs="Englanninkieliset tekstitykset (WebVTT)",
    checked="Viranomaiset ja lähteet seuraavat toimittajan hyväksymää sääntösivua, tarkistettu {d}.",
    minutes="Noin {m} min",
    placeholder="Tätä sivua valmistellaan, ja se odottaa toimittajan tarkistusta. Katso sillä välin Näin säännöt syntyvät.",
),
"is": dict(
    title="Svona er ákveðið um rafmyntareglur — myndbönd",
    desc="Fimm skýringar frá Nordic Crypto um hvernig rafmyntareglur eru ákveðnar og þeim framfylgt í Noregi, Svíþjóð, Danmörku, Finnlandi og Íslandi. Myndband er spilað hér þegar skráin er til. Þar til sýnir hver reitur titil, glósur sögumanns og heimildir.",
    lead="Fimm stuttar skýringar á því hvernig reglur um rafmynt og bitcoin eru ákveðnar og þeim framfylgt í hverju norrænu landi. Þær fylgja sama korti með heimildum og Svona verða reglurnar til.",
    soon="Myndböndin eru ekki tilbúin. Þegar MP4 er bætt við fyrir land spilar sá reitur það á þessari síðu. Þar til færðu titil, glósur sögumanns og heimildirnar.",
    soon_some="Sum myndbönd eru ekki tilbúin. Reitur spilar MP4-skrána þegar hún er til staðar. Hin sýna titil, glósur sögumanns og heimildirnar.",
    not_advice="Einfaldað yfirlit, ekki lögfræðiráðgjöf.",
    signoff="The Nordic Crypto team",
    back="← Svona verða reglurnar til",
    jump="Lönd",
    slot_title="{country}: svona er ákveðið um rafmyntareglur",
    coming="Myndband á leiðinni",
    coming_p="Handrit og söguspjald eru tilbúin. Þessi reitur spilar MP4-skrána hér þegar hún er til staðar.",
    poster_alt="Veggspjald fyrir skýringuna um {country}. Myndbandið er ekki tilbúið.",
    narrator="Glósur sögumanns",
    notes_en="Glósur sögumanns eru á ensku.",
    sources="Heimildir",
    parliament="Þing", ministry="Ráðuneyti", supervisor="Eftirlit", fiu="FIU", tax="Skattyfirvald",
    law="Landslög", route="Leið", eea="EES", eu="ESB-ríki", chart="hver er hvað",
    is_note="Ísland er á Evrópska efnahagssvæðinu, ekki í ESB. Seðlabanki Íslands hýsir Fjármálaeftirlit, eftirlitið sem veitir þjónustuveitendum sýndareigna starfsleyfi samkvæmt MiCA.",
    video_note="Myndbandið er spilað af þessum vef, án spilara þriðja aðila.",
    video_fallback="Vafrinn þinn getur ekki spilað myndbandið hér.",
    subs="Enskur texti (WebVTT)",
    checked="Stofnanir og heimildir fylgja síðunni sem ritstjóri hefur samþykkt, athugað {d}.",
    minutes="Um {m} mín.",
    placeholder="Verið er að undirbúa þessa síðu og hún bíður yfirferðar ritstjóra. Sjá á meðan Svona verða reglurnar til.",
),
}

CSS = site_css.style("regulation-videos")   # assets/css/regulation-videos.css

def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_slots():
    path = os.path.join(_root(), "data", "regulation-videos.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return []
    return [v for v in data.get("videos") or [] if v.get("country")]

def load_rules():
    try:
        return json.load(open(os.path.join(_root(), "rules.json"), encoding="utf-8"))
    except FileNotFoundError:
        return None

def narrator_lines(path):
    """Spoken lines only. The production header (voice, brand rules) stays off the page.
    Cue headers and stage directions stay off too."""
    if not os.path.isfile(path):
        return []
    out = []
    seen_cue = False
    for raw in open(path, encoding="utf-8"):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            seen_cue = True
            continue
        if not seen_cue or s.startswith("("):
            continue
        out.append(s)
    return out

def media_path(name):
    if not name:
        return None
    path = os.path.join(_root(), "regulation-videos", "media", os.path.basename(name))
    return path if os.path.isfile(path) else None

def poster_path(name):
    if not name:
        return None
    path = os.path.join(_root(), "regulation-videos", "posters", os.path.basename(name))
    return path if os.path.isfile(path) else None

def copy_assets(m, videos):
    """Copy posters and any rendered files once, into site/regulation-videos/ (all languages link there)."""
    if m.LANG != "en":
        return
    dest = os.path.join(m.SITE, "regulation-videos")
    os.makedirs(dest, exist_ok=True)
    for v in videos:
        poster = poster_path(v.get("poster"))
        if poster:
            shutil.copy(poster, os.path.join(dest, os.path.basename(v["poster"])))
        for key in ("file", "subs"):
            src = media_path(v.get(key))
            if src:
                shutil.copy(src, os.path.join(dest, os.path.basename(v[key])))

def _source_keys(row):
    keys = ["mica", row.get("law_src")]
    sup = row.get("supervisor") or {}
    keys.append(sup.get("src"))
    keys.append(sup.get("src2"))
    for item in row.get("enforce") or []:
        keys.append(item.get("src"))
        keys.append(item.get("src2"))
    for name in ("note4_src", "note5_src"):
        keys.extend(row.get(name) or [])
    seen, out = set(), []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out

def build(m, ctx):
    R = load_rules()
    videos = load_slots()
    if not R or not videos:
        return
    L = m.LANG
    S = dict(STR["en"], **STR.get(L, {}))
    E = m.E
    title = S["title"]
    if R.get("review") == "pending" and not m.PREVIEW:
        body = (f'<h1>{E(title)}</h1><p class="lead">{E(S["placeholder"])}</p>'
                f'<p><a href="../rules/">{E(S["back"])}</a></p>')
        m.page("regulation-videos", title, "org-chart", body, S["desc"])
        return
    copy_assets(m, videos)
    by_cc = {v["country"]: v for v in videos}
    order = [c for c in m.COUNTRY_CODES if c in by_cc and c in R.get("countries", {})]
    srcs = R.get("sources") or {}
    ids = {e["id"] for e in (ctx.get("ents") or [])}
    reg_by = {r.get("country"): r for r in ((ctx.get("org") or {}).get("regulation") or []) if r.get("country")}
    asset = m.up1() + "regulation-videos/"

    def link_src(key):
        x = srcs.get(key)
        if not x:
            return ""
        return f'<a href="{E(x["url"])}" rel="noopener">{E(x.get("publisher") or x.get("title") or key)}</a>'

    def chart(org):
        if org and org in ids:
            return f' · <a href="../org-chart/#{E(org)}">{E(S["chart"])}</a>'
        return ""

    def d(iso):
        return m.i18n.long_date(L, datetime.date.fromisoformat(iso))

    jump = (f'<nav class="rv-jump" aria-label="{E(S["jump"])}">'
            + "".join(f'<a href="#{c}">{m.flag(c, deco=True)}{E(m.cname(c))}</a>' for c in order)
            + "</nav>")
    blocks = []
    for c in order:
        v = by_cc[c]
        row = R["countries"][c]
        name = m.cname(c)
        h = S["slot_title"].format(country=name)
        route = S["eea"] if row.get("route") == "eea" else S["eu"]
        minutes = S["minutes"].format(m=max(1, int(round((v.get("duration_target_s") or 0) / 60)))) if v.get("duration_target_s") else ""
        kicker = (f'<p class="rv-kicker">{m.flag(c, deco=True)}<span>{E(name)}</span><span>{E(route)}</span>'
                  + (f'<span>{E(minutes)}</span>' if minutes else "")
                  + "</p>")
        vid = media_path(v.get("file"))
        poster_name = os.path.basename(v["poster"]) if v.get("poster") and poster_path(v.get("poster")) else ""
        if vid:
            poster_attr = f' poster="{asset}{E(poster_name)}"' if poster_name else ""
            subs = media_path(v.get("subs"))
            track = (f'<track kind="subtitles" srclang="en" label="{E(S["subs"])}" src="{asset}{E(os.path.basename(v["subs"]))}">'
                     if subs else "")
            sub_link = (f' · <a href="{asset}{E(os.path.basename(v["subs"]))}" download>{E(S["subs"])}</a>' if subs else "")
            media = (f'<figure class="rv-media"><video controls preload="metadata" playsinline{poster_attr} width="1920" height="1080">'
                     f'<source src="{asset}{E(os.path.basename(v["file"]))}" type="video/mp4">{track}'
                     f'<p>{E(S["video_fallback"])}</p></video>'
                     f'<figcaption class="meta">{E(S["video_note"])}{sub_link}</figcaption></figure>')
        else:
            img = (f'<img src="{asset}{E(poster_name)}" alt="{E(S["poster_alt"].format(country=name))}" width="480" height="270" loading="lazy">'
                   if poster_name else "")
            media = (f'<figure class="rv-media">{img}<figcaption class="rv-soon"><b>{E(S["coming"])}</b> {E(S["coming_p"])}</figcaption></figure>'
                     if img else f'<p class="rv-soon"><b>{E(S["coming"])}</b> {E(S["coming_p"])}</p>')
        facts = []   # the route is in the label line above
        law_bits = " · ".join(x for x in (link_src(row.get("law_src")),) if x)
        facts.append((S["law"], row.get("law") or "", f'<div class="meta">{law_bits}</div>' if law_bits else ""))
        def chart_line(org):
            x = chart(org).lstrip(" ·")
            return f'<div class="meta">{x}</div>' if x else ""
        facts.append((S["parliament"], row.get("parliament") or "", chart_line(row.get("parliament_org"))))
        ministry = row.get("ministry") or {}
        facts.append((S["ministry"], ministry.get("name") or "", chart_line(ministry.get("org"))))
        sup = row.get("supervisor") or {}
        sup_links = " · ".join(x for x in (link_src(sup.get("src")), link_src(sup.get("src2")), chart(sup.get("org")).lstrip(" ·")) if x)
        facts.append((S["supervisor"], sup.get("name") or "", f'<div class="meta">{sup_links}</div>' if sup_links else ""))
        for item in row.get("enforce") or []:
            kind = S["fiu"] if item.get("kind") == "fiu" else S["tax"] if item.get("kind") == "tax" else item.get("kind") or ""
            bits = " · ".join(x for x in (link_src(item.get("src")), link_src(item.get("src2")), chart(item.get("org")).lstrip(" ·")) if x)
            facts.append((kind, item.get("name") or "", f'<div class="meta">{bits}</div>' if bits else ""))
        fact_html = "".join(
            f'<div class="rv-fact"><span class="k">{E(k)}</span><b>{E(val)}</b>{extra}</div>'
            for k, val, extra in facts if val)
        call = f'<p class="rv-call">{E(S["is_note"])}</p>' if c == "IS" else ""
        script = os.path.join(_root(), "regulation-videos", v.get("script") or "")
        lines = narrator_lines(script)
        notes_lang = m.bidi_attr("en")   # English notes: lang="en" on other pages, and dir="ltr" on right-to-left ones
        en_note = "" if L == "en" else f'<p class="meta">{E(S["notes_en"])}</p>'
        notes = (f'<details class="rv-nbox"><summary>{E(S["narrator"])}</summary>{en_note}<div class="rv-notes"{notes_lang}>'
                 + "".join(f"<p>{E(line)}</p>" for line in lines) + "</div></details>") if lines else ""
        seen_url = {srcs[k]["url"] for k in _source_keys(row) if k in srcs}
        extra_src = []
        for s in (reg_by.get(c) or {}).get("sources") or []:
            url = s.get("url")
            if url and url not in seen_url:
                seen_url.add(url)
                extra_src.append(f'<a href="{E(url)}" rel="noopener">{E(s.get("source_name") or s.get("title") or url)}</a>')
        src_html = " · ".join([link_src(k) for k in _source_keys(row)] + extra_src)
        src_block = f'<p class="meta"><b>{E(S["sources"])}.</b> {src_html}</p>' if src_html else ""
        blocks.append(
            f'<article class="rv-slot" id="{E(c)}" aria-labelledby="rv-{E(c)}-h">{kicker}<h2 id="rv-{E(c)}-h">{E(h)}</h2>{media}'
            f'<div class="rv-facts">{fact_html}</div>{call}{notes}{src_block}</article>')
    checked = d(R["checked"]) if R.get("checked") else ""
    checked_p = f'<p class="meta">{E(S["checked"].format(d=checked))}</p>' if checked else ""
    n_ready = sum(1 for c in order if media_path(by_cc[c].get("file")))
    if n_ready == 0:
        soon_html = f'<p class="notice">{E(S["soon"])}</p>'
    elif n_ready < len(order):
        soon_html = f'<p class="notice">{E(S["soon_some"])}</p>'
    else:
        soon_html = ""
    body = (CSS + f'<div class="rv"><h1>{E(title)}</h1><p class="lead">{E(S["lead"])}</p>'
            f'{soon_html}'
            f'<p class="rv-advice">{E(S["not_advice"])} <b>{E(S["signoff"])}</b>.</p>'
            f'<p class="rv-back"><a href="../rules/">{E(S["back"])}</a></p>{jump}{"".join(blocks)}<div class="rv-end">{checked_p}'
            f'<p><b>{E(S["signoff"])}</b></p></div></div>')
    m.page("regulation-videos", title, "org-chart", body, S["desc"])
    if L == "en":
        ready = sum(1 for c in order if media_path(by_cc[c].get("file")))
        print(f"regulation-videos: {len(order)} slots, {ready} with MP4")
