import Link from "next/link";
import { blockFees, chains, confirmations, getAddress, getToken, getTx, nextBlock, previousBlock } from "@/lib/data";
import { formatAge, formatBytes, formatCoin, formatGap, formatNumber, formatTokenAmount, formatWhen, shortId } from "@/lib/format";
import type { Address, Block, ChainId, Tx, TxSide } from "@/lib/types";
import { CopyButton } from "./copy-button";
import { FeeRate, Money } from "./money";

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
  if (!side.addressId) return <span>{side.label ?? "Unknown"}</span>;
  const address = getAddress(side.addressId);
  if (!address) return <span>{side.label ?? side.addressId}</span>;
  return (
    <Link href={`/${chainId}/address/${address.id}`}>
      {address.label ?? shortId(address.address)}
    </Link>
  );
}

function TokenBit({ chainId, side }: { chainId: ChainId; side: TxSide }) {
  if (!side.token) return null;
  const token = getToken(side.token.tokenId);
  if (!token) return null;
  return (
    <Link className="tokenline" href={`/${chainId}/token/${token.id}`}>
      {formatTokenAmount(side.token.amount, token.decimals, token.ticker)}
    </Link>
  );
}

export function BlockView({ block }: { block: Block }) {
  const chain = chains[block.chain];
  const prev = previousBlock(block);
  const next = nextBlock(block);
  const fees = blockFees(block);
  return (
    <>
      <Crumb chainId={block.chain} current={`Block ${formatNumber(block.height)}`} />
      <p className="eyebrow">Block · {chain.name}</p>
      <h1 className="num">#{formatNumber(block.height)}</h1>
      <p className="lead">
        {formatAge(block.time)}. {formatWhen(block.time)}.
        {prev ? ` Mined ${formatGap(block.time, prev.time)} after the block before it.` : ""}
      </p>
      <div className="hashrow">
        <code>{block.hash}</code>
        <CopyButton value={block.hash} />
      </div>
      <div className="pager">
        {prev ? <Link href={`/${block.chain}/block/${prev.height}`}>← {formatNumber(prev.height)}</Link> : <span />}
        {next ? <Link href={`/${block.chain}/block/${next.height}`}>{formatNumber(next.height)} →</Link> : <span>Latest block</span>}
      </div>
      <dl className="facts">
        <div>
          <dt>Miner</dt>
          <dd>{block.minerAddressId ? <Link href={`/${block.chain}/address/${block.minerAddressId}`}>{block.miner}</Link> : block.miner}</dd>
        </div>
        <div>
          <dt>Transactions</dt>
          <dd>{formatNumber(block.txIds.length)}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(block.size)}</dd>
        </div>
        <div>
          <dt>Reward</dt>
          <dd>
            {formatCoin(block.reward, chain)} · <Money coin={block.reward} chainId={block.chain} />
          </dd>
        </div>
        <div>
          <dt>Fees</dt>
          <dd>{formatCoin(fees, chain)}</dd>
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
          <dd>{formatNumber(chain.height - block.height + 1)}</dd>
        </div>
        <div>
          <dt>Previous</dt>
          <dd className="mono">
            {prev ? <Link href={`/${block.chain}/block/${prev.height}`}>{shortId(block.previous, 14, 8)}</Link> : shortId(block.previous, 14, 8)}
          </dd>
        </div>
        <div>
          <dt>Merkle root</dt>
          <dd className="mono">{shortId(block.merkle, 14, 8)}</dd>
        </div>
      </dl>
      <section className="sheet" aria-labelledby="btx-h">
        <div className="sheethead">
          <h2 id="btx-h">{block.txIds.length === 1 ? "1 transaction" : `${formatNumber(block.txIds.length)} transactions`}</h2>
        </div>
        <table className="ledger">
          <caption className="vh">Transactions in block {formatNumber(block.height)}</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Kind</th>
              <th className="r">Fee</th>
            </tr>
          </thead>
          <tbody>
            {block.txIds.map((id) => {
              const tx = getTx(id);
              if (!tx) return null;
              return (
                <tr key={id}>
                  <td data-label="Transaction">
                    <Link className="mono" href={`/${block.chain}/tx/${tx.id}`}>
                      {shortId(tx.hash, 16, 8)}
                    </Link>
                  </td>
                  <td data-label="Kind">{tx.coinbase ? "Coinbase" : "Payment"}</td>
                  <td data-label="Fee" className="r">
                    {formatCoin(tx.fee, chain)}
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

function SideList({ chainId, title, sides, coinbase }: { chainId: ChainId; title: string; sides: TxSide[]; coinbase?: boolean }) {
  const chain = chains[chainId];
  return (
    <div className="flowcol">
      <h2>{title}</h2>
      {coinbase ? <p className="muted">No inputs. This is the block reward.</p> : null}
      {sides.map((side, index) => (
        <div className="side" key={`${title}-${index}`}>
          <div className="who">
            <Party chainId={chainId} side={side} />
            <TokenBit chainId={chainId} side={side} />
          </div>
          <div className="amt">
            {side.amount > 0 || !side.token ? (
              <>
                {formatCoin(side.amount, chain)}
                <span className="muted" style={{ display: "block" }}>
                  <Money coin={side.amount} chainId={chainId} />
                </span>
              </>
            ) : (
              <span className="muted">—</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TxView({ tx }: { tx: Tx }) {
  const chain = chains[tx.chain];
  const conf = confirmations(tx);
  const primary = tx.outputs.find((o) => o.token) ?? tx.outputs[0];
  const token = primary?.token ? getToken(primary.token.tokenId) : undefined;
  const headline = token
    ? formatTokenAmount(primary!.token!.amount, token.decimals, token.ticker)
    : formatCoin(tx.outputs.reduce((sum, o) => sum + o.amount, 0), chain);

  return (
    <>
      <Crumb chainId={tx.chain} current={tx.coinbase ? "Coinbase" : "Transaction"} />
      <p className="eyebrow">
        {tx.coinbase ? "Coinbase" : "Transaction"} · {chain.name} ·{" "}
        {conf > 0 ? <span className="up">Confirmed</span> : <span className="down">Waiting</span>}
      </p>
      <h1>{headline}</h1>
      <p className="lead">
        {conf > 0 ? (
          <>
            {conf === 1 ? "1 confirmation" : `${formatNumber(conf)} confirmations`} in{" "}
            <Link href={`/${tx.chain}/block/${tx.blockHeight}`}>{formatNumber(tx.blockHeight!)}</Link>. {tx.time ? formatWhen(tx.time) : null}.
          </>
        ) : (
          <>In the mempool. It is not in a block yet. Fee {formatCoin(tx.fee, chain)} · <FeeRate rate={tx.feeRate} prices={chain.prices} />.</>
        )}
      </p>
      <div className="hashrow">
        <code>{tx.hash}</code>
        <CopyButton value={tx.hash} />
      </div>
      {token ? (
        <div className="callout">
          <strong>
            <Link href={`/${tx.chain}/token/${token.id}`}>{token.name}</Link> · {token.kind}
          </strong>
          <p>
            {formatTokenAmount(primary!.token!.amount, token.decimals, token.ticker)} moves in this transaction.
            {tx.chain === "bch" ? " The output also carries a small Bitcoin Cash amount, which CashTokens require." : " The NEX beside it is the coin moved with the token, including change."}
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
            {formatCoin(tx.fee, chain)} · <FeeRate rate={tx.feeRate} prices={chain.prices} />
          </dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(tx.size)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{conf > 0 ? `Confirmed, ${formatNumber(conf)}` : "Waiting in the mempool"}</dd>
        </div>
        <div>
          <dt>Block</dt>
          <dd>
            {tx.blockHeight ? <Link href={`/${tx.chain}/block/${tx.blockHeight}`}>{formatNumber(tx.blockHeight)}</Link> : "Not mined"}
          </dd>
        </div>
      </dl>
    </>
  );
}

export function AddressView({ address }: { address: Address }) {
  const chain = chains[address.chain];
  return (
    <>
      <Crumb chainId={address.chain} current={address.label ?? "Address"} />
      <p className="eyebrow">Address · {chain.name}{address.label ? ` · ${address.label}` : ""}</p>
      <h1 className="balance">
        <span className="vh">Balance </span>
        {formatCoin(address.balance, chain).replace(` ${chain.ticker}`, "")}
        <span>{chain.ticker}</span>
      </h1>
      <p className="fiatline">
        <Money coin={address.balance} chainId={address.chain} />
      </p>
      <div className="hashrow">
        <code>{address.address}</code>
        <CopyButton value={address.address} />
      </div>
      {address.tokens.length > 0 ? (
        <div className="chips">
          {address.tokens.map((holding) => {
            const token = getToken(holding.tokenId);
            if (!token) return null;
            return (
              <Link className="chip" key={holding.tokenId} href={`/${address.chain}/token/${token.id}`}>
                {token.name}
                <b>{formatTokenAmount(holding.amount, token.decimals, token.ticker)}</b>
              </Link>
            );
          })}
        </div>
      ) : (
        <p className="muted">No tokens on this address in the sample.</p>
      )}
      <section className="sheet" aria-labelledby="hist-h">
        <div className="sheethead">
          <h2 id="hist-h">History</h2>
        </div>
        <table className="ledger">
          <caption className="vh">Transactions for this address</caption>
          <thead>
            <tr>
              <th>Transaction</th>
              <th>When</th>
              <th>Where</th>
            </tr>
          </thead>
          <tbody>
            {address.txIds.map((id) => {
              const tx = getTx(id);
              if (!tx) return null;
              return (
                <tr key={id}>
                  <td data-label="Transaction">
                    <Link className="mono" href={`/${address.chain}/tx/${tx.id}`}>
                      {tx.coinbase ? "Coinbase" : shortId(tx.hash, 12, 6)}
                    </Link>
                  </td>
                  <td data-label="When" className="muted">
                    {tx.blockHeight ? formatAge(tx.time) : "Waiting"}
                  </td>
                  <td data-label="Where">
                    {tx.blockHeight ? <Link href={`/${address.chain}/block/${tx.blockHeight}`}>{formatNumber(tx.blockHeight)}</Link> : "Mempool"}
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
