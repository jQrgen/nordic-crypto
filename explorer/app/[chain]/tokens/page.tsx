import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TokenIndex } from "@/components/tokens";
import { chainOrder, getChain } from "@/lib/data";
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
    title: socialTitle(`Tokens · ${info.name}`),
    description: onExplorer(info.name, "Tokens"),
    path: `/${info.id}/tokens/`,
  });
}

export default async function TokensPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <TokenIndex chainId={info.id} />
    </Frame>
  );
}
