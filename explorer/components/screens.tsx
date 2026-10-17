"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { chains } from "@/lib/chains";
import { loadAddress, loadBlock, loadFeeTable, loadTransaction, loadToken } from "@/lib/load";
import { loadBtcAddress, loadBtcBlock, loadBtcFees, loadBtcTx, MEMPOOL_LABEL } from "@/lib/mempool-space";
import { formatBytes, formatNumber } from "@/lib/format";
import { addressHref, txHref } from "@/lib/routes";
import type { ChainId } from "@/lib/types";
import { AddressView, BlockView, TxView } from "./ledger";
import { FeeRate } from "./money";
import { ServerLine } from "./server-line";
import { LoadingState, MissingItem, Unreachable } from "./states";
import { TokenLookup, TokenView } from "./tokens";
import { useChainLoad, useSourceLoad } from "./use-chain";

function LookupForm({ chainId, kind, name, placeholder }: { chainId: ChainId; kind: "tx" | "address"; name: string; placeholder: string }) {
  const router = useRouter();
  return (
    <>
      <p className="eyebrow">{chains[chainId].name}</p>
      <h1>{kind === "tx" ? "Look up a transaction" : "Look up an address"}</h1>
      <p className="lead">{placeholder}</p>
      <form
        className="search"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const value = String(data.get(name) ?? "").trim();
          if (!value) return;
          router.push(kind === "tx" ? txHref(chainId, value) : addressHref(chainId, value));
        }}
      >
        <label className="vh" htmlFor={name}>
          {placeholder}
        </label>
        <input id={name} name={name} placeholder={placeholder} autoComplete="off" />
        <button type="submit">Look up</button>
      </form>
    </>
  );
}

export function BlockScreen({ chainId }: { chainId: ChainId }) {
  const params = useSearchParams();
  const heightRaw = params.get("height");
  const hashRaw = (params.get("hash") ?? "").trim();
  const hash = hashRaw || (heightRaw && /^[0-9a-f]{64}$/i.test(heightRaw.trim()) ? heightRaw.trim() : "");
  if (hash) {
    if (chains[chainId].backend !== "mempool-space") return <MissingItem chainId={chainId} message="Look up a block on this chain by its height." />;
    return <BlockLoader chainId={chainId} height={null} hash={hash} />;
  }
  const height = heightRaw == null || heightRaw === "" ? null : Number(heightRaw);
  if (heightRaw && !Number.isInteger(height)) return <MissingItem chainId={chainId} message="That is not a block height." />;
  return <BlockLoader chainId={chainId} height={height} />;
}

function BlockLoader({ chainId, height, hash }: { chainId: ChainId; height: number | null; hash?: string }) {
  const { state, retry } = useSourceLoad(chainId, hash ?? (height == null ? "tip" : String(height)), {
    electrum: (session) => loadBlock(session, height ?? session.tipHeight),
    mempool: () => loadBtcBlock(hash ? { hash } : { height }),
  });
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <BlockView block={state.data} />;
}

export function TxScreen({ chainId }: { chainId: ChainId }) {
  const txid = (useSearchParams().get("txid") ?? "").trim();
  if (!txid) return <LookupForm chainId={chainId} kind="tx" name="txid" placeholder="Transaction id, 64 hex characters" />;
  return <TxLoader chainId={chainId} txid={txid} />;
}

function TxLoader({ chainId, txid }: { chainId: ChainId; txid: string }) {
  const { state, retry } = useSourceLoad(chainId, txid, { electrum: (session) => loadTransaction(session, txid), mempool: () => loadBtcTx(txid) });
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <TxView tx={state.data} />;
}

export function AddressScreen({ chainId }: { chainId: ChainId }) {
  const address = (useSearchParams().get("address") ?? "").trim();
  if (!address) return <LookupForm chainId={chainId} kind="address" name="address" placeholder="Paste an address" />;
  return <AddressLoader chainId={chainId} address={address} />;
}

