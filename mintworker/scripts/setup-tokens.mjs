// Local one-off, for a machine that already has the hot key. The deployed
// Worker keeps the key as a secret, so the operator path is
// POST /api/admin/setup-tokens. This script refuses mainnet.
//
//   MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs --chain nexa
//
// It reads NEXA_HOT_KEY / BCH_HOT_KEY from the environment, or asks once on a
// terminal with echo off. It does not write a file and it does not print the key.

import { spawnSync } from "node:child_process";
import readline from "node:readline";
import { pathToFileURL } from "node:url";
import { assertOperatorNetwork, chainsFromArgs, networkFromArgs, setupChain } from "../src/setup.js";

export { assertOperatorNetwork, chainsFromArgs, networkFromArgs };

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

export async function runSetup(argv, secrets) {
  const network = assertOperatorNetwork(argv, process.env.MINT_SETUP_I_AM_THE_OPERATOR);
  const chains = chainsFromArgs(argv);
  const lines = ["network=" + network];
  let failed = false;
  for (const chain of chains) {
    const env = {
      NC_EVENT_NFT: "1",
      MINT_NETWORK: "testnet",
      NEXA_HOT_KEY: secrets.nexa,
      BCH_HOT_KEY: secrets.bch,
      NEXA_HOT_ADDRESS: process.env.NEXA_HOT_ADDRESS,
      BCH_HOT_ADDRESS: process.env.BCH_HOT_ADDRESS,
    };
    const result = await setupChain(env, chain, { record: false });
    if (!result.ok) {
      say(chain + ": " + (result.reason || "failed"));
      if (result.reason === "unfunded") say(chain + ": have " + result.have_sats + " sats, need " + result.need_sats + " (" + result.detail + ")");
      failed = true;
      continue;
    }
    if (chain === "nexa") {
      lines.push("NEXA_PARENT_GROUP=" + result.public_id);
      lines.push("nexa_txid=" + result.txid);
    } else {
      lines.push("BCH_CATEGORY=" + result.public_id);
      lines.push("bch_txid=" + result.txid);
      if (result.prep_txid) lines.push("bch_prep_txid=" + result.prep_txid);
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
    assertOperatorNetwork(argv, "yes");
    chainsFromArgs(argv);
  } catch (e) {
    if (e && e.code === "mainnet_blocked") {
      say("Refusing mainnet. This script and the admin endpoint stay on testnet.");
      process.exit(1);
    }
    say("Usage: MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs [--chain nexa|bch]");
    process.exit(1);
  }
  say("Testnet / chipnet. The key is not printed.");
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
