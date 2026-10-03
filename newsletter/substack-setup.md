# Nordic Crypto – newsletter setup kit (Substack + email)

Status: **prepared, nothing created or sent.** No Substack account exists yet; jQrgen creates it with his own login.
Nothing here is published to gh-pages, and the signup form on the site is **off** (`newsletter/config.json` → `enabled: false`).

Two channels:
1. **Substack** – the publication itself (web archive + Substack's own email and app).
2. **Email signup on the site** – our own double opt-in form → Cloudflare Worker (`tipworker/`, `POST /api/subscribe`) → D1 table
   `subscribers`. Confirmed addresses are exported as CSV (`tipworker/export_subscribers.py`) and imported into Substack, or
   sent by another provider later (`tipworker/src/mailer.js`; provider not chosen).

---

## 1. Publication

| Field | Proposal |
|---|---|
| Publication name | **Nordic Crypto** |
| Subdomain | **nordiccrypto.substack.com** – looked free on 4 Oct 2026 01:22 CEST (HTTP 404, the same as for a random unused name). Alternative: nordiccryptonews.substack.com (also 404). A 404 is only a hint: Substack's sign-up form gives the final answer. |
| Custom domain (optional, paid add-on) | not needed; the site stays on jqrgen.github.io/nordic-crypto/ |
| Language (Settings › Publication details) | English |
| Sender name ("From" name) | **Nordic Crypto** (alternative: "Nordic Crypto – jQrgen") |
| Reply-to | jQrgen decides (no public email address exists today; do **not** use a private address without deciding) |
| Paid subscriptions | off (free newsletter) |
| Categories | Primary **Crypto**; secondary **Finance**, then **International** or **News** (pick from Substack's current list) |

**Tagline (≤ 100 characters):**
> Crypto, bitcoin and blockchain news from Norway, Sweden, Denmark, Finland and Iceland – every week.

Short Nordic variants (for the about page or social posts):
- nn: Nyheiter om krypto, bitcoin og blokkjede frå Noreg, Sverige, Danmark, Finland og Island – kvar veke.
- nb: Nyheter om krypto, bitcoin og blokkjede fra Norge, Sverige, Danmark, Finland og Island – hver uke.
- sv: Nyheter om krypto, bitcoin och blockkedjor från Norge, Sverige, Danmark, Finland och Island – varje vecka.
- da: Nyheder om krypto, bitcoin og blockchain fra Norge, Sverige, Danmark, Finland og Island – hver uge.
- fi: Krypto-, bitcoin- ja lohkoketjuuutisia Norjasta, Ruotsista, Tanskasta, Suomesta ja Islannista – joka viikko.
- is: Fréttir af kriptó, bitcoin og bálkakeðjum frá Noregi, Svíþjóð, Danmörku, Finnlandi og Íslandi – vikulega.

**About page (English):**
> Nordic Crypto collects news about crypto, bitcoin and blockchain from Norway, Sweden, Denmark, Finland and Iceland –
> newspapers, broadcasters, regulators and central banks – and gives each story a short summary with a link to the original
> source. Once a week, this newsletter sends the stories our editor has approved.
>
> The summaries are written by our editor, a bot based on artificial intelligence; Jørgen S. Notland (jQrgen), Oslo, is the
> responsible person. Nothing here is investment advice. The website also has a calendar of Nordic crypto events and a
> who's who of the people and organisations in the field: https://jqrgen.github.io/nordic-crypto/
>
> Disclosure: Kaupr (kaupr.io) is one of the news sources we follow, sponsors some events in our calendar and sponsors
> Oslo Blockchain Meetup, the meetup run by jQrgen, the publisher of Nordic Crypto.

Short Nordic variants of the about text:
- nn: Nordic Crypto samlar nyheiter om krypto, bitcoin og blokkjede frå heile Norden og gir kvar sak eit kort samandrag med lenkje til kjelda. Ein gong i veka sender vi sakene redaktøren vår har godkjent. Samandraga er skrivne av ein bot basert på kunstig intelligens; jQrgen er ansvarleg. Ikkje investeringsråd.
- nb: Nordic Crypto samler nyheter om krypto, bitcoin og blokkjede fra hele Norden og gir hver sak et kort sammendrag med lenke til kilden. Én gang i uka sender vi sakene redaktøren vår har godkjent. Sammendragene er skrevet av en bot basert på kunstig intelligens; jQrgen er ansvarlig. Ikke investeringsråd.
- sv: Nordic Crypto samlar nyheter om krypto, bitcoin och blockkedjor från hela Norden och ger varje nyhet en kort sammanfattning med länk till källan. En gång i veckan skickar vi de nyheter som vår redaktör har godkänt. Sammanfattningarna skrivs av en bot baserad på artificiell intelligens; jQrgen är ansvarig. Inga investeringsråd.
- da: Nordic Crypto samler nyheder om krypto, bitcoin og blockchain fra hele Norden og giver hver historie et kort resumé med link til kilden. Én gang om ugen sender vi de historier, vores redaktør har godkendt. Resuméerne skrives af en bot baseret på kunstig intelligens; jQrgen er ansvarlig. Ikke investeringsrådgivning.
- fi: Nordic Crypto kokoaa krypto-, bitcoin- ja lohkoketjuuutisia koko Pohjolasta ja antaa jokaisesta lyhyen tiivistelmän ja linkin lähteeseen. Kerran viikossa lähetämme toimittajamme hyväksymät uutiset. Tiivistelmät kirjoittaa tekoälyyn perustuva botti; vastuuhenkilö on jQrgen. Ei sijoitusneuvontaa.
- is: Nordic Crypto safnar fréttum af kriptó, bitcoin og bálkakeðjum frá öllum Norðurlöndum og gefur hverri frétt stutta samantekt með tengli á heimildina. Einu sinni í viku sendum við fréttirnar sem ritstjórinn okkar hefur samþykkt. Samantektirnar eru skrifaðar af vélmenni byggðu á gervigreind; jQrgen ber ábyrgð. Ekki fjárfestingarráðgjöf.

## 2. Branding (from the site's existing brand: the "Nordic **Crypto**" wordmark in #0f5ea8 and the Nordic-cross favicon)

| Substack field | File |
|---|---|
| Publication logo (square, ≥ 256 px) | `newsletter/assets/logo-512.png` (source `logo.svg`) |
| Wordmark (optional) | `newsletter/assets/wordmark-1200x300.png` |
| Email header / banner | `newsletter/assets/email-banner-1100x220.png` |
| Cover / social preview image | `newsletter/assets/cover-1200x630.png` |

Regenerate with `.venv/bin/python newsletter/make_brand_assets.py` (renders both sites' images with Playwright).
Suggested accent colour in Substack's theme: **#0f5ea8**.

## 3. Welcome email (Substack: Settings › Emails › Welcome email) – draft

**Subject:** Welcome to Nordic Crypto

> Hi, and thanks for subscribing.
>
> Once a week you'll get a short digest of the crypto, bitcoin and blockchain stories from Norway, Sweden, Denmark,
> Finland and Iceland that our editor has approved – a headline, a one- or two-sentence summary and a link to the original
> source. Some sources may require a subscription; we say so next to the story.
>
> The summaries are written by our editor, a bot based on artificial intelligence, and Jørgen S. Notland (jQrgen) in Oslo is
> the responsible person. Nothing in the newsletter is investment advice. Spotted a mistake or a story we missed? Use
> "Send a tip" on the website: https://jqrgen.github.io/nordic-crypto/tip/
>
> Disclosure: Kaupr (kaupr.io) is one of the news sources we follow, sponsors some events in our calendar and sponsors
> Oslo Blockchain Meetup, the meetup run by jQrgen, the publisher of Nordic Crypto.
>
> You can unsubscribe at any time with the link at the bottom of every email.
>
> – Nordic Crypto

(The Worker's own confirmation and welcome emails for the site signup are in `tipworker/src/messages.js`, all 7 languages.)

## 4. Weekly digest (generated from approved stories only)

    ./build.sh                                   # public build → site/ (never --preview)
    .venv/bin/python newsletter/digest.py --lang en          # last 7 days up to today (Oslo time)
    .venv/bin/python newsletter/digest.py --lang nn --until 2026-10-03

- Reads `site/data/news.json` of the **public** build and refuses a preview build, so only editor-approved stories (and only
  approved translations) can appear. Writes `newsletter/out/digest-<date>-<lang>.md|.txt|.html` (gitignored).
- `.md` → paste into a new Substack post (Substack keeps headings, bold and links). `.html`/`.txt` → for a mail provider
  (`{{unsubscribe}}` is the provider's unsubscribe placeholder).
- Template (every edition):
  1. Title "Nordic Crypto weekly" (per language) + date range, one-line intro
  2. Stories grouped by country (Norway, Sweden, Denmark, Finland, Iceland): **headline (link to the source)** – English
     headline with the original in brackets for the English edition; original headline otherwise – then our summary in the
     edition's language, then `source · date · may require a subscription · Kaupr is a sponsor` (the last only for Kaupr stories)
  3. Link to the website (all stories, calendar, who's who)
  4. Footer: Kaupr disclosure, who runs it / bot based on artificial intelligence / not investment advice, why you get this email
- Norwegian editions (nn/nb) are checked for «AI»/«KI» in our own text before the file is written (external headlines are left as published).
- Sample: `newsletter/sample-digest-2026-10-03-en.md`.
- Suggested rhythm: weekly, Friday morning (Oslo). Nothing is scheduled; jQrgen or the editor pastes and sends.

## 5. Kaupr sponsor disclosure (use everywhere: about page, welcome email, every digest footer)

> Disclosure: Kaupr (kaupr.io) is one of the news sources we follow, sponsors some events in our calendar and sponsors
> Oslo Blockchain Meetup, the meetup run by jQrgen, the publisher of Nordic Crypto.

Stories from Kaupr are marked "Kaupr is a sponsor" in the digest.

## 6. Email channel (site signup) and moving subscribers to Substack

- Form: footer of every page + `/newsletter/` in all 7 languages, with a privacy note. Off until `newsletter/config.json`
  `enabled: true` (and the Worker is deployed). Test build: `NC_NEWSLETTER=1 NEWSLETTER_ENDPOINT=http://127.0.0.1:8789 NC_SITE_DIR=/tmp/x .venv/bin/python build.py`.
- Double opt-in: signup → confirmation link (valid 7 days) → `confirmed`. Unconfirmed rows are deleted after 7 days.
  No IP address or user agent is stored. CORS only for https://jqrgen.github.io.
- Confirmation emails are **not sent** until a provider is chosen and `MAIL_PROVIDER` + `MAIL_SEND_ENABLED=1` are set on the
  Worker (see `tipworker/README.md`). With Substack only: keep the site form off, or use it and import confirmed addresses:
  `.venv/bin/python tipworker/export_subscribers.py --site nordic-crypto` → `state/newsletter/nordic-crypto-confirmed-<date>.csv`
  (mode 600, gitignored; column `email` first) → Substack › Subscribers › Import. Delete the CSV after the import.

## 7. Checklist for jQrgen (nothing below has been done)

- [ ] Create the Substack publication with your own login; confirm the subdomain (nordiccrypto).
- [ ] Approve: publication name, sender name, reply-to address, tagline, about text, categories, branding images.
- [ ] Paste the welcome email; set language English; paid subscriptions off.
- [ ] Choose the confirmation-email provider for the site form (Resend, Buttondown, Postmark via webhook, or Substack import only) and the from-address (needs a domain you control for SPF/DKIM).
- [ ] Give a Cloudflare API token to deploy the Worker (`tipworker/deploy.sh`), then approve switching the form on.
- [ ] After the first import: set `substack_url` in `newsletter/config.json` so the site links to the Substack.
