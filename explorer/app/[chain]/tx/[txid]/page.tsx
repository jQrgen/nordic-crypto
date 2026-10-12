import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TxView } from "@/components/ledger";
import { getChain, getTx } from "@/lib/data";
import { txs } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return txs.map((x) => ({ chain: x.chain, txid: x.id }));
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string; txid: string }> }): Promise<Metadata> {
  const { txid } = await params;
  const tx = getTx(txid);
  return { title: tx ? (tx.coinbase ? "Coinbase" : "Transaction") : "Transaction" };
}

export default async function TxPage({ params }: { params: Promise<{ chain: string; txid: string }> }) {
  const { chain, txid } = await params;
  const info = getChain(chain);
  const tx = getTx(txid);
  if (!info || !tx || tx.chain !== info.id) notFound();
  return (
    <Frame chain={info.id}>
      <TxView tx={tx} />
    </Frame>
  );
}
