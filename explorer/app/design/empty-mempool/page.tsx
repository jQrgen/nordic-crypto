import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { EmptyMempool } from "@/components/states";
import { defaultChain } from "@/lib/chains";

export const metadata: Metadata = { title: "Empty mempool" };

export default function EmptyMempoolDesign() {
  return (
    <Frame chain={defaultChain}>
      <EmptyMempool chainId={defaultChain} />
    </Frame>
  );
}
