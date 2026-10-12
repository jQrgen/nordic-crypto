import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { Overview } from "@/components/overview";
import { getChain } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ chain: "nexa" }, { chain: "bch" }];
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  return { title: info ? info.name : "Explorer" };
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
