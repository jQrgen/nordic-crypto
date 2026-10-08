// One-off token setup. The operator runs this locally. It is not part of the
// Worker and it is not run by the build.
//
// It reads NEXA_HOT_KEY / BCH_HOT_KEY from the environment, or asks on stdin
// with echo off. It does not write a file and it does not print the key.
//
// Default is Nexa testnet and Bitcoin Cash chipnet. Mainnet is refused unless
// --mainnet is present. Set MINT_SETUP_I_AM_THE_OPERATOR=yes.
//
//   MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs
//   MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs --chain nexa
//   MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs --dry-run
//
// Prints the public group id and category id. Set those as Worker vars:
//   NEXA_PARENT_GROUP  and  BCH_CATEGORY

import { spawnSync } from "node:child_process";
import readline from "node:readline";
import { pathToFileURL } from "node:url";
import { broadcastBch, broadcastNexa, electrumRequest } from "../src/broadcast.js";
import { bchAddress, signBchGenesis, signBchToSelf } from "../src/bch/sign.js";
import { signNexaGroup } from "../src/nexa/sign.js";
import { PrivateKey } from "libnexa-ts";

const BCH_GENESIS_MIN = 800 + 546 + 400;
const BCH_PREP_MIN = BCH_GENESIS_MIN + 400;
const NEXA_MIN = 5000;

const NEXA_MAINNET = "wss://electrum.nexa.org:20004";
const BCH_MAINNET = ["wss://bch.imaginary.cash:50004"];

export function networkFromArgs(argv) {
  return argv.includes("--mainnet") ? "mainnet" : "testnet";
}

export function chainsFromArgs(argv) {
  const i = argv.indexOf("--chain");
  if (i < 0) return ["nexa", "bch"];
  const value = argv[i + 1];
  if (value === "nexa" || value === "bch") return [value];
  if (value === "both") return ["nexa", "bch"];
  const err = new Error("bad_chain");
  err.code = "bad_chain";
  throw err;
}

export function assertOperatorNetwork(argv, operator) {
  if (operator !== "yes") {
    const err = new Error("not_operator");
    err.code = "not_operator";
    throw err;
  }
  const network = networkFromArgs(argv);
  if (network === "mainnet" && !argv.includes("--mainnet")) {
    const err = new Error("mainnet_blocked");
    err.code = "mainnet_blocked";
    throw err;
  }
  return network;
}

function rowsOf(result) {
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.unspent)) return result.unspent;
  return [];
}

async function firstRequest(urls, method, params) {
  let last = null;
  for (const url of urls) {
    const res = await electrumRequest(url, method, params);
    if (res && res.ok) return res;
    last = res;
  }
  return last;
}

function bchCoins(result) {
  return rowsOf(result)
    .filter((row) => row && row.tx_hash && row.tx_pos != null && row.value != null && !row.token_data && row.token_amount == null)
    .map((row) => ({ txid: String(row.tx_hash), vout: Number(row.tx_pos), satoshis: Number(row.value) }))
    .filter((row) => row.satoshis > 0);
}

function nexaCoins(result) {
  return rowsOf(result)
    .filter((row) => row && row.outpoint_hash && row.value != null)
    .map((row) => ({ outpoint: String(row.outpoint_hash), satoshis: Number(row.value) }))
    .filter((row) => row.satoshis > 0);
}

function publicText(text, secret) {
  const s = String(text || "failed");
  if (secret && s.includes(String(secret).trim())) return "failed";
  return s.slice(0, 180);
}

function say(line) {
  process.stderr.write(line + "\n");
}

