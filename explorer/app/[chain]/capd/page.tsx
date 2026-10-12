import type { Metadata } from "next";
import { Suspense } from "react";
import { notFound } from "next/navigation";
import { CapdScreen } from "@/components/capd";
import { Frame } from "@/components/frame";
import { LoadingState } from "@/components/states";
import { getChain } from "@/lib/chains";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ chain: "nexa" }];
}

export async function generateMetadata({ params }: { params: Promise<{ chain: string }> }): Promise<Metadata> {
  const { chain } = await params;
  const info = getChain(chain);
  return { title: info?.id === "nexa" ? "CAPD · Nexa" : "CAPD" };
}

export default async function CapdPage({ params }: { params: Promise<{ chain: string }> }) {
  const { chain } = await params;
  const info = getChain(chain);
  if (info?.id !== "nexa") notFound();
  return (
    <Frame chain="nexa">
      <Suspense fallback={<LoadingState chainId="nexa" />}>
        <CapdScreen />
      </Suspense>
    </Frame>
  );
}
