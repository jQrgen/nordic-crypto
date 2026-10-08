# Country domains Worker

Cloudflare Worker `nordiccrypto-country-domains`. It serves the site on its own address on
**nordiccrypto.se, nordiccrypto.fi, nordiccrypto.dk and nordiccrypto.is**. The address bar keeps the country
domain while the reader browses. The pages come from https://nordiccrypto.no/ (GitHub Pages, unchanged).

| Domain | Front page (`/`) | Origin path |
|---|---|---|
| nordiccrypto.se | Swedish | `/sv/` |
| nordiccrypto.fi | Finnish | `/fi/` |
| nordiccrypto.dk | Danish | `/da/` |
| nordiccrypto.is | Icelandic | `/is/` |

- `www.<country>` answers 301 to the apex on the same country domain.
- `/<lang>/` for the country's own language answers 301 to `/`. English lives at `/en/` (the origin root). Every
  other path is proxied unchanged: `/about/`, `/da/stories/…`, `/assets/…`, `/api/v1/…`.
- HTML links to nordiccrypto.no, absolute or relative, are rewritten to paths on the country domain. Origin
  redirect `Location` headers are rewritten the same way. `<link rel=canonical>`, the hreflang alternates,
  `og:url` and share links stay on https://nordiccrypto.no/, so search engines see one canonical site.
- The IP-based language pick (`tools/langselect.js`) only runs on the English home page. On a country domain `/`
  is the country's language page, so the pick never runs there, and the Worker strips the script from `/en/`. An
  explicit choice in the language switcher (the `nc_lang` cookie) still wins on `/`. For example, choosing
  English on nordiccrypto.se sends later visits to `/` on to `/en/`.
- Nothing is stored or logged. Workers observability is off.

## Cloudflare setup
- Zones (type full) in the Cloudflare account. Each zone has proxied `AAAA 100::` records for the apex and `www`,
  so the Worker routes catch the traffic. SSL is Full (strict), Always Use HTTPS is on, and the minimum TLS version is 1.2.
- Zone routes: `<domain>/*` and `www.<domain>/*` → `nordiccrypto-country-domains`. No workers.dev subdomain is needed.
- Nameservers at Domeneshop: the Cloudflare pair shown on each zone (`daisy.ns.cloudflare.com`,
  `kip.ns.cloudflare.com`). The Domeneshop API cannot change nameservers, so this step happens in the Domeneshop web UI.
  DNSSEC at Domeneshop must be off (DS removed) when the nameservers move. Otherwise resolvers fail validation.
- nordiccrypto.eu stays a Domeneshop HTTP forward to https://nordiccrypto.no/.

Deploy: `npx wrangler deploy` in this directory (`CLOUDFLARE_API_TOKEN` with Workers Scripts Edit and Workers Routes Edit).
You can also upload `worker.js` as an ES module with the Workers API.

The tip worker’s CORS list includes https://nordiccrypto.no, www, these four country domains (apex and www) and
https://jqrgen.github.io, so a form on nordiccrypto.se posts with that origin.
