import Link from "next/link";
import { chains, getTx, tokensOn } from "@/lib/data";
import { formatAge, formatNumber, formatTokenAmount, shortId } from "@/lib/format";
import type { ChainId, TokenInfo } from "@/lib/types";

export function TokenIndex({ chainId }: { chainId: ChainId }) {
  const chain = chains[chainId];
  const list = tokensOn(chainId);
  return (
    <>
      <p className="eyebrow">Tokens · {chain.name}</p>
      <h1>{chainId === "nexa" ? "Group tokens" : "CashTokens"}</h1>
      <p className="lead">
        {chainId === "nexa"
          ? "Nexa carries tokens in the same transaction as the coin. A group id is the token’s identity."
          : "Bitcoin Cash carries tokens as CashTokens. A fungible token and an NFT use the same page, with the kind written out."}
      </p>
      <section className="sheet">
        <table className="ledger">
          <caption className="vh">{chain.name} tokens</caption>
          <thead>
            <tr>
              <th>Token</th>
              <th>Kind</th>
              <th className="r">Supply</th>
            </tr>
          </thead>
          <tbody>
            {list.map((token) => (
              <tr key={token.id}>
                <td data-label="Token">
                  <Link href={`/${chainId}/token/${token.id}`}>
                    <strong>{token.ticker}</strong>
                    <span className="muted"> · {token.name}</span>
                  </Link>
                </td>
                <td data-label="Kind">{token.kind}</td>
                <td data-label="Supply" className="r">
                  {formatNumber(token.supply)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

export function TokenView({ token }: { token: TokenInfo }) {
  const chain = chains[token.chain];
  return (
    <>
      <nav className="crumb" aria-label="Breadcrumb">
        <Link href={`/${token.chain}`}>{chain.name}</Link>
        <span aria-hidden="true"> · </span>
        <Link href={`/${token.chain}/tokens`}>Tokens</Link>
        <span aria-hidden="true"> · </span>
        <span>{token.ticker}</span>
      </nav>
      <p className="eyebrow">
        Token · {chain.name} · {token.kind}
      </p>
      <h1>{token.ticker}</h1>
      <p className="lead">{token.name}. {token.about}</p>
      <dl className="facts">
        <div>
          <dt>Supply</dt>
          <dd>{formatTokenAmount(token.supply, token.decimals, token.ticker)}</dd>
        </div>
        <div>
          <dt>Decimals</dt>
          <dd>{formatNumber(token.decimals)}</dd>
        </div>
        <div>
          <dt>Kind</dt>
          <dd>{token.kind}</dd>
        </div>
        <div>
          <dt>Chain</dt>
          <dd>
            <Link href={`/${token.chain}`}>{chain.name}</Link>
          </dd>
        </div>
      </dl>
      <section className="sheet" aria-labelledby="moves-h">
        <div className="sheethead">
          <h2 id="moves-h">Transfers in this sample</h2>
        </div>
        <table className="ledger">
          <caption className="vh">Sample transfers of {token.ticker}</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>When</th>
              <th className="r">Amount</th>
            </tr>
          </thead>
          <tbody>
            {token.txIds.map((id) => {
              const tx = getTx(id);
              if (!tx) return null;
              const move = [...tx.outputs, ...tx.inputs].find((side) => side.token?.tokenId === token.id);
              return (
                <tr key={id}>
                  <td data-label="Transaction">
                    <Link className="mono" href={`/${token.chain}/tx/${tx.id}`}>
                      {shortId(tx.hash, 16, 8)}
                    </Link>
                  </td>
                  <td data-label="When" className="muted">
                    {formatAge(tx.time)}
                  </td>
                  <td data-label="Amount" className="r">
                    {move?.token ? formatTokenAmount(move.token.amount, token.decimals, token.ticker) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </>
  );
}
