import Link from "next/link";
import { chains, getToken, latestBlocks, mempool, recentTxs, tokensOn } from "@/lib/data";
import { formatAge, formatBytes, formatChange, formatCoin, formatCompact, formatNumber, formatTokenAmount, shortId } from "@/lib/format";
import type { ChainId } from "@/lib/types";
import { UnitPrice, UsdPrice } from "./money";

export function Overview({
  chainId,
  syncing,
}: {
  chainId: ChainId;
  syncing?: { have: number; network: number; behind: string };
}) {
  const chain = chains[chainId];
  const blocks = latestBlocks(chainId);
  const txs = recentTxs(chainId);
  const waiting = mempool(chainId);
  const change = formatChange(chain.change24h);
  const shownHeight = syncing ? syncing.have : chain.height;

  return (
    <>
      {syncing ? (
        <div className="banner" role="status">
          <strong>{chain.name} is still catching up.</strong>
          <p>
            The server has block {formatNumber(syncing.have)}. The network tip is {formatNumber(syncing.network)}, {syncing.behind} ahead. Figures below are the blocks we already have. Nexa and the news site are unaffected.
          </p>
        </div>
      ) : null}
      <p className="eyebrow">
        <span className={`pip ${chainId}`} aria-hidden="true" />
        {chain.name} · {chain.target} blocks
      </p>
      <h1>{chain.name}</h1>
      <p className="lead">{chain.about}</p>
      <p className="serverline">
        Read from {chain.serverName} · <a href={chain.apiHref}>API status</a>
      </p>
      <p className="tries">
        Try{" "}
        <Link href={`/${chainId}/block/${blocks[0]?.height ?? chain.height}`}>{formatNumber(blocks[0]?.height ?? chain.height)}</Link>
        {tokensOn(chainId)[0] ? (
          <>
            , <Link href={`/${chainId}/token/${tokensOn(chainId)[0].id}`}>{tokensOn(chainId)[0].ticker}</Link>
          </>
        ) : null}{" "}
        or a name such as <Link href={`/search?chain=${chainId}&q=Sigrid`}>Sigrid</Link>. Press <kbd>/</kbd> to search.
      </p>

      <section className="stats" aria-label="Chain summary">
        <Link className="stat" href={`/${chainId}/block/${shownHeight}`}>
          <span className="eyebrow">Latest block</span>
          <b className="num">{formatNumber(shownHeight)}</b>
          <span className="sub">{syncing ? `${formatNumber(chain.height - syncing.have)} blocks behind` : formatAge(blocks[0]?.time ?? null)}</span>
        </Link>
        <Link className="stat" href={syncing ? `/${chainId}/mempool` : `/${chainId}/mempool`}>
          <span className="eyebrow">Mempool</span>
          <b className="num">{formatNumber(syncing ? 0 : chain.mempoolCount)}</b>
          <span className="sub">{syncing ? "Hidden while we catch up" : waiting.length === 1 ? "1 transaction waiting" : `${formatNumber(chain.mempoolCount)} waiting`}</span>
        </Link>
        <div className="stat">
          <span className="eyebrow">Price</span>
          <b className="num">
            <UnitPrice chainId={chainId} />
          </b>
          <span className="sub">
            <UsdPrice chainId={chainId} />
            {change ? (
              <>
                {" "}
                · 24h <span className={chain.change24h! < 0 ? "down" : "up"}>{change}</span>
              </>
            ) : (
              <span> · no 24-hour quote</span>
            )}
          </span>
        </div>
        <div className="stat">
          <span className="eyebrow">Circulating</span>
          <b className="num">{formatCompact(chain.supply)}</b>
          <span className="sub">{formatNumber(chain.supply)} {chain.ticker}</span>
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
                <th>Miner</th>
                <th className="r">Txns</th>
                <th className="r">Size</th>
              </tr>
            </thead>
            <tbody>
              {blocks.map((block) => (
                <tr key={block.height}>
                  <td data-label="Height">
                    <Link className="blocklink" href={`/${chainId}/block/${block.height}`}>
                      {formatNumber(block.height)}
                    </Link>
                  </td>
                  <td data-label="When" className="muted">
                    {formatAge(block.time)}
                  </td>
                  <td data-label="Miner">{block.minerAddressId ? <Link href={`/${chainId}/address/${block.minerAddressId}`}>{block.miner}</Link> : block.miner}</td>
                  <td data-label="Transactions" className="r">
                    {formatNumber(block.txIds.length)}
                  </td>
                  <td data-label="Size" className="r">
                    {formatBytes(block.size)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="sheet" aria-labelledby="txs-h">
          <div className="sheethead">
            <h2 id="txs-h">Latest transactions</h2>
            <Link href={`/${chainId}/mempool`}>Mempool</Link>
          </div>
          <table className="ledger">
            <caption className="vh">Latest {chain.name} transactions, excluding coinbase</caption>
            <thead>
              <tr>
                <th>Transaction</th>
                <th>When</th>
                <th className="r">Amount</th>
              </tr>
            </thead>
            <tbody>
              {txs.map((tx) => {
                const moved = tx.outputs.find((o) => o.token) ?? tx.outputs[0];
                return (
                  <tr key={tx.id}>
                    <td data-label="Transaction">
                      <Link className="mono" href={`/${chainId}/tx/${tx.id}`}>
                        {shortId(tx.hash, 10, 6)}
                      </Link>
                    </td>
                    <td data-label="When" className="muted">
                      {formatAge(tx.time)}
                    </td>
                    <td data-label="Amount" className="r">
                      {moved?.token ? (
                        <Link href={`/${chainId}/token/${moved.token.tokenId}`}>
                          {formatTokenAmount(moved.token.amount, getToken(moved.token.tokenId)?.decimals ?? 0, getToken(moved.token.tokenId)?.ticker ?? "")}
                        </Link>
                      ) : (
                        formatCoin(tx.outputs[0]?.amount ?? 0, chain)
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section" aria-labelledby="tokens-h">
        <div className="sheethead" style={{ paddingLeft: 0 }}>
          <h2 id="tokens-h">{chainId === "nexa" ? "Group tokens" : "CashTokens"}</h2>
          <Link href={`/${chainId}/tokens`}>All tokens</Link>
        </div>
        <div className="tokengrid">
          {tokensOn(chainId).map((token) => (
            <Link className="token" key={token.id} href={`/${chainId}/token/${token.id}`}>
              <span className="eyebrow">{token.name}</span>
              <span className="ticker">{token.ticker}</span>
              <span className="kind">
                {formatNumber(token.supply)} · {token.kind}
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="net-h">
        <h2 id="net-h" className="vh">
          Network
        </h2>
        <dl className="network">
          <div>
            <dt>Hashrate</dt>
            <dd>{chain.hashrate}</dd>
          </div>
          <div>
            <dt>Difficulty</dt>
            <dd className="num">{chain.difficulty}</dd>
          </div>
          <div>
            <dt>Chain size</dt>
            <dd>{chain.size}</dd>
          </div>
          <div>
            <dt>Transactions</dt>
            <dd className="num">{chain.txCount}</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
