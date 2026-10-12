import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TokenScreen } from "@/components/screens";
import { LoadingState } from "@/components/states";
import { chainOrder, getChain } from "@/lib/chains";

export const dynamicParams = false;

export function generateStaticParams() {
  return chainOrder.map((chain) => ({ chain }));
}

export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  return { title: info ? `Token · ${info.name}` : "Token" };
}

export default async function TokenPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <Suspense fallback={<LoadingState chainId={info.id} />}>
        <TokenScreen chainId={info.id} />
      </Suspense>
    </Frame>
  );
}
