# Nordic Crypto – own email list

The newsletter signup is a form on this site. It posts to the tip Worker (`POST /api/subscribe`). Confirmed addresses live in a private Cloudflare D1 database. They are not in the GitHub repo, and the site does not load a third-party signup form.

The site used to link to a Substack publication. That link, the embed, and the CSV-for-import path are gone. Leave that publication unused. Do not import this list into it.

Each published issue is mailed with `newsletter/send_issue.py`. Nothing is sent until you set a provider and `MAIL_SEND_ENABLED=1`. This file uses placeholders (`FROM-ADDRESS`, `RESEND_API_KEY`). Do not commit real keys or addresses.

Sign-off on the English issue stays **The Nordic Crypto team**. Kaupr is a news source only. Do not add a Kaupr sponsor line.

## Where the addresses live

| What | Where |
|---|---|
| Database | Cloudflare D1 `nordic-crypto-tips` (same database as reader tips) |
| Table | `subscribers` (`tipworker/migrations/0003_subscribers.sql`) |
| Columns | email, site (`nordic-crypto`), lang, status (`pending` / `confirmed` / `unsubscribed`), token hash, timestamps |
| Not stored | IP address, user agent |
| Not in git | the rows themselves. `state/` is gitignored |

A pending address is deleted if it is not confirmed within 7 days. Unsubscribed rows stay, with status `unsubscribed`, so they are not mailed again.

Operator export (counts on stdout, addresses only in the file, mode 600):

```
.venv/bin/python tipworker/export_subscribers.py --site nordic-crypto
```

The CSV lands in `state/newsletter/` (gitignored). Delete it when you are done. Do not commit it and do not paste it into a public issue.

## 1. Deploy the Worker

Needs `CLOUDFLARE_API_TOKEN` (Account › Workers Scripts: Edit, Account › D1: Edit, Account › Account Settings: Read) and a workers.dev subdomain.

```
tipworker/deploy.sh
```

That creates the D1 database if needed, applies migrations (including `subscribers`), and deploys the Worker. It does **not** turn on mail.

`deploy.sh` creates `UNSUB_SECRET` inside Cloudflare the first time and does not print it. The send script needs the **same** value. Set it yourself and keep a private copy that is not in git:

```
umask 077
openssl rand -hex 32 > "$HOME/.nordic-crypto-unsub"
npx wrangler secret put UNSUB_SECRET < "$HOME/.nordic-crypto-unsub"
```

Run that from `tipworker/` (or pass `--config tipworker/wrangler.toml` from the repo root). If `deploy.sh` already created a secret you cannot read, run the commands above once. That replaces it. No issue has been mailed yet, so there are no old unsubscribe links to keep.

## 2. DNS and a From address

Pick an address on a domain you control, for example `newsletter@nordiccrypto.no`. The examples below say `FROM-ADDRESS`. Put the real address only in Cloudflare and in your shell, not in this repo.

**Resend or Mailgun** (either one can send the list):

1. Add the domain in that provider’s dashboard.
2. Add the SPF and DKIM records they show you, on the DNS host for `nordiccrypto.no`. Copy the records from the provider. This repo does not invent them.
3. Wait until the provider says the domain is verified.
4. Create an API key. Store it as a Worker secret and as a shell variable. Do not commit it.

**Cloudflare Email Routing** receives mail for the domain and can forward replies to you. It does **not** send a newsletter to this list. Use it only if you want a reply address. Sending still needs Resend, Mailgun, or an HTTPS webhook in front of another transactional provider.

**Worker secrets** (confirmation and welcome mail; same names as the send script):

```
# Resend
npx wrangler secret put RESEND_API_KEY
npx wrangler secret put MAIL_FROM_NORDIC_CRYPTO
# value: Nordic Crypto <FROM-ADDRESS>

# or Mailgun
npx wrangler secret put MAILGUN_API_KEY
npx wrangler secret put MAILGUN_DOMAIN
# optional, EU region: https://api.eu.mailgun.net
npx wrangler secret put MAILGUN_API_BASE
```

Then set the vars (these are not secret, but they arm sending):

```
# in tipworker/wrangler.toml [vars], or `wrangler secret put` if you prefer
MAIL_PROVIDER = "resend"          # or "mailgun" or "webhook"
MAIL_SEND_ENABLED = "1"
```