async function readSecret(name) {
  const fromEnv = process.env[name];
  if (fromEnv && fromEnv.trim().length >= 32) return fromEnv.trim();
  if (!process.stdin.isTTY) {
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    const text = Buffer.concat(chunks).toString("utf8").trim();
    if (text.length >= 32) return text;
    return null;
  }
  if (process.platform !== "win32") spawnSync("stty", ["-echo"], { stdio: "inherit" });
  const value = await new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(name + " (not echoed): ", (answer) => {
      rl.close();
      resolve(String(answer || "").trim());
    });
  });
  if (process.platform !== "win32") spawnSync("stty", ["echo"], { stdio: "inherit" });
  process.stderr.write("\n");
  return value.length >= 32 ? value : null;
}

function nexaUrls(network) {
  if (network === "testnet") return null;
  return [NEXA_MAINNET];
}

async function nexaUnspent(address, network) {
  if (network === "testnet") {
    const res = await electrumRequest(
      "wss://testnet-electrum.nexa.org:30004",
      "blockchain.address.listunspent",
      [address, "exclude_tokens"],
    );
    return res && res.ok ? nexaCoins(res.result) : null;
  }
  const res = await firstRequest(nexaUrls(network), "blockchain.address.listunspent", [address, "exclude_tokens"]);
  return res && res.ok ? nexaCoins(res.result) : null;
}

async function bchUnspent(address, network) {
  const urls = network === "testnet"
    ? ["wss://chipnet.imaginary.cash:50004", "wss://chipnet.bch.ninja:50004"]
    : BCH_MAINNET;
  const res = await firstRequest(urls, "blockchain.address.listunspent", [address]);
  return res && res.ok ? bchCoins(res.result) : null;
}

async function setupNexa({ secret, network, dryRun }) {
  const nets = network === "mainnet" ? "mainnet" : "testnet";
  let hot;
  try {
    hot = PrivateKey.fromWIF(secret, nets).toAddress().toString();
  } catch {
    return { ok: false, error: "bad_key" };
  }
  const named = process.env.NEXA_HOT_ADDRESS;
  if (named && named !== hot) return { ok: false, error: "address_mismatch", hot };
  const coins = await nexaUnspent(hot, network);
  if (!coins) return { ok: false, error: "utxo_unavailable" };
  const coin = coins.sort((a, b) => b.satoshis - a.satoshis)[0];
  if (!coin || coin.satoshis < NEXA_MIN) return { ok: false, error: "insufficient_funds" };
  let signed;
  try {
    signed = signNexaGroup({ secret, utxo: coin, network });
  } catch (e) {
    return { ok: false, error: e && e.code ? e.code : "sign_failed" };
  }
  if (dryRun) return { ok: true, group: signed.group, txid: signed.txid, dryRun: true };
  const sent = network === "testnet"
    ? await broadcastNexa(signed.hex)
    : await broadcastNexa(signed.hex, { url: NEXA_MAINNET });
  if (!sent || !sent.ok) return { ok: false, error: publicText(sent && sent.error ? JSON.stringify(sent.error) : "broadcast_rejected", secret) };
  return { ok: true, group: signed.group, txid: signed.txid };
}

async function setupBch({ secret, network, dryRun }) {
  const prefix = network === "mainnet" ? "bitcoincash" : "bchtest";
  let hot;
  try {
    hot = bchAddress(secret, { prefix, tokenSupport: true });
  } catch {
    return { ok: false, error: "bad_key" };
  }
  const named = process.env.BCH_HOT_ADDRESS;
  if (named && named !== hot) return { ok: false, error: "address_mismatch", hot };
  const coins = await bchUnspent(hot, network);
  if (!coins) return { ok: false, error: "utxo_unavailable" };
  let funding = coins.find((row) => row.vout === 0 && row.satoshis >= BCH_GENESIS_MIN);
  if (!funding) {
    const source = coins.filter((row) => row.satoshis >= BCH_PREP_MIN).sort((a, b) => b.satoshis - a.satoshis)[0];
    if (!source) return { ok: false, error: "insufficient_funds" };
    let prep;
    try {
      prep = signBchToSelf({ secret, funding: source, prefix });
    } catch (e) {
      return { ok: false, error: e && e.code ? e.code : "sign_failed" };
    }
    if (!dryRun) {
      const sent = await sendBch(prep.hex, network);
      if (!sent.ok) return { ok: false, error: publicText(sent.error, secret) };
    }
    funding = { txid: prep.txid, vout: 0, satoshis: prep.satoshis };
  }
  let signed;
  try {
    signed = signBchGenesis({ secret, funding, prefix });
  } catch (e) {
    return { ok: false, error: e && e.code ? e.code : "sign_failed" };
  }
  if (dryRun) return { ok: true, category: signed.category, txid: signed.txid, dryRun: true };
  const sent = await sendBch(signed.hex, network);
  if (!sent.ok) return { ok: false, error: publicText(sent.error, secret) };
  return { ok: true, category: signed.category, txid: signed.txid };
}

