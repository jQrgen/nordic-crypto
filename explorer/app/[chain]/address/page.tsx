import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { AddressScreen } from "@/components/screens";
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
    title: socialTitle(`Address · ${info.name}`),
    description: onExplorer(info.name, "Address"),
    path: `/${info.id}/address/`,
  });
}

export default async function AddressPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (!info) notFound();
  return (
    <Frame chain={info.id}>
      <Suspense fallback={<LoadingState chainId={info.id} />}>
        <AddressScreen chainId={info.id} />
      </Suspense>
    </Frame>
  );
}
