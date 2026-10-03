# Rules page: claim check (2026-10-03)
Workflow: public-claim-check (find the primary source, read the passage, record the verdict). Data: `rules.json`; page: `tools/rules_page.py` → `/rules/`.
The page stays **pending** (public build shows a placeholder) until the editor sets `"review": "approved"` in `rules.json`.

Verdicts: **verified** = read in the primary source on 2026-10-03; **soften** = true in substance but the wording on the page is generic or simplified; **unverified** = sourced only indirectly. The editor decides on the last two.

| # | Claim on the page | Source | Verdict | Note |
|---|---|---|---|---|
| 1 | The European Commission proposes EU acts; the European Parliament and the Council adopt them | MiCA preamble (Commission proposal, ordinary legislative procedure) | verified | |
| 2 | MiCA is an EU regulation and is directly applicable in member states | MiCA closing formula ("binding in its entirety and directly applicable") | verified | |
| 3 | MiCA applies from 30 Dec 2024; Titles III and IV (stablecoins: ARTs and EMTs) from 30 Jun 2024 | MiCA Art. 149 | verified | |
| 4 | TFR (2023/1113) applies from 30 Dec 2024 | TFR Art. 40 | verified | |
| 5 | AMLR (2024/1624) applies from 10 Jul 2027 | AMLR Art. 90 | verified | |
| 6 | DORA (2022/2554) applies from 17 Jan 2025 | DORA Art. 64 | verified | |
| 7 | ESMA keeps the MiCA register and drafts technical standards | MiCA Art. 109; ESMA interim MiCA register page | verified (register) / soften (standards) | The register is verified; "drafts technical standards" reflects MiCA's many RTS/ITS mandates to ESMA but no single article was quoted. |
| 8 | EBA supervises significant ARTs/EMTs | MiCA Art. 117 | verified | Page says "significant stablecoins" – simplified. |
| 9 | Sweden: Lag (2024:1159) supplements MiCA; Finansinspektionen is the competent authority | SFS 2024:1159, 1 kap. 2 § | verified | |
| 10 | Sweden: suspicious transactions go to Polismyndigheten (Finanspolisen) | Lag (2017:630) | verified | |
| 11 | Denmark: lov nr. 481 af 22. maj 2024 supplements MiCA; Finanstilsynet supervises | Finanstilsynet (DK) practice page citing lov 481 | verified | Act text itself (retsinformation.dk) not read; the regulator's page is the source. |
| 12 | Denmark: Hvidvasksekretariatet is the FIU; Skattestyrelsen handles tax | org-chart entries (hvidvask.dk, sktst.dk) | unverified | Only sourced via the org-chart rows, not via a legal text. |
| 13 | Finland: Laki 402/2024 supplements MiCA; Finanssivalvonta supervises | Finlex 402/2024; FIVA news release 2026 | soften | Finlex pages are JS-rendered and could not be read; FIVA as supervisor comes from FIVA's own news release. |
| 14 | Finland: Rahanpesun selvittelykeskus (KRP) is the FIU | Finlex 444/2017 | soften | Same Finlex limitation; the FIU's own page (poliisi.fi) supports it. |
| 15 | Norway: MiCA is part of the EEA Agreement and applies via the Crypto-Assets Act (LOV-2025-05-27-20); Finanstilsynet supervises | Lovdata, kryptoeiendelsloven § 2 | verified | |
| 16 | Norway: reports of suspicious transactions go to Økokrim | hvitvaskingsloven § 34 | verified | |
| 17 | Iceland: Act 101/2025 implements MiCA; the Central Bank (Seðlabanki Íslands) supervises | Act 101/2025 Art. 1, 3, 16 | verified | |
| 18 | MiCA was incorporated into the EEA Agreement by EEA Joint Committee Decision 41/2025 of 20 Feb 2025 | Icelandic Act 101/2025 (text cites the decision) | soften | Sourced from the Icelandic act, not from the EFTA/EEA register itself. |
| 19 | Iceland: the FIU (Skrifstofa fjármálagreininga lögreglu) receives reports | Act 140/2018 Art. 20 | verified | |
| 20 | Tax authorities per country (Skatteverket, Skattestyrelsen, Verohallinto, Skatteetaten, Skatturinn) handle crypto taxation | org-chart entries | unverified | Not tied to a legal text on this page; wording is generic. |
| 21 | "The ministry prepares the bill; parliament adopts it" | — | soften | Generic description of the national legislative process, not a sourced claim. |

Untranslated: the act names and quotes stay in the original language; the explanatory text is translated into all 7 site languages (AI-assisted, needs native review).
