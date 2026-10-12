import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { AddressView } from "@/components/ledger";
import { getAddress, getChain } from "@/lib/data";
import { addresses } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return addresses.map((x) => ({ chain: x.chain, id: x.id }));
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string; id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const address = getAddress(id);
  return { title: address?.label ?? "Address" };
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
