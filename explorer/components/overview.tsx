"use client";

import Link from "next/link";
import { chains } from "@/lib/chains";
import { loadOverview } from "@/lib/load";
import { formatBytes, formatChange, formatNumber } from "@/lib/format";
import { blockHref } from "@/lib/routes";
import type { ChainId, OverviewModel } from "@/lib/types";
import { Age } from "./age";
import { FeeRate, UnitPrice, UsdPrice, useChange, usePriceStatus, useUnitPrice } from "./money";
import { usePrefs } from "./prefs";
import { ServerLine } from "./server-line";
import { LoadingState, MissingItem, Unreachable } from "./states";
import { useChainLoad } from "./use-chain";

function PriceStat({ chainId }: { chainId: ChainId }) {
  const { fiat } = usePrefs();
  const status = usePriceStatus();
  const price = useUnitPrice(chainId, fiat);
  const changeValue = useChange(chainId, fiat);
  const change = formatChange(changeValue);
  return (
    <div className="stat">
      <span className="eyebrow">Price</span>
      <b className="num">{status === "loading" ? "…" : price == null ? "Unavailable" : <UnitPrice chainId={chainId} />}</b>
      <span className="sub">
        {status === "loading" ? (
          "Asking for a quote"
        ) : price == null ? (
          "No fiat quote, so amounts stay in coins"
        ) : (
          <>
            <UsdPrice chainId={chainId} />
            {change ? (
              <>
                {" "}
                · 24h <span className={changeValue! < 0 ? "down" : "up"}>{change}</span>
              </>
            ) : (
              <span> · no 24-hour quote</span>
            )}
          </>
        )}
      </span>
    </div>
  );
}

function OverviewView({ chainId, model }: { chainId: ChainId; model: OverviewModel }) {
  const chain = chains[chainId];
  const tip = model.blocks[0];
  const mempoolLabel =
    model.mempoolCount != null ? formatNumber(model.mempoolCount) : model.mempoolVsize > 0 ? formatBytes(model.mempoolVsize) : "0";
  const mempoolSub =
    model.mempoolCount != null
      ? model.mempoolCount === 1
        ? "1 transaction waiting"
        : `${formatNumber(model.mempoolCount)} waiting`
      : model.mempoolVsize > 0
        ? "Waiting, measured by fee rate"
        : "Nothing waiting";

  return (
    <>
      <p className="eyebrow">
        <span className={`pip ${chainId}`} aria-hidden="true" />
        {chain.name} · {chain.target} blocks
      </p>
      <h1>{chain.name}</h1>
      <p className="lead">{chain.about}</p>
      <ServerLine label={model.serverLabel} version={model.serverVersion} fallback={model.fallback} apiHref={chain.apiHref} />
      {tip ? (
        <p className="tries">
          Open block <Link href={blockHref(chainId, tip.height)}>{formatNumber(tip.height)}</Link>
          {" or the "}
          <Link href={`/${chainId}/mempool`}>fee table</Link>. Press <kbd>/</kbd> to search.
        </p>
      ) : null}

      <section className="stats" aria-label="Chain summary">
        <Link className="stat" href={tip ? blockHref(chainId, tip.height) : `/${chainId}`}>
          <span className="eyebrow">Latest block</span>
          <b className="num">{tip ? formatNumber(tip.height) : "—"}</b>
          <span className="sub">{tip ? <Age iso={tip.time} /> : "No header yet"}</span>
        </Link>
        <Link className="stat" href={`/${chainId}/mempool`}>
          <span className="eyebrow">Mempool</span>
          <b className="num">{mempoolLabel}</b>
          <span className="sub">{mempoolSub}</span>
        </Link>
        <PriceStat chainId={chainId} />
        <div className="stat">
          <span className="eyebrow">Difficulty</span>
          <b className="num">{tip?.difficulty ?? "—"}</b>
          <span className="sub">{tip ? `Bits ${tip.bits}` : "From the latest header"}</span>
        </div>
      </section>

      <div className="grid2">
        <section className="sheet" aria-labelledby="blocks-h">
          <div className="sheethead">
            <h2 id="blocks-h">Latest blocks</h2>
          </div>
          <table className="ledger">
            <caption className="vh">Latest {chain.name} blocks</caption>
            <thead>
              <tr>
                <th>Height</th>
                <th>When</th>
                <th className="r">Txns</th>
                <th className="r">Size</th>
              </tr>
            </thead>
            <tbody>
              {model.blocks.map((block) => (
                <tr key={block.height}>
                  <td data-label="Height">
                    <Link className="blocklink" href={blockHref(chainId, block.height)}>
                      {formatNumber(block.height)}
                    </Link>
                  </td>
                  <td data-label="When" className="muted">
                    <Age iso={block.time} />
                  </td>
                  <td data-label="Transactions" className="r">
                    {block.txCount == null ? "—" : formatNumber(block.txCount)}
                  </td>
                  <td data-label="Size" className="r">
                    {block.size == null ? "—" : formatBytes(block.size)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="sheet" aria-labelledby="fees-h">
          <div className="sheethead">
            <h2 id="fees-h">Fees</h2>
            <Link href={`/${chainId}/mempool`}>Mempool</Link>
          </div>
          {model.fees.length === 0 ? (
            <p className="muted" style={{ padding: "8px 10px 16px" }}>
              This server did not return a fee estimate.
            </p>
          ) : (
            <table className="ledger">
              <caption className="vh">{chain.name} fee estimates</caption>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Fee rate</th>
                  <th className="r">Size</th>
                </tr>
              </thead>
              <tbody>
                {model.fees.map((row, index) => (
                  <tr key={`${row.label}-${row.satPerByte}-${index}`}>
                    <td data-label="When">{row.label}</td>
                    <td data-label="Fee rate">
                      <FeeRate satPerByte={row.satPerByte} chainId={chainId} />
                    </td>
                    <td data-label="Size" className="r">
                      {row.vsize == null ? "—" : formatBytes(row.vsize)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="section" aria-labelledby="tokens-h">
        <h2 id="tokens-h">{chainId === "nexa" ? "Group tokens" : "CashTokens"}</h2>
        <p className="lead">
          {chainId === "nexa"
            ? "A token shows up on the transaction or address that holds it. There is no directory of every group in the Electrum replies."
            : "A CashToken shows up on the transaction or address that holds it. There is no directory of every token in the Electrum replies."}{" "}
          <Link href={`/${chainId}/tokens`}>Look up a token id</Link>.
        </p>
      </section>
    </>
  );
}

export function Overview({ chainId }: { chainId: ChainId }) {
  const { state, retry } = useChainLoad(chainId, "overview", (session) => loadOverview(session));
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <OverviewView chainId={chainId} model={state.data} />;
}
