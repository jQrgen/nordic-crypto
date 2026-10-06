# Nordic Crypto — Raspberry Pi news screen

Lightweight fullscreen news board for a Pi. Pulls live data from the Nordic Crypto JSON API and **self-updates** when you publish a new kiosk version under `gh-pages/kiosk/`.

Designed for low RAM: static HTML/JS, local `python3 -m http.server`, Chromium kiosk with small cache and no extensions. **Pi 3 / 4 / 5 recommended.** Pi Zero 2 may work but Chromium is tight on memory.

## Quick install (Pi)

```bash
curl -fsSL https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/kiosk/scripts/bootstrap.sh | bash
```

Requires Raspberry Pi OS with desktop, autologin to the graphical session (default), and network. The service is enabled for `graphical.target` so the news screen starts **fullscreen on every boot**.

Or copy this folder and run `bash scripts/install.sh`.


## Config

Edit `/opt/nordic-crypto-kiosk/config.env` (from `config.example.env`):

| Key | Default | Meaning |
|---|---|---|
| `API_BASE` | raw GitHub `gh-pages` | Avoids broken custom-domain cert |
| `LANG` | `en` | Summary language: `en` `nn` `nb` `sv` `da` `fi` `is` |
| `SLIDE_SEC` | `22` | Seconds per headline |
| `NEWS_REFRESH_SEC` | `900` | Reload feed |
| `UPDATE_BASE` | `…/gh-pages/kiosk` | Where VERSION + files are published |

Keys: `←` `→` / Space change slide, `R` reload feed.

## Auto-update (app)

1. Bump `VERSION` in this folder.
2. Publish the folder contents to **`https://github.com/jQrgen/nordic-crypto` → `gh-pages` branch path `/kiosk/`** (include `VERSION` + `MANIFEST.txt`).
3. Pi timer runs `scripts/update.sh` every 6 hours (and soon after boot). If remote `VERSION` differs, it downloads every path in `MANIFEST.txt` and restarts the kiosk.

News content updates separately every `NEWS_REFRESH_SEC` from `/api/v1/news.json`.

## Publish kiosk to gh-pages

From a machine with the nordic-crypto checkout (or a cloud agent):

```bash
# example: copy into gh-pages worktree
rsync -a --delete \
  --exclude config.env --exclude web/config.js --exclude .git \
  nordic-crypto-pi-kiosk/ /path/to/nordic-crypto-gh-pages/kiosk/
# commit + push gh-pages
```

## Notes

- Sign-off on screen: **The Nordic Crypto team**. Not investment advice.
- Kaupr is a news source only (never shown as sponsor).
- Until `cryptonordic.no` has a matching HTTPS cert, keep `API_BASE` on raw.githubusercontent.com.
