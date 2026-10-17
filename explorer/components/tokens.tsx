"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { chains } from "@/lib/chains";
import { formatNumber, shortId } from "@/lib/format";
import { blockHref, tokenHref, txHref } from "@/lib/routes";
import type { ChainId, TokenModel } from "@/lib/types";

export function TokenLookup({ chainId }: { chainId: ChainId }) {
  const chain = chains[chainId];
  const router = useRouter();
  return (
    <>
      <p className="eyebrow">Tokens · {chain.name}</p>
      <h1>{chainId === "nexa" ? "Group tokens" : "CashTokens"}</h1>
      <p className="lead">
        {chainId === "nexa"
          ? "Nexa carries tokens in the same transaction as the coin. Paste a group id to ask the server for its genesis record. There is no list of every token."
          : "Bitcoin Cash carries tokens as CashTokens. Paste a category id to ask the server for its genesis record. There is no list of every token."}
      </p>
      <form
        className="search"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const id = String(data.get("id") ?? "").trim();
          if (!id) return;
          router.push(tokenHref(chainId, id));
        }}
      >
        <label className="vh" htmlFor="token-id">
          Token id
        </label>
        <input id="token-id" name="id" placeholder="Token id" autoComplete="off" />
        <button type="submit">Look up</button>
      </form>
    </>
  );
}

export function TokenView({ token }: { token: TokenModel }) {
  const chain = chains[token.chain];
  return (
    <>
      <nav className="crumb" aria-label="Breadcrumb">
        <Link href={`/${token.chain}`}>{chain.name}</Link>
        <span aria-hidden="true"> · </span>
        <Link href={`/${token.chain}/tokens`}>Tokens</Link>
        <span aria-hidden="true"> · </span>
        <span>{token.ticker ?? "Token"}</span>
      </nav>
      <p className="eyebrow">Token · {chain.name}</p>
      <h1 className="token-title">
        {token.icon ? <img src={token.icon} alt="" width={48} height={48} /> : null}
        {token.name && token.ticker ? `${token.name} (${token.ticker})` : (token.ticker ?? token.name ?? shortId(token.id, 12, 6))}
      </h1>
      <p className="lead">
        {token.name ?? "The server returned a genesis record without a name."}
        {token.documentUrl ? (
          <>
            {" "}
            <a href={token.documentUrl}>Document</a>.
          </>
        ) : null}
      </p>
      <div className="hashrow">
        <code>{token.id}</code>
      </div>
      <dl className="facts">
        <div>
          <dt>Name</dt>
          <dd>{token.name ?? "Not reported"}</dd>
        </div>
        <div>
          <dt>Ticker</dt>
          <dd>{token.ticker ?? "Not reported"}</dd>
        </div>
        <div>
          <dt>Decimals</dt>
          <dd>{token.decimals == null ? "Not reported" : formatNumber(token.decimals)}</dd>
        </div>
        <div>
          <dt>Genesis</dt>
          <dd>
            {token.txid ? <Link href={txHref(token.chain, token.txid)}>{shortId(token.txid, 12, 6)}</Link> : "Not reported"}
            {token.height != null ? (
              <>
                {" · "}
                <Link href={blockHref(token.chain, token.height)}>{formatNumber(token.height)}</Link>
              </>
            ) : null}
          </dd>
        </div>
      </dl>
    </>
  );
}
