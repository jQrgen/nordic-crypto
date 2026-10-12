"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { chains } from "@/lib/chains";
import { loadAddress, loadBlock, loadFeeTable, loadTransaction, loadToken } from "@/lib/load";
import { formatBytes, formatNumber } from "@/lib/format";
import { addressHref, txHref } from "@/lib/routes";
import type { ChainId } from "@/lib/types";
import { AddressView, BlockView, TxView } from "./ledger";
import { FeeRate } from "./money";
import { ServerLine } from "./server-line";
import { LoadingState, MissingItem, Unreachable } from "./states";
import { TokenLookup, TokenView } from "./tokens";
import { useChainLoad } from "./use-chain";

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
  const heightRaw = useSearchParams().get("height");
  const height = heightRaw == null || heightRaw === "" ? null : Number(heightRaw);
  if (heightRaw && !Number.isInteger(height)) return <MissingItem chainId={chainId} message="That is not a block height." />;
  return <BlockLoader chainId={chainId} height={height} />;
}

function BlockLoader({ chainId, height }: { chainId: ChainId; height: number | null }) {
  const { state, retry } = useChainLoad(chainId, height == null ? "tip" : String(height), (session) => loadBlock(session, height ?? session.tipHeight));
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
  const { state, retry } = useChainLoad(chainId, txid, (session) => loadTransaction(session, txid));
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
  const { state, retry } = useChainLoad(chainId, address, (session) => loadAddress(session, address));
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  return <AddressView address={state.data} />;
}

export function MempoolScreen({ chainId }: { chainId: ChainId }) {
  const { state, retry } = useChainLoad(chainId, "mempool", async (session) => ({ session, fees: await loadFeeTable(session) }));
  if (state.status === "loading") return <LoadingState chainId={chainId} />;
  if (state.status === "unreachable") return <Unreachable chainId={chainId} servers={state.servers} onRetry={retry} />;
  if (state.status === "missing") return <MissingItem chainId={chainId} message={state.message} />;
  const { fees, session } = state.data;
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
              ? "Transactions known to the server and not in a block yet."
              : "Bitcoin Cash servers report the mempool as a fee histogram, not a list of transactions. The size below is the virtual size waiting at each rate."}
          </p>
        </>
      )}
      <ServerLine label={session.server.label} version={session.version} fallback={!session.server.primary} apiHref={chain.apiHref} />
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
