# Story pictures

Norwegian copyright law protects a photographic picture even when it is not a work of art. Åndsverkloven § 23 covers *fotografiske bilder*: a news photo a newspaper made or bought for a story is protected. A link to the article is not a licence to copy, store, proxy or hotlink that picture.

Nordic Crypto links to the newspaper. It does not reuse the newspaper's photograph.

## Audit (6 October 2026)

Checked the committed data, the build, the public JSON at `/api/v1/`, the live site, and the published `gh-pages` tree.

| Place | What we looked for | Result |
|---|---|---|
| `data/news.json` | `image`, `og_image`, `thumbnail`, `hero`, `enclosure`, `media_content` and the other keys in `tools/press_images.py` | None stored. Published rows have title, url, summary and source, not a picture. |
| `archive/articles.json` | The same fields | None. |
| `fetch.py` (before this change) | `og:image`, RSS `media:content`, image enclosures | Read `og:title` and `og:description` only. Did not save a picture URL. |
| `tools/api_feed.py` | Article image URLs in news items | The news object is a whitelist. It had no article image field. |
| Live `https://cryptonordic.no/api/v1/news.json` (generated 2026-10-06) | Picture URLs on newspaper hosts | None. |
| Live homepage HTML | `<img>` sources | Outlet logos and the newsletter player. No story photograph. |
| `gh-pages` | `og:image` pointing at a newspaper, `media:content`, a blurred hero | None. Story pages on this tree had no photo hero. |

Nothing was deleted, because nothing of that kind was stored. The import now refuses those fields so a later fetch cannot add them.

These stay, and they are not newspaper article photos:

- Outlet logos in `assets/img/logos/`, shown only to name the source.
- Portraits in `assets/img/people/` and `data/images.json`. Those are Wikimedia Commons photographs of public officials, with licence and credit, used on the people pages.
- The newsletter poster `thumbnail.png`, which is our own frame, not a press photo.

## Import rule

`tools/press_images.py` is called from `fetch.py`, the site build and the API.

- `og:image` is counted and dropped. The URL is not returned.
- RSS `media:content`, `media:thumbnail` and image enclosures are counted. The URL is not read into the news row.
- Before `data/news.json` is saved, every row is passed through `strip_press_images`. That removes `image`, `og_image`, `thumbnail`, `hero`, `hero_blur`, `enclosure`, `media_content` and the other keys listed in that file. `status`, `summary` and `url` stay.
- `illustration_id` may be a catalogue id. A value that looks like a URL is removed.
- A picture URL on a newspaper or broadcaster host is treated as someone else's news photo wherever it appears.
- The log records how many pictures were refused. It does not record the URL.

`source_logo` is not in that set. An outlet logo identifies the source and is not an article image.

## What a story picture may be

Each picture in `data/illustrations.json` has `source`, `author`, `license` and `url`. The API copies those fields onto the news item and onto `/api/v1/illustrations.json`. The credit under the picture on the site uses the same facts.

Three kinds are allowed:

1. **original** — drawn for Nordic Crypto (`tools/make_illustrations.py`). Abstract shapes. No real person. No copied logo, banknote or trademark (no bitcoin "B"). Released as CC0.
2. **commons** — a Wikimedia Commons file under CC0, public domain, CC BY or CC BY-SA. The author and the licence are the ones on the Commons file page. A crop is named in `modifications` and in the credit line.
3. **official-press** — a file a public body has released for free use. The page that states the terms is `license_url`. The terms we relied on are written on the record. Each agency is checked on its own. "For the press" is not the same as free use.

A story does not store the picture. `assign()` in `tools/illustrations.py` picks one record from topics, then country. An optional `illustration_id` on a story wins when it is a catalogue id. Existing news rows do not have that field.

## Assignment

First matching rule wins.

| Topics | Country | Picture |
|---|---|---|
| crime | any | Oslo tinghus (Commons, public domain) |
| mining | any | Mining machines (Commons, CC BY-SA) |
| bitcoin | any | Physical bitcoin token (Commons, CC BY-SA, cropped) |
| aml | SE | Riksbank building (official, free use) |
| banking, funds | NO | Norges Bank facade (official, bank's terms) |
| banking, funds | SE | Riksbank building |
| banking, funds, companies, business, payments, stablecoins, defi, tokenisation | any | Our bar-chart illustration |
| policy, tax, cbdc, consumer protection | any | Our columns illustration |
| regulation, mica | any | The country's parliament building |
| events, community | any | The country's parliament building |
| anything else | any | The country's parliament building, or the abstract chain if the country has no picture |

Country pictures: Stortinget (NO, CC BY 2.0, cropped), Riksdagshuset (SE, CC0), Christiansborg (DK, CC BY-SA), Eduskunta (FI, CC BY 2.0), Alþingishúsið (IS, CC BY-SA).

## Official pictures we checked

- **Sveriges Riksbank** image bank (checked 2026-10-06): pictures may be downloaded and used freely if Sveriges Riksbank is credited. Used: the building. Not used: banknotes and coins, which that bank does not release in the same way.
- **Norges Bank** copyright page (checked 2026-10-06): copying from norges-bank.no is allowed when Norges Bank is named, the content is not changed, and it is not used in advertising. Used: the daytime facade (photo: Esten Borgos), scaled to 960 pixels and saved as WebP, not cropped or recoloured. Not used: portraits, notes and coins.
- **Danmarks Nationalbank** press photos are for the press and forbid alteration. Not used. Denmark uses the Commons photograph of Christiansborg.
- **Suomen Pankki** and **Seðlabanki Íslands** were not used. We did not find an equally clear free-use grant.

## How the picture is shown

The site does not render the assigned picture. The same few files were reused across many stories and took the width of each card. The front page, the screen listing and story pages are text: the headline in the page language, the source headline underneath when it differs, the summary, the outlet logo and name, and the date. Nothing in that block is centred.

The JSON API still includes `illustration` on each news item, and `/api/v1/illustrations.json` still lists the catalogue. The field is the licensed record (source, author, license, url, file_url), not a decorative stand-in, so a client that already reads it keeps the credit. `file_url` still points at the file on this site.

`og:image` on story pages is the Nordic Crypto brand image, not the assigned picture.

Outlet logos stay next to the outlet name. They are not this picture.
