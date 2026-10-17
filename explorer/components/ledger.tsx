import Link from "next/link";
import { chains } from "@/lib/chains";
import { formatBytes, formatCoin, formatNumber, formatRawAmount, formatWhen, shortId } from "@/lib/format";
import { addressHref, blockHref, tokenHref, txHref } from "@/lib/routes";
import type { AddressModel, BlockModel, ChainId, TxModel, TxSide } from "@/lib/types";
import { Age } from "./age";
import { CopyButton } from "./copy-button";
import { CoinWithFiat, FeeRate, FiatOnly } from "./money";

function Crumb({ chainId, current }: { chainId: ChainId; current: string }) {
  return (
    <nav className="crumb" aria-label="Breadcrumb">
      <Link href={`/${chainId}`}>{chains[chainId].name}</Link>
      <span aria-hidden="true"> · </span>
      <span>{current}</span>
    </nav>
  );
}

function Party({ chainId, side }: { chainId: ChainId; side: TxSide }) {
  if (side.address) return <Link href={addressHref(chainId, side.address)}>{shortId(side.address, 18, 6)}</Link>;
  return <span>{side.label ?? "Unknown"}</span>;
}

function TokenBit({ chainId, side }: { chainId: ChainId; side: TxSide }) {
  if (!side.token) return null;
  return (
    <Link className="tokenline" href={tokenHref(chainId, side.token.id)}>
      {formatRawAmount(side.token.amount)} {shortId(side.token.id, 8, 4)}
    </Link>
  );
}

