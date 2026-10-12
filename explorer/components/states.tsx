import Link from "next/link";
import { chains, defaultChain } from "@/lib/chains";
import type { ChainId, SearchHit } from "@/lib/types";
import { Frame } from "./frame";

export function Results({ q, hits }: { q: string; hits: SearchHit[] }) {
  return (
    <>
      <p className="eyebrow">Search</p>
      <h1>
        {hits.length === 1 ? "1 match" : `${hits.length} matches`} for “{q}”
      </h1>
      <p className="lead">Open a row to ask the chain for it.</p>
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
            ? `That is not a block height, a 64-character transaction id, or a ${chain.name} address.`
            : "Use the field above for a block height, a transaction id, or an address."}
      </p>
    </>
  );
}

export function MissingItem({ chainId, message }: { chainId: ChainId; message: string }) {
  return (
    <>
      <p className="eyebrow">{chains[chainId].name}</p>
      <h1>Nothing there</h1>
      <p className="lead">{message}</p>
      <p>
        <Link className="btn" href={`/${chainId}`}>
          Back to the overview
        </Link>
      </p>
    </>
  );
}

export function Unreachable({ chainId, servers, onRetry }: { chainId: ChainId; servers: string[]; onRetry?: () => void }) {
  const chain = chains[chainId];
  return (
    <>
      <p className="eyebrow">{chain.name}</p>
      <h1>Could not reach chain servers</h1>
      <p className="lead">None of the {chain.name} servers answered, so this page has no figures in their place.</p>
      <ul>
        {servers.map((server) => (
          <li key={server} className="mono">
            {server}
          </li>
        ))}
      </ul>
      {onRetry ? (
        <p>
          <button className="btn" type="button" onClick={onRetry}>
            Try again
          </button>
        </p>
      ) : null}
    </>
  );
}

export function Fault() {
  return (
    <>
      <p className="eyebrow">Something went wrong</p>
      <h1>The explorer could not draw this page.</h1>
      <p className="lead">Trying again usually clears it. This is a fault in drawing the page.</p>
      <p>
        <Link className="btn" href={`/${defaultChain}`}>
          Back to {chains[defaultChain].name}
        </Link>
      </p>
    </>
  );
}

export function LoadingState({ chainId = defaultChain }: { chainId?: ChainId }) {
  const chain = chains[chainId];
  return (
    <>
      <p className="eyebrow">{chain.name}</p>
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
      <p className="muted">Loading the chain. Figures appear when a server answers.</p>
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

export function StatePage({ chain, children }: { chain?: ChainId; children: React.ReactNode }) {
  return <Frame chain={chain}>{children}</Frame>;
}
