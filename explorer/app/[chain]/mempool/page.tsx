import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { MempoolView } from "@/components/states";
import { getChain } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ chain: "nexa" }, { chain: "bch" }];
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  return { title: info ? `Mempool · ${info.name}` : "Mempool" };
}

export default async function MempoolPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <MempoolView chainId={info.id} />
    </Frame>
  );
}
