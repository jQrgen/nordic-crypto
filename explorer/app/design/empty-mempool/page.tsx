import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { EmptyMempool } from "@/components/states";

export const metadata: Metadata = { title: "Empty mempool" };

export default function EmptyMempoolDesign() {
  return (
    <Frame chain="nexa">
      <EmptyMempool chainId="nexa" />
    </Frame>
  );
}