`MAIL_PROVIDER=webhook` also needs `MAIL_WEBHOOK_URL` (`https://…`) and `MAIL_WEBHOOK_TOKEN`. The Worker POSTs JSON `{to, from, subject, text, html, site, lang, kind}`.

Leave `MAIL_SEND_ENABLED` unset until the From domain verifies. Until then, signups are stored and **no** confirmation mail goes out.

## 3. Turn the form on

In `newsletter/config.json`:

```
"enabled": true,
"endpoint": "https://nordic-crypto-tips.<account>.workers.dev"
```

`endpoint` may stay `null` when `tipserver/config.json` `public_endpoint` is already that workers.dev URL. Rebuild and publish the site after the change.

The form is in the footer, on the front page, and at `/newsletter/#signup`, in all 7 site languages. It asks for the address and a required consent checkbox, then the Worker sends a confirmation link (valid 7 days). Every issue mail includes an unsubscribe link (and a `List-Unsubscribe` header, including one-click).

Test build, form only, nothing public:

```
NC_NEWSLETTER=1 NEWSLETTER_ENDPOINT=http://127.0.0.1:8789 NC_SITE_DIR=/tmp/nc-nl .venv/bin/python build.py
```

## 4. Send an issue

Dry run first. It prints counts only.

```
.venv/bin/python newsletter/send_issue.py --issue 001 --dry-run
```

Send, after the provider and the From address work:

```
export MAIL_SEND_ENABLED=1
export MAIL_PROVIDER=resend
export RESEND_API_KEY=…                  # placeholder; the real key stays in your shell
export MAIL_FROM_NORDIC_CRYPTO='Nordic Crypto <FROM-ADDRESS>'
export UNSUB_SECRET="$(cat "$HOME/.nordic-crypto-unsub")"
export NEWSLETTER_WORKER_ORIGIN=https://nordic-crypto-tips.<account>.workers.dev
export CLOUDFLARE_API_TOKEN=…            # read D1; not committed
.venv/bin/python newsletter/send_issue.py --issue 001
```

- Confirmed `nordic-crypto` rows only. Each person gets `newsletter/published/<id>/issue.<lang>.html` when that file exists, otherwise the English issue.
- The mail is left-aligned HTML plus a plain-text part, with a link to the issue on https://nordiccrypto.no/ and an unsubscribe link.
- A second run skips ids already recorded in `state/newsletter/sent-issue-<id>.json` (mode 600, ids only, gitignored). `--force` sends again.
- Mailgun: set `MAIL_PROVIDER=mailgun`, `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`. EU accounts also set `MAILGUN_API_BASE=https://api.eu.mailgun.net`.

Weekly digest from approved stories (still does not send by itself):

```
./build.sh
.venv/bin/python newsletter/digest.py --lang nb
.venv/bin/python newsletter/send_issue.py \
  --html newsletter/out/digest-YYYY-MM-DD-nb.html \
  --text newsletter/out/digest-YYYY-MM-DD-nb.txt \
  --subject "Nordic Crypto – uka som gikk" --lang nb --dry-run
```

`{{unsubscribe}}` in the digest is replaced per recipient. Norwegian digest text is checked for «AI»/«KI» before it is written; our own text says «kunstig intelligens».

## 5. Privacy (what the site says)

- The form and the About page say we store the address, the language and the time in our private Cloudflare database, not the IP address, and not on GitHub.
- Cloudflare Web Analytics counts visits in aggregate, without cookies. The site says so. It does not claim there is no analytics.
- Consent: the checkbox on the form, then the confirmation email. Unconfirmed rows are deleted after 7 days.
- Unsubscribe: link in every mail, and the Worker page `GET/POST /api/unsubscribe` (a button, so a mail scanner does not unsubscribe someone). RFC 8058 one-click is the POST with `List-Unsubscribe=One-Click`.
- The list is only for this newsletter. It is not sold.

## Checklist

- [ ] Deploy `tipworker/deploy.sh` so D1 has `subscribers`.
- [ ] Save `UNSUB_SECRET` in a private file and set the same value on the Worker.
- [ ] Verify a From domain (Resend or Mailgun SPF/DKIM). Email Routing is for replies only.
- [ ] Set `MAIL_PROVIDER`, `MAIL_SEND_ENABLED=1`, the API key, and `MAIL_FROM_NORDIC_CRYPTO` on the Worker.
- [ ] Set `newsletter/config.json` `enabled` to true and publish the site.
- [ ] Dry-run `newsletter/send_issue.py --issue 001`, then send.
