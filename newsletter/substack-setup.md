# Nordic Crypto – newsletter setup kit (Substack + email)

Status: **Substack publication created by jQrgen on 2026-10-05: https://cryptonordic.substack.com** (subdomain `cryptonordic`, renamed from `nordiccrypto` on 2026-10-05;
`/subscribe` answers HTTP 200). Nothing has been sent. The site links to the Substack signup
(https://cryptonordic.substack.com/subscribe) in the footer of every page and on `/newsletter/` in all 7 languages
(`newsletter/config.json` → `substack_url`). The site's own signup form stays **off** (`enabled: false`) until the Worker is deployed.

Two channels:
1. **Substack** – the publication itself (web archive + Substack's own email and app).
2. **Email signup on the site** – our own double opt-in form → Cloudflare Worker (`tipworker/`, `POST /api/subscribe`) → D1 table
   `subscribers`. Confirmed addresses are exported as CSV (`tipworker/export_subscribers.py`) and imported into Substack, or
   sent by another provider later (`tipworker/src/mailer.js`; provider not chosen).

---

## 1. Publication

**Live embed title is not set by this site.** The iframe `https://cryptonordic.substack.com/embed` still shows the publication name **“jQrgen's Substack”** and the description **“My personal Substack”** (checked 2026-10-05). The site only chooses that URL (`newsletter/config.json` → `substack_url`). Rename it in Substack: Settings → Publication details → publication name **Nordic Crypto**, and replace the description. Sender name: **Nordic Crypto**. The subdomain stays **cryptonordic.substack.com**. The public site name is Nordic Crypto; do not set the publication name back to Crypto Nordic.

| Field | Proposal |
|---|---|
| Publication name | **Nordic Crypto** |
| Subdomain | **cryptonordic.substack.com** – created by jQrgen on 2026-10-05 (https://cryptonordic.substack.com, HTTP 200; `/subscribe` HTTP 200). |
| Custom domain (optional, paid add-on) | not needed; the site is https://cryptonordic.no/ |
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
> The summaries are made with the help of artificial intelligence, with human editors (jQrgen and the Nordic Crypto editor). Jørgen S. Notland (jQrgen), Oslo, is the
> responsible person. Nothing here is investment advice. The website also has a calendar of Nordic crypto events and a
> who's who of the people and organisations in the field: https://cryptonordic.no/
>
> Kaupr (kaupr.io) is one of the news sources we follow. Stories from Kaupr are credited to Kaupr.

Short Nordic variants of the about text:
- nn: Nordic Crypto samlar nyheiter om krypto, bitcoin og blokkjede frå heile Norden og gir kvar sak eit kort samandrag med lenkje til kjelda. Ein gong i veka sender vi sakene redaktøren vår har godkjent. Samandraga er laga med hjelp av kunstig intelligens, med menneskelege redaktørar (jQrgen og Nordic Crypto-redaktøren). Ikkje investeringsråd.
- nb: Nordic Crypto samler nyheter om krypto, bitcoin og blokkjede fra hele Norden og gir hver sak et kort sammendrag med lenke til kilden. Én gang i uka sender vi sakene redaktøren vår har godkjent. Sammendragene er laget med hjelp av kunstig intelligens, med menneskelige redaktører (jQrgen og Nordic Crypto-redaktøren). Ikke investeringsråd.
- sv: Nordic Crypto samlar nyheter om krypto, bitcoin och blockkedjor från hela Norden och ger varje nyhet en kort sammanfattning med länk till källan. En gång i veckan skickar vi de nyheter som vår redaktör har godkänt. Sammanfattningarna görs med hjälp av artificiell intelligens, med mänskliga redaktörer (jQrgen och Nordic Crypto-redaktören). Inga investeringsråd.
- da: Nordic Crypto samler nyheder om krypto, bitcoin og blockchain fra hele Norden og giver hver historie et kort resumé med link til kilden. Én gang om ugen sender vi de historier, vores redaktør har godkendt. Resuméerne er lavet med hjælp fra kunstig intelligens, med menneskelige redaktører (jQrgen og Nordic Crypto-redaktøren). Ikke investeringsrådgivning.
- fi: Nordic Crypto kokoaa krypto-, bitcoin- ja lohkoketjuuutisia koko Pohjolasta ja antaa jokaisesta lyhyen tiivistelmän ja linkin lähteeseen. Kerran viikossa lähetämme toimittajamme hyväksymät uutiset. Tiivistelmät on tehty tekoälyn avulla, ihmistoimittajina jQrgen ja Nordic Crypton toimittaja. Ei sijoitusneuvontaa.
- is: Nordic Crypto safnar fréttum af kriptó, bitcoin og bálkakeðjum frá öllum Norðurlöndum og gefur hverri frétt stutta samantekt með tengli á heimildina. Einu sinni í viku sendum við fréttirnar sem ritstjórinn okkar hefur samþykkt. Samantektirnar eru unnar með aðstoð gervigreindar, með mannlegum ritstjórum (jQrgen og ritstjóra Nordic Crypto). Ekki fjárfestingarráðgjöf.

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
> Jørgen S. Notland (jQrgen) in Oslo is the responsible person. Nothing in the newsletter is investment advice. Spotted a mistake or a story we missed? Use
> "Send a tip" on the website: https://cryptonordic.no/tip/
>
> Kaupr (kaupr.io) is one of the news sources we follow. Stories from Kaupr are credited to Kaupr.
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
     edition's language, then `source · date · may require a subscription`. Kaupr stories are credited to Kaupr as a news source.
  3. Link to the website (all stories, calendar, who's who)
  4. Footer: made with the help of artificial intelligence with human editors / not investment advice, why you get this email. No Kaupr sponsor line. Kaupr appears only as the source of a story.
- Norwegian editions (nn/nb) are checked for «AI»/«KI» in our own text before the file is written (external headlines are left as published).
- Sample: `newsletter/sample-digest-2026-10-03-en.md`.
- Suggested rhythm: weekly, Friday morning (Oslo). Nothing is scheduled; jQrgen or the editor pastes and sends.

## 5. Kaupr (news source only)

Stories from Kaupr are credited to Kaupr as the source, the same way as any other outlet. Do not call Kaupr a sponsor of Nordic Crypto, the newsletter, or a calendar event. Do not add a Kaupr footer to the digest. Onchain Pages may be credited when that directory was the source of a company row.

## 6. Email channel (site signup) and moving subscribers to Substack

- Form: footer of every page + `/newsletter/` in all 7 languages, with a privacy note. Off until `newsletter/config.json`
  `enabled: true` (and the Worker is deployed). Test build: `NC_NEWSLETTER=1 NEWSLETTER_ENDPOINT=http://127.0.0.1:8789 NC_SITE_DIR=/tmp/x .venv/bin/python build.py`.
- Double opt-in: signup → confirmation link (valid 7 days) → `confirmed`. Unconfirmed rows are deleted after 7 days.
  No IP address or user agent is stored. CORS only for the public site origin (`site_url.json`) and https://jqrgen.github.io (Kryptonytt).
- Confirmation emails are **not sent** until a provider is chosen and `MAIL_PROVIDER` + `MAIL_SEND_ENABLED=1` are set on the
  Worker (see `tipworker/README.md`). With Substack only: keep the site form off, or use it and import confirmed addresses:
  `.venv/bin/python tipworker/export_subscribers.py --site nordic-crypto` → `state/newsletter/nordic-crypto-confirmed-<date>.csv`
  (mode 600, gitignored; column `email` first) → Substack › Subscribers › Import. Delete the CSV after the import.

## 7. Checklist for jQrgen (updated 2026-10-05)

- [x] Create the Substack publication with your own login; confirm the subdomain (cryptonordic, renamed from nordiccrypto). Done 2026-10-05: https://cryptonordic.substack.com
- [ ] In Substack settings: publication name "Nordic Crypto" (the public page still shows "jQrgen's Substack" as of 2026-10-05), tagline and about text (section 1), sender name, categories (Crypto; Finance, International/News).
- [ ] Reply-to address: still undecided (no public address exists; do not use a private one without deciding).
- [ ] Branding: upload `newsletter/assets/logo-512.png` (logo), `email-banner-1100x220.png` (email header), `cover-1200x630.png`
  (cover/social image), optionally `wordmark-1200x300.png`; accent colour #0f5ea8. (Regenerated 2026-10-05 for the rename to Nordic Crypto: the wordmark
  reads "Nordic Crypto" with the space kept – an earlier version dropped it.)
- [ ] Paste the welcome email; set language English; paid subscriptions off.
- [ ] Choose the confirmation-email provider for the site form (Resend, Buttondown, Postmark via webhook, or Substack import only) and the from-address (needs a domain you control for SPF/DKIM).
- [ ] Give a Cloudflare API token to deploy the Worker (`tipworker/deploy.sh`), then approve switching the form on.
- [x] Set `substack_url` in `newsletter/config.json` (2026-10-05) – the site links to https://cryptonordic.substack.com/subscribe in the footer and on /newsletter/ (7 languages), even while the own form is off.