export function BlockView({ block }: { block: BlockModel }) {
  const chain = chains[block.chain];
  const prev = block.height > 0 ? block.height - 1 : null;
  const next = block.confirmations > 1 ? block.height + 1 : null;
  const listed = block.txIds.length;
  const hidden = block.txCount != null ? Math.max(0, block.txCount - listed) : null;
  return (
    <>
      <Crumb chainId={block.chain} current={`Block ${formatNumber(block.height)}`} />
      <p className="eyebrow">Block · {chain.name}</p>
      <h1 className="num">#{formatNumber(block.height)}</h1>
      <p className="lead">
        <Age iso={block.time} />. {block.time ? formatWhen(block.time) : null}.
      </p>
      <div className="hashrow">
        <code>{block.hash}</code>
        <CopyButton value={block.hash} />
      </div>
      <div className="pager">
        {prev != null ? <Link href={blockHref(block.chain, prev)}>← {formatNumber(prev)}</Link> : <span />}
        {next != null ? <Link href={blockHref(block.chain, next)}>{formatNumber(next)} →</Link> : <span>Latest block</span>}
      </div>
      <dl className="facts">
        <div>
          <dt>Miner</dt>
          <dd>
            {block.minerAddress ? (
              <Link href={addressHref(block.chain, block.minerAddress)}>{block.miner ?? shortId(block.minerAddress)}</Link>
            ) : (
              (block.miner ?? "Not in the coinbase text")
            )}
          </dd>
        </div>
        <div>
          <dt>Transactions</dt>
          <dd>{block.txCount == null ? "Not reported" : formatNumber(block.txCount)}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{block.size == null ? "Not reported" : formatBytes(block.size)}</dd>
        </div>
        <div>
          <dt>Reward</dt>
          <dd>{block.reward == null ? "Not reported" : <CoinWithFiat coin={block.reward} chainId={block.chain} />}</dd>
        </div>
        <div>
          <dt>Difficulty</dt>
          <dd className="num">{block.difficulty}</dd>
        </div>
        <div>
          <dt>Bits</dt>
          <dd className="mono">{block.bits}</dd>
        </div>
        <div>
          <dt>Confirmations</dt>
          <dd>{formatNumber(block.confirmations)}</dd>
        </div>
        <div>
          <dt>Previous</dt>
          <dd className="mono">
            {prev != null ? <Link href={blockHref(block.chain, prev)}>{shortId(block.previous, 14, 8)}</Link> : shortId(block.previous, 14, 8)}
          </dd>
        </div>
        <div>
          <dt>Merkle root</dt>
          <dd className="mono">{shortId(block.merkle, 14, 8)}</dd>
        </div>
      </dl>
      <section className="sheet" aria-labelledby="btx-h">
        <div className="sheethead">
          <h2 id="btx-h">{block.txCount == null ? "Coinbase" : block.txCount === 1 ? "1 transaction" : `${formatNumber(block.txCount)} transactions`}</h2>
        </div>
        {hidden != null && hidden > 0 ? (
          <p className="muted" style={{ padding: "0 10px 8px" }}>
            Showing {formatNumber(listed)} of {formatNumber(block.txCount!)}. Look up any other transaction by its id.
          </p>
        ) : null}
        {block.txCount == null ? (
          <p className="muted" style={{ padding: "0 10px 12px" }}>
            This server does not list every transaction in a block. The coinbase is below. Look up any other transaction by its id.
          </p>
        ) : null}
        <table className="ledger">
          <caption className="vh">Transactions in block {formatNumber(block.height)}</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Kind</th>
            </tr>
          </thead>
          <tbody>
            {block.txIds.map((id, index) => (
              <tr key={id}>
                <td data-label="Transaction">
                  <Link className="mono" href={txHref(block.chain, id)}>
                    {shortId(id, 16, 8)}
                  </Link>
                </td>
                <td data-label="Kind">{index === 0 ? "Coinbase" : "Transaction"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function SideList({ chainId, title, sides, coinbase }: { chainId: ChainId; title: string; sides: TxSide[]; coinbase?: boolean }) {
  return (
    <div className="flowcol">
      <h2>{title}</h2>
      {coinbase ? <p className="muted">No inputs. This is the block reward.</p> : null}
      {sides.length === 0 && !coinbase ? <p className="muted">None reported.</p> : null}
      {sides.map((side, index) => (
        <div className="side" key={`${title}-${index}`}>
          <div className="who">
            <Party chainId={chainId} side={side} />
            <TokenBit chainId={chainId} side={side} />
          </div>
          <div className="amt">
            {side.amount != null ? <CoinWithFiat coin={side.amount} chainId={chainId} /> : <span className="muted">Amount not reported</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TxView({ tx }: { tx: TxModel }) {
  const chain = chains[tx.chain];
  const token = [...tx.outputs, ...tx.inputs].find((side) => side.token)?.token;
  const outputTotal = tx.outputs.reduce((sum, side) => sum + (side.amount ?? 0), 0);
  return (
    <>
      <Crumb chainId={tx.chain} current={tx.coinbase ? "Coinbase" : "Transaction"} />
      <p className="eyebrow">
        {tx.coinbase ? "Coinbase" : "Transaction"} · {chain.name} ·{" "}
        {tx.confirmations > 0 ? <span className="up">Confirmed</span> : <span className="down">Waiting</span>}
      </p>
      <h1>{token ? formatRawAmount(token.amount) : tx.outputs.some((side) => side.amount != null) ? formatCoin(outputTotal, chain) : shortId(tx.txid, 10, 6)}</h1>
      <p className="lead">
        {tx.confirmations > 0 && tx.blockHeight != null ? (
          <>
            {tx.confirmations === 1 ? "1 confirmation" : `${formatNumber(tx.confirmations)} confirmations`} in{" "}
            <Link href={blockHref(tx.chain, tx.blockHeight)}>{formatNumber(tx.blockHeight)}</Link>. {tx.time ? formatWhen(tx.time) : null}
          </>
        ) : (
          <>
            In the mempool. It is not in a block yet.
            {tx.fee != null ? (
              <>
                {" "}
                Fee <CoinWithFiat coin={tx.fee} chainId={tx.chain} />
                {tx.satPerByte != null ? (
                  <>
                    {" · "}
                    <FeeRate satPerByte={tx.satPerByte} chainId={tx.chain} />
                  </>
                ) : null}
                .
              </>
            ) : null}
          </>
        )}
      </p>
      <div className="hashrow">
        <code>{tx.txid}</code>
        <CopyButton value={tx.txid} />
      </div>
      {token ? (
        <div className="callout">
          <strong>
            <Link href={tokenHref(tx.chain, token.id)}>{token.kind}</Link>
          </strong>
          <p>
            {formatRawAmount(token.amount)} of token {shortId(token.id, 12, 6)} moves in this transaction.
          </p>
        </div>
      ) : null}
      <div className="flow">
        <SideList chainId={tx.chain} title="From" sides={tx.inputs} coinbase={tx.coinbase} />
        <div className="arrow" aria-hidden="true">
          →
        </div>
        <SideList chainId={tx.chain} title="To" sides={tx.outputs} />
      </div>
      <dl className="facts">
        <div>
          <dt>Fee</dt>
          <dd>
            {tx.fee == null ? (
              "Not reported"
            ) : (
              <>
                <CoinWithFiat coin={tx.fee} chainId={tx.chain} />
                {tx.satPerByte != null ? (
                  <>
                    {" · "}
                    <FeeRate satPerByte={tx.satPerByte} chainId={tx.chain} />
                  </>
                ) : null}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>{chain.feeUnit === "vB" ? "Virtual size" : "Size"}</dt>
          <dd>{tx.size == null ? "Not reported" : chain.feeUnit === "vB" ? `${formatNumber(tx.size)} vB` : formatBytes(tx.size)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{tx.confirmations > 0 ? `Confirmed, ${formatNumber(tx.confirmations)}` : "Waiting in the mempool"}</dd>
        </div>
        <div>
          <dt>Block</dt>
          <dd>{tx.blockHeight != null ? <Link href={blockHref(tx.chain, tx.blockHeight)}>{formatNumber(tx.blockHeight)}</Link> : "Not mined"}</dd>
        </div>
      </dl>
    </>
  );
}

export function AddressView({ address }: { address: AddressModel }) {
  const chain = chains[address.chain];
  const hidden = Math.max(0, address.historyTotal - address.history.length);
  return (
    <>
      <Crumb chainId={address.chain} current="Address" />
      <p className="eyebrow">Address · {chain.name}</p>
      <h1 className="balance">
        <span className="vh">Balance </span>
        {formatNumber(address.balance, Math.min(chain.decimals, address.balance !== 0 && Math.abs(address.balance) < 1 ? chain.decimals : 2))}
        <span>{chain.ticker}</span>
      </h1>
      <p className="fiatline">
        <FiatOnly coin={address.balance} chainId={address.chain} />
        {address.unconfirmed !== 0 ? <span> · {formatNumber(address.unconfirmed, chain.decimals)} unconfirmed</span> : null}
      </p>
      <div className="hashrow">
        <code>{address.address}</code>
        <CopyButton value={address.address} />
      </div>
      {address.tokens.length > 0 ? (
        <div className="chips">
          {address.tokens.map((holding) => (
            <Link className="chip" key={holding.id} href={tokenHref(address.chain, holding.id)}>
              {shortId(holding.id, 8, 4)}
              <b>{formatRawAmount(holding.amount)}</b>
            </Link>
          ))}
        </div>
      ) : chain.tokens ? (
        <p className="muted">No token balance reported for this address.</p>
      ) : null}
      <section className="sheet" aria-labelledby="hist-h">
        <div className="sheethead">
          <h2 id="hist-h">History</h2>
        </div>
        {hidden > 0 ? (
          <p className="muted" style={{ padding: "0 10px 8px" }}>
            Showing the latest {formatNumber(address.history.length)} of {formatNumber(address.historyTotal)}.
          </p>
        ) : null}
        <table className="ledger">
          <caption className="vh">Transactions for this address</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Where</th>
            </tr>
          </thead>
          <tbody>
            {address.history.length === 0 ? (
              <tr>
                <td colSpan={2}>No transactions reported.</td>
              </tr>
            ) : (
              address.history.map((row) => (
                <tr key={row.txid}>
                  <td data-label="Transaction">
                    <Link className="mono" href={txHref(address.chain, row.txid)}>
                      {shortId(row.txid, 16, 8)}
                    </Link>
                  </td>
                  <td data-label="Where">
                    {row.height != null ? <Link href={blockHref(address.chain, row.height)}>{formatNumber(row.height)}</Link> : "Mempool"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </>
  );
}