async function sendBch(hex, network) {
  if (network === "testnet") return broadcastBch(hex);
  return broadcastBch(hex, { urls: BCH_MAINNET });
}

export async function runSetup(argv, secrets) {
  const network = assertOperatorNetwork(argv, process.env.MINT_SETUP_I_AM_THE_OPERATOR);
  const chains = chainsFromArgs(argv);
  const dryRun = argv.includes("--dry-run");
  const lines = ["network=" + network];
  if (dryRun) lines.push("dry_run=1");
  let failed = false;
  for (const chain of chains) {
    const secret = secrets[chain];
    if (!secret) {
      say(chain + ": key missing");
      failed = true;
      continue;
    }
    const result = chain === "nexa"
      ? await setupNexa({ secret, network, dryRun })
      : await setupBch({ secret, network, dryRun });
    if (!result.ok) {
      say(chain + ": " + result.error);
      if (result.hot) say(chain + " address from key: " + result.hot);
      failed = true;
      continue;
    }
    if (chain === "nexa") {
      lines.push("NEXA_PARENT_GROUP=" + result.group);
      lines.push("nexa_txid=" + result.txid);
    } else {
      lines.push("BCH_CATEGORY=" + result.category);
      lines.push("bch_txid=" + result.txid);
    }
  }
  return { failed, lines };
}

async function main() {
  if (process.env.MINT_SETUP_I_AM_THE_OPERATOR !== "yes") {
    say("Refusing. The operator runs this, with MINT_SETUP_I_AM_THE_OPERATOR=yes.");
    process.exit(1);
  }
  let argv;
  try {
    argv = process.argv.slice(2);
    networkFromArgs(argv);
    chainsFromArgs(argv);
  } catch {
    say("Usage: MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs [--chain nexa|bch] [--dry-run] [--mainnet]");
    process.exit(1);
  }
  if (argv.includes("--mainnet")) {
    say("Mainnet. This will create a real group and a real CashTokens category.");
  } else {
    say("Testnet / chipnet. Pass --mainnet to allow mainnet. The key is not printed.");
  }
  const chains = chainsFromArgs(argv);
  const secrets = {};
  const missing = [];
  if (chains.includes("nexa") && !(process.env.NEXA_HOT_KEY && process.env.NEXA_HOT_KEY.trim().length >= 32)) missing.push("nexa");
  if (chains.includes("bch") && !(process.env.BCH_HOT_KEY && process.env.BCH_HOT_KEY.trim().length >= 32)) missing.push("bch");
  if (missing.length > 1 || (missing.length === 1 && !process.stdin.isTTY)) {
    say("Set the missing key in the environment (NEXA_HOT_KEY / BCH_HOT_KEY). Stdin is only used for one key, from a terminal.");
    process.exit(1);
  }
  if (chains.includes("nexa")) secrets.nexa = await readSecret("NEXA_HOT_KEY");
  if (chains.includes("bch")) secrets.bch = await readSecret("BCH_HOT_KEY");
  const { failed, lines } = await runSetup(argv, secrets);
  for (const key of Object.keys(secrets)) secrets[key] = "";
  for (const line of lines) process.stdout.write(line + "\n");
  process.exit(failed ? 1 : 0);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
