import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TxScreen } from "@/components/screens";
import { LoadingState } from "@/components/states";
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
    title: socialTitle(`Transaction · ${info.name}`),
    description: onExplorer(info.name, "Transaction"),
    path: `/${info.id}/tx/`,
  });
}

export default async function TxPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <Suspense fallback={<LoadingState chainId={info.id} />}>
        <TxScreen chainId={info.id} />
      </Suspense>
    </Frame>
  );
}
