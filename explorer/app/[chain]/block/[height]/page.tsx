import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { BlockView } from "@/components/ledger";
import { getBlock, getChain } from "@/lib/data";
import { formatNumber } from "@/lib/format";
import { blocks } from "@/lib/data";
import { onExplorer, rootSocial, socialMetadata, socialTitle } from "@/lib/social";

export const dynamicParams = false;

export function generateStaticParams() {
  return blocks.map((b) => ({ chain: b.chain, height: String(b.height) }));
}


export async function generateMetadata({
  params,
}: {
  params: Promise<{ chain: string; height: string }>;
}): Promise<Metadata> {
  const { chain, height } = await params;
  const info = getChain(chain);
  const block = info && getBlock(info.id, Number(height));
  if (!info || !block) return rootSocial();
  const label = `Block ${formatNumber(block.height)}`;
  return socialMetadata({
    title: socialTitle(`${label} · ${info.name}`),
    description: onExplorer(info.name, label),
    path: `/${info.id}/block/${height}/`,
  });
}

export default async function BlockPage({ params }: { params: Promise<{ chain: string; height: string }> }) {
  const { chain, height } = await params;
  const info = getChain(chain);
  const block = info && getBlock(info.id, Number(height));
  if (!info || !block || !Number.isFinite(Number(height))) notFound();
  return (
    <Frame chain={info.id}>
      <BlockView block={block} />
    </Frame>
  );
}
