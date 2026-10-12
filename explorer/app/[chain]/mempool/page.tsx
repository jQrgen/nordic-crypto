import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { MempoolScreen } from "@/components/screens";
import { chainOrder, getChain } from "@/lib/chains";
import { onExplorer, rootSocial, socialMetadata, socialTitle } from "@/lib/social";

export const dynamicParams = false;

export function generateStaticParams() {
  return chainOrder.map((chain) => ({ chain }));
}

export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) return rootSocial();
  return socialMetadata({
    title: socialTitle(`Mempool · ${info.name}`),
    description: onExplorer(info.name, "Unconfirmed transactions"),
    path: `/${info.id}/mempool/`,
  });
}

export default async function MempoolPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <MempoolScreen chainId={info.id} />
    </Frame>
  );
}