function AddressLoader({ chainId, address }: { chainId: ChainId; address: string }) {
  const { state, retry } = useSourceLoad(chainId, address, { electrum: (session) => loadAddress(session, address), mempool: () => loadBtcAddress(address) });
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <AddressView address={state.data} />;
}

export function MempoolScreen({ chainId }: { chainId: ChainId }) {
  const { state, retry } = useSourceLoad(chainId, "mempool", {
    electrum: async (session) => ({ source: { label: session.server.label, version: session.version, fallback: !session.server.primary }, fees: await loadFeeTable(session) }),
    mempool: async () => ({ source: { label: MEMPOOL_LABEL, version: "REST API", fallback: false }, fees: await loadBtcFees() }),
  });
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  const { fees, source } = state.data;
  const chain = chains[chainId];
  const estimates = fees.rows.filter((row) => row.vsize == null);
  const histogram = fees.rows.filter((row) => row.vsize != null);
  const empty = (fees.count == null || fees.count === 0) && fees.vsize === 0;
  return (
    <>
      <p className="eyebrow">Mempool · {chain.name}</p>
      {empty ? (
        <>
          <h1>Nothing is waiting</h1>
          <p className="lead">The next block will be only the miner’s reward, unless a transaction arrives before it is found.</p>
        </>
      ) : (
        <>
          <h1 className="num">{fees.count != null ? `${formatNumber(fees.count)} waiting` : formatBytes(fees.vsize)}</h1>
          <p className="lead">
            {fees.count != null
              ? chain.backend === "mempool-space"
                ? "Transactions in the mempool.space mempool and not in a block yet. The histogram groups them by fee rate."
                : "Transactions known to the server and not in a block yet."
              : "Bitcoin Cash servers report the mempool as a fee histogram, not a list of transactions. The size below is the virtual size waiting at each rate."}
          </p>
        </>
      )}
      <ServerLine label={source.label} version={source.version} fallback={source.fallback} apiHref={chain.apiHref} apiLabel={chain.apiLabel} />
      {estimates.length > 0 ? (
        <section className="sheet" aria-labelledby="est-h">
          <div className="sheethead">
            <h2 id="est-h">Estimated fee</h2>
          </div>
          <table className="ledger">
            <caption className="vh">{chain.name} fee estimates</caption>
            <thead>
              <tr>
                <th>Target</th>
                <th>Fee rate</th>
              </tr>
            </thead>
            <tbody>
              {estimates.map((row) => (
                <tr key={row.label}>
                  <td data-label="Target">{row.label}</td>
                  <td data-label="Fee rate">
                    <FeeRate satPerByte={row.satPerByte} chainId={chainId} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
      {histogram.length > 0 ? (
        <section className="sheet" style={{ marginTop: 18 }} aria-labelledby="hist-h">
          <div className="sheethead">
            <h2 id="hist-h">Fee histogram</h2>
          </div>
          <table className="ledger">
            <caption className="vh">{chain.name} mempool fee histogram</caption>
            <thead>
              <tr>
                <th>Fee rate</th>
                <th className="r">Virtual size</th>
              </tr>
            </thead>
            <tbody>
              {histogram.map((row) => (
                <tr key={`${row.satPerByte}-${row.vsize}`}>
                  <td data-label="Fee rate">
                    <FeeRate satPerByte={row.satPerByte} chainId={chainId} />
                  </td>
                  <td data-label="Virtual size" className="r">
                    {formatBytes(row.vsize ?? 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : empty ? (
        <p>
          <Link className="btn" href={`/${chainId}`}>
            Back to the overview
          </Link>
        </p>
      ) : null}
    </>
  );
}

export function TokenScreen({ chainId, index = false }: { chainId: ChainId; index?: boolean }) {
  const id = (useSearchParams().get("id") ?? "").trim();
  if (index || !id) return <TokenLookup chainId={chainId} />;
  return <TokenLoader chainId={chainId} id={id} />;
}

function TokenLoader({ chainId, id }: { chainId: ChainId; id: string }) {
  const { state, retry } = useChainLoad(chainId, id, (session) => loadToken(session, id));
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <TokenView token={state.data} />;
}
