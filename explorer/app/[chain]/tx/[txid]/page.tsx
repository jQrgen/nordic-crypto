import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TxView } from "@/components/ledger";
import { getChain, getTx } from "@/lib/data";
import { txs } from "@/lib/data";
import { onExplorer, rootSocial, socialMetadata, socialTitle } from "@/lib/social";

export const dynamicParams = false;

export function generateStaticParams() {
  return txs.map((x) => ({ chain: x.chain, txid: x.id }));
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string; txid: string }> }): Promise<Metadata> {
  const { chain, txid } = await params;
  const info = getChain(chain);
  const tx = getTx(txid);
  if (!info) return rootSocial();
  const kind = tx?.coinbase ? "Coinbase" : "Transaction";
  return socialMetadata({
    title: socialTitle(`${kind} · ${info.name}`),
    description: onExplorer(info.name, tx?.coinbase ? "Coinbase" : "A transaction"),
    path: `/${info.id}/tx/${txid}/`,
  });
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
