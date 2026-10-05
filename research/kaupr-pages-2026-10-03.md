# Kaupr Onchain Pages check, 3 Oct 2026

We went through every company at https://www.kaupr.io/pages (40 profiles) and compared each one with the Nordic Crypto org chart.

How we checked:
- Each new entry is verified against the company's own website, its own press release, or a business register: Brønnøysundregistrene; Bolagsverket data via allabolag.se; CVR data via ownr.dk. Kaupr's description alone was not enough.
- Kaupr is credited as a source on every entry where we used it.
- All new entries carry `"review": "pending"` in `data/orgchart_nordic.json`. That keeps them out of the public site until the editor lists their ids in `queue/approved.json` → `org.approve`. `approve_countries` does not cover them.

Kaupr is one of the news sources we follow. Company rows that used Kaupr’s Onchain Pages credit Kaupr as that source.

## Already in the org chart (no change)
Bare Bitcoin, Coinmotion, DNB, Firi, Goobit, Januar, K33, Kvarn Capital, NBX, Nordic Blockchain Association, Norges Bank, Northstake, Penning, Safello, TÝR Markets, Valuno, Virtune.

## BTCX
BTCX is a brand of Goobit. It is not a separate entry. The existing `goobit` entry is now named "Goobit (BTCX)" and has these changes:
- aliases BTCX, Goobit AB and Goobit Group AB;
- a new source, https://bt.cx/sv/ ("BTCX drivs av Goobit AB" (registry entry checked));
- the Kaupr BTCX profile as a source.

## Added (pending editor review)
| id | Company | Country | Group | Verified by |
|---|---|---|---|---|
| no-ace-digital | Ace Digital AS | NO | Companies & startups | acedigital.no (Oslo address, Euronext Growth Oslo: ACED); Brønnøysund register entry checked |
| no-web3-creatives | Web3 Creatives AS | NO | Companies & startups | web3creatives.no ("agency based in Oslo"); Brønnøysund register entry checked |
| dk-aryze | ARYZE ApS | DK | Companies & startups | CVR entry checked (København K); aryze.io |
| dk-bloxcel | BloXcel | DK | International players in the Nordics (moved: no Danish legal entity verified) | bloxcel.com/about ("Headquartered in Denmark, with strategic presence in … Sweden") |
| se-blockchain-sweden | Blockchain Sweden | SE | Associations & communities | blockchainsweden.se; Bolagsverket registry entry checked |
| se-divly | Divly (Ragnaros AB) | SE | Companies & startups | divly.com terms (Ragnaros AB registry entry checked, Stockholm) |
| se-dwellir | Dwellir AB | SE | Companies & startups | dwellir.com footer (registry entry checked, Uppsala) |
| se-firstblock | FirstBlock AB | SE | Companies & startups | the company's own press release (Stockholm, 2023); Bolagsverket registry entry checked |
| se-h100 | H100 Group AB | SE | Companies & startups | h100.group; Bolagsverket registry entry checked |
| se-hilbert-group | Hilbert Group AB (publ) | SE | Investors & funds | hilbert.group (Nasdaq First North, HILB B); Bolagsverket registry entry checked |
| se-pretax | PRETAX AB | SE | Companies & startups | pretax.se (Kungsgatan 8, Stockholm; crypto tax articles) |
| se-true-original | TRUE Original (True Value Software AB) | SE | Companies & startups | trueoriginal.com terms page (True Value Software AB, Stockholm; blockchain-backed certificates) |
| intl-visa | Visa | SE | International players in the Nordics | Visa press release 19 June 2025: Swedish/regional head office in Stockholm, over 300 staff |
| intl-swift | Swift (S.W.I.F.T. Nordic AB) | SE | International players in the Nordics | Bolagsverket registry entry checked, Stockholm (swift.com blocks automated fetches) |
| intl-d-fine | d-fine AB | SE | International players in the Nordics | d-fine.com Sweden page (Stockholm office); Bolagsverket registry entry checked |
| intl-okx | OKX Europe | NORDIC | International players in the Nordics | okx.com "OKX goes live in the Nordics" (DK/SE/NO/FI); OKX launch with a GM for Central Europe and the Nordics and local growth staff (Fintech in Nordics, Kaupr) |


## Skipped
| Company | Reason |
|---|---|
| Artely | Nordic presence verified (Artely AB registry entry checked, Stockholm), but the gallery's own site does not confirm that it sells blockchain or NFT-registered works. That claim rests on Kaupr alone. |
| Bitwise Europe | No Nordic licence, office or entity found. It has Nasdaq Stockholm ETP listings and a partnership with Alfakraft (a Swedish fund manager), but that is distribution, not a local organisation. |
| Circle | No Nordic office or entity found. The European entity is in Paris, and USDC/EURC distribution through Nordic platforms (e.g. Safello) is not Circle's own presence. |
| Strategy | No Nordic bitcoin activity. A small software subsidiary, MicroStrategy Sweden AB (3 employees), is registered in Stockholm, but its link to the bitcoin-treasury business is not relevant and its parent could not be confirmed from the register snippet. |

## Editor rules applied (Kryptonytt editor, 3 Oct 2026)
- National categories need a local legal entity (AS/AB/ApS/Oy/ehf, or a branch with an office or services in the country); otherwise "International players in the Nordics". BloXcel was moved there (its own site says it is headquartered in Denmark, but no Danish legal entity could be verified). TRUE Original was confirmed through its own terms page (True Value Software AB, Stockholm).
- Companies whose licence doesn't cover the country, or whose crypto link is undocumented, are rejected:
  - **Binance**: rejected. No MiCA authorisation; per Kaupr it stopped serving new EU customers on 1 July 2026. Having a Swedish AB doesn't make it a licensed Nordic service.
  - **Bybit EU**: rejected. It has no Nordic entity or office, and its own press release only says Nordic services are planned for 2026.
  - **Visa** and **Swift**: the crypto link is now documented from their own sites (Visa Stablecoin Solutions; Swift's blockchain-based ledger press release of 29 Sep 2025).
- Generic finance industry bodies list only the chair and vice chair:
  - Finans Norge: the CEO and a director were left out; chair Inge Reinertsen was added from the registry. The registry lists no vice chair.
  - Fintech Norway: the CEO was left out and the chair kept. The registry lists no vice chair.
- People are never merged without a source. Registry-sourced people carry the source title "Name and role only from the registry".

## Editor decisions, 4 Oct 2026
- Approved: dk-aryze, se-blockchain-sweden, se-divly, se-firstblock, se-h100, se-hilbert-group, se-pretax, se-true-original, intl-visa, intl-swift, intl-d-fine, intl-okx; plus no-ace-digital, no-web3-creatives, se-dwellir after the org numbers were removed from their source titles.
- Rejected: dk-bloxcel.
- OKX: added the ESMA CASP register (esma.europa.eu …/2024-12/CASPS.csv): OKX Europe Limited, MFSA Malta, authorised 27 Jan 2025, passported to NO, SE, DK, FI, IS among others. Description corrected: the June 2025 launch covered SE/FI/DK; Norway is documented from July 2025.
- Kaupr and Morten Myrstad: no event-sponsor note. Kaupr is a news source only.
- The privacy gate now also blocks org numbers in visible text, including source titles.
