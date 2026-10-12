import Link from "next/link";
import { chains, defaultChain, mempool } from "@/lib/data";
import { formatCoin, formatNumber, shortId } from "@/lib/format";
import type { ChainId, SearchHit } from "@/lib/types";
import { Frame } from "./frame";

export function Results({ q, hits }: { q: string; hits: SearchHit[] }) {
  return (
    <>
      <p className="eyebrow">Search</p>
      <h1>
        {hits.length === 1 ? "1 match" : `${hits.length} matches`} for “{q}”
      </h1>
      <p className="lead">The chain you were on is listed first. Open a row to see it.</p>
      <div className="results">
        {hits.map((hit) => (
          <Link className="result" key={hit.href} href={hit.href}>
            <span className="kind">
              <span className={`pip ${hit.chain}`} aria-hidden="true" />
              {hit.kind} · {chains[hit.chain].name}
            </span>
            <span>
              <strong>{hit.title}</strong>
              <span className="muted" style={{ display: "block" }}>
                {hit.detail}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </>
  );
}

export function Missing({ q, chainId, page = false }: { q: string; chainId: ChainId; page?: boolean }) {
  const chain = chains[chainId];
  const title = page ? "This page is not on the explorer." : q ? `Nothing matches “${q}”` : "Look something up";
  return (
    <>
      <p className="eyebrow">Search</p>
      <h1>{title}</h1>
      <p className="lead">
        {page
          ? "The address in the bar does not point at a block, a transaction, an address or a token."
          : q
            ? `Checked ${chain.name} first, then the other chain. No block, transaction, address or token matched.`
            : "Use the field above for a block height, a transaction, an address or a token ticker."}
      </p>
      <p className="tries">
        Try a height such as <Link href={`/${chainId}/block/${chain.height}`}>{formatNumber(chain.height)}</Link>, a token such as{" "}
        <Link href="/nexa/token/agnar">AGNAR</Link>, or a name such as <Link href={`/search?q=Sigrid&chain=${chainId}`}>Sigrid</Link>.
      </p>
    </>
  );
}

export function Fault() {
  return (
    <>
      <p className="eyebrow">Something went wrong</p>
      <h1>The explorer could not draw this page.</h1>
      <p className="lead">The chain is still there. This is a fault in drawing the page, not a missing transaction. Trying again usually clears it.</p>
      <p>
        <Link className="btn" href={`/${defaultChain}`}>
          Back to {chains[defaultChain].name}
        </Link>
      </p>
    </>
  );
}

export function LoadingState() {
  return (
    <>
      <p className="eyebrow">{chains[defaultChain].name}</p>
      <span className="skel" style={{ height: 52, width: "42%", margin: "8px 0 14px" }} />
      <span className="skel" style={{ height: 18, width: "70%", marginBottom: 8 }} />
      <span className="skel" style={{ height: 18, width: "54%", marginBottom: 22 }} />
      <div className="stats" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div className="stat sk-card" key={i}>
            <span className="skel" style={{ height: 12, width: "46%" }} />
            <span className="skel" style={{ height: 32, width: "70%", marginTop: 12 }} />
            <span className="skel" style={{ height: 12, width: "50%", marginTop: 12 }} />
          </div>
        ))}
      </div>
      <p className="muted">Loading the chain. Hashes and balances appear when the server answers.</p>
    </>
  );
}

export function EmptyMempool({ chainId }: { chainId: ChainId }) {
  const chain = chains[chainId];
  return (
    <>
      <p className="eyebrow">Mempool · {chain.name}</p>
      <h1>Nothing is waiting</h1>
      <p className="lead">The next block will be only the miner’s reward, unless a transaction arrives before it is found.</p>
      <p>
        <Link className="btn" href={`/${chainId}`}>
          Back to the overview
        </Link>
      </p>
    </>
  );
}

export function MempoolView({ chainId, empty = false }: { chainId: ChainId; empty?: boolean }) {
  const chain = chains[chainId];
  const rows = empty ? [] : mempool(chainId);
  if (rows.length === 0) return <EmptyMempool chainId={chainId} />;
  const shown = rows.length;
  const rest = Math.max(0, chain.mempoolCount - shown);
  return (
    <>
      <p className="eyebrow">Mempool · {chain.name}</p>
      <h1 className="num">{formatNumber(chain.mempoolCount)} waiting</h1>
      <p className="lead">
        {rest > 0
          ? `Showing ${formatNumber(shown)} transactions, highest fee rate first. ${formatNumber(rest)} more are also waiting.`
          : "These transactions are known to the server and are not in a block yet."}
      </p>
      <section className="sheet">
        <table className="ledger">
          <caption className="vh">{chain.name} mempool</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Fee rate</th>
              <th className="r">Fee</th>
              <th className="r">Size</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .slice()
              .sort((a, b) => b.fee - a.fee)
              .map((tx) => (
                <tr key={tx.id}>
                  <td data-label="Transaction">
                    <Link className="mono" href={`/${chainId}/tx/${tx.id}`}>
                      {shortId(tx.hash, 16, 8)}
                    </Link>
                  </td>
                  <td data-label="Fee rate">{tx.feeRate}</td>
                  <td data-label="Fee" className="r">
                    {formatCoin(tx.fee, chain)}
                  </td>
                  <td data-label="Size" className="r">
                    {formatNumber(tx.size)} B
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

export function StatePage({ chain, children }: { chain?: ChainId; children: React.ReactNode }) {
  return <Frame chain={chain}>{children}</Frame>;
}
