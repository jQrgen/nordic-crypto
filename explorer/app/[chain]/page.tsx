import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { Overview } from "@/components/overview";
import { chainOrder, getChain } from "@/lib/chains";
import { chainExplorerTitle, rootSocial, socialMetadata } from "@/lib/social";

export const dynamicParams = false;

export function generateStaticParams() {
  return chainOrder.map((chain) => ({ chain }));
}

export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) return rootSocial();
  return socialMetadata({
    title: chainExplorerTitle(info.name),
    description: info.about,
    path: `/${info.id}/`,
  });
}

export default async function ChainPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <Overview chainId={info.id} />
    </Frame>
  );
}
