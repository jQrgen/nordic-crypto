import type { ChainId } from "./types";

// Groups and icons from the Nexa block explorer (gitlab.com/nexa/explorer, commit 7ed08c8:
// utils.knownTokens("nexa") and public/img/tokens), MIT License, Copyright (c) 2018-2020 Dan Janosik.
// Icons live in public/tokens/nexa/<group without "nexa:">.png. NCSHLD is ours.
const nexaKnown = [
  "nexa:tqcr5dzhetyyughy9uwgsc35altfmhwuk9t5vyn7yjzw9pc0pqqqqyz68skt0",
  "nexa:tptlgmqhvmwqppajq7kduxenwt5ljzcccln8ysn9wdzde540vcqqqcra40x0x",
  "nexa:tzs4e8n7dqtsyk0axx7zvcgt2snzt3t7z07ued0nu89hlvp6ggqqqdrypc4ea",
  "nexa:tztnyazksgqpkphrx2m2fgxapllufqmuwp6k07xtlc8k4xcjpqqqq99lxywr8",
  "nexa:tp0jg4h6gj5gcj5rrf9h6xclxstk52dr72yyttmrn6umrjyd6sqqqsy86tk9q",
  "nexa:tr9v70v4s9s6jfwz32ts60zqmmkp50lqv7t0ux620d50xa7dhyqqqcg6kdm6f",
  "nexa:tpc29y9ahl0m62av6qv4n44vhl9yx8fl2prcvdmfm2zkggg75qqqq3f2seyj9",
  "nexa:tzjntmuvat5px5fp44auwpcjuqk4dkxz5wtysal4e3wmmut08yqqqy2ltpmwz",
  "nexa:tpjkhlhuazsgskkt5hyqn3d0e7l6vfvfg97cf42pprntks4x7vqqqcavzypmt",
  "nexa:trm9zcajh900a02t8fmqklw99uflcvcd6antut98asxfxlq4rcqqqdw80lls5",
  "nexa:tqjn69vd07zu2lf2jwsvhwr5s3yse2epq4823zyazz62732w0vqqq5fhgdygx",
  "nexa:trcetxjzwf9ancuq5vcg2fx7gztc4k7hx98rj7al0zpdssqn4gqqqu2wddynj",
  "nexa:tp5mk7zv78q86jx8xlxsstmt69z6khtawrklcdr27udw722h2sqqqshrajlfj",
];
// Listed upstream without an icon file.
const noIcon = new Set(["nexa:tqcr5dzhetyyughy9uwgsc35altfmhwuk9t5vyn7yjzw9pc0pqqqqyz68skt0", "nexa:tr9v70v4s9s6jfwz32ts60zqmmkp50lqv7t0ux620d50xa7dhyqqqcg6kdm6f"]);

export function isKnownToken(chain: ChainId, id: string): boolean {
  return chain === "nexa" && nexaKnown.includes(id.trim().toLowerCase());
}

export function knownTokenIcon(chain: ChainId, id: string): string | null {
  const group = id.trim().toLowerCase();
  if (!isKnownToken(chain, group) || noIcon.has(group)) return null;
  return `/tokens/nexa/${group.slice("nexa:".length)}.png`;
}
