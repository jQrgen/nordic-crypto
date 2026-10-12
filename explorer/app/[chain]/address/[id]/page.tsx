import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { AddressView } from "@/components/ledger";
import { getAddress, getChain } from "@/lib/data";
import { addresses } from "@/lib/data";
import { onExplorer, rootSocial, socialMetadata, socialTitle } from "@/lib/social";

export const dynamicParams = false;

export function generateStaticParams() {
  return addresses.map((x) => ({ chain: x.chain, id: x.id }));
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string; id: string }> }): Promise<Metadata> {
  const { chain, id } = await params;
  const info = getChain(chain);
  const address = getAddress(id);
  if (!info) return rootSocial();
  const label = address?.label ?? "Address";
  return socialMetadata({
    title: socialTitle(`${label} · ${info.name}`),
    description: onExplorer(info.name, label),
    path: `/${info.id}/address/${id}/`,
  });
}

export default async function AddressPage({ params }: { params: Promise<{ chain: string; id: string }> }) {
  const { chain, id } = await params;
  const info = getChain(chain);
  const address = getAddress(id);
  if (!info || !address || address.chain !== info.id) notFound();
  return (
    <Frame chain={info.id}>
      <AddressView address={address} />
    </Frame>
  );
}
