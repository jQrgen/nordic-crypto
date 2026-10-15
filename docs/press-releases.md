# Press releases for each newsletter issue

`tools/press_release.py` turns a published newsletter issue into a short, factual press release
(headline, 3–5 key stories with source links, issue link, video link, press contact
jqrgen@nordiccrypto.no) in each contact's language (no, sv, da, fi, is, en) and sends **one
individual email per contact** from `Nordic Crypto <jqrgen@nordiccrypto.no>` via Resend.
No CC or BCC lists are ever used: every message has exactly one `to` address.

## Review-first

```sh
.venv/bin/python tools/press_release.py --issue 002            # drafts only (default)
.venv/bin/python tools/press_release.py --issue 002 --dry-run  # never sends, even with --send
.venv/bin/python tools/press_release.py --issue 002 --send     # delivers after review
```

Every run writes to `out/press/<issue>/` (gitignored): `press-<id>-<lang>.txt` and `.html` per
language, `press-<id>-recipients.csv` (who would get what, and why someone is skipped) and
`press-<id>-summary.json`. jQrgen reads these before the first `--send`. The GitHub workflow
(`press-release.yml`, see `/workspace/press-newsletter-workflow.patch`) only sends when its `send`
input is set to `true`.

Without `RESEND_API_KEY` a `--send` run skips sending and still writes drafts. `--send` also
refuses to run without `PRESS_UNSUB_ORIGIN` (https) and `PRESS_UNSUB_SECRET`, so no email can go
out without a working one-click unsubscribe link.

## Copy per issue

`data/press/issues/<id>.json` holds the chosen stories (by URL) and the headline and story lines
per language. Without it, the tool takes the first five stories from the published English issue
and uses English story text with localised framing. Tone is factual and quote-free.

Brand rules are checked on every draft and a failing draft stops the run: always "Nordic Crypto"
(never the reversed name), no "made with AI" in the opening, and Kaupr is never called a sponsor.

## Contacts and sources

`data/press/contacts.csv`: `name, outlet, country, role/beat, email, source_url, verified_date, language`.

- Only addresses the outlet itself publishes (contact, tips or staff pages) go in. Never guess an
  address from a `firstname.lastname@` pattern. Rows without an https `source_url` are skipped.
- Named journalists are listed only when the outlet publishes their work address and their beat is
  finance, fintech, investing or crypto.
- Keep `source_url` and `verified_date` for every row; re-check them at least twice a year and
  remove addresses that are no longer published.

## Unsubscribe and suppression

- Every email has a visible unsubscribe link and the headers
  `List-Unsubscribe: <https://…/api/press-unsubscribe?h=…&sig=…>, <mailto:jqrgen@nordiccrypto.no?subject=unsubscribe>`
  and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058).
- The link carries a SHA-256 hash of the address (not the address) and an HMAC with
  `PRESS_UNSUB_SECRET`. The endpoint `/api/press-unsubscribe` must record the hash; it is then
  added to `data/press/suppressed.csv` (the file accepts a plain address or a 64-hex hash).
- Requests by reply or by email: `tools/press_release.py --suppress someone@outlet.no --reason "asked by email"`.
- Suppressed addresses are never mailed again, even if they stay in `contacts.csv`.

## Idempotent state

`data/press/sent/<issue>.json` stores SHA-256 hashes of addresses already sent for that issue. It is
written after each successful send, so a re-run or a crash never mails anyone twice. Resend also
gets an `Idempotency-Key` per issue and recipient.

## GDPR and markedsføringsloven

- **Legal basis:** legitimate interest (GDPR art. 6(1)(f)). Press releases about published news,
  sent to addresses that media outlets publish so they can receive news tips and press releases,
  are an expected use. The balancing test is documented here: low volume (one email per weekly
  issue), relevant to the recipient's beat, easy to stop.
- **Markedsføringsloven § 15 / ePrivacy:** the press release is editorial information, not an offer
  of goods or services, and goes to role and desk addresses published for this purpose. Named
  journalists are only included where the outlet publishes the address for contact on their beat.
  Do not add advertising or sales offers to these emails; that would need prior consent.
- **Information duty (GDPR art. 14):** each email says why the recipient gets it, who sends it and
  how to stop it. Data held: name, outlet, role, public work address, source URL, date checked.
- **Objection:** an unsubscribe or a reply asking to stop is honoured at once via the suppression
  list, and the person is not re-added from the same source.
- **Records:** keep `source_url` for every contact, so the origin of each address can be shown on
  request (art. 15), and delete rows on request (art. 17), keeping only the hash in `suppressed.csv`.

## Setup before the first send

1. Resend: add and verify the domain `nordiccrypto.no` (SPF/DKIM TXT records, MX for the
   `send` subdomain as Resend lists them, and a DMARC record such as `v=DMARC1; p=none; rua=mailto:jqrgen@nordiccrypto.no`).
2. Repository secrets: `RESEND_API_KEY`, `PRESS_UNSUB_SECRET`; variable `PRESS_UNSUB_ORIGIN`.
3. Deploy an `/api/press-unsubscribe` route (GET page with a button, POST for one-click) that
   records the hash for `suppressed.csv`.
4. Apply the workflow patch, run it with `send: false`, review the artifact, then run with `send: true`.
