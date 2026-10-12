import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Frame } from "@/components/frame";
import { TokenView } from "@/components/tokens";
import { getChain, getToken } from "@/lib/data";
import { tokens } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return tokens.map((x) => ({ chain: x.chain, id: x.id }));
}


export async function generateMetadata({ params }: { params: Promise<{ chain: string; id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const token = getToken(id);
  return { title: token ? `${token.ticker} · ${token.name}` : "Token" };
}

export default async function TokenPage({ params }: { params: Promise<{ chain: string; id: string }> }) {
  const { chain, id } = await params;
  const info = getChain(chain);
  const token = getToken(id);
  if (!info || !token || token.chain !== info.id) notFound();
  return (
    <Frame chain={info.id}>
      <TokenView token={token} />
    </Frame>
  );
}
