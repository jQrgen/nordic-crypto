import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { Fault } from "@/components/states";
import { defaultChain } from "@/lib/chains";

export const metadata: Metadata = { title: "Could not load" };

export default function FaultDesign() {
  return (
    <Frame chain={defaultChain}>
      <Fault />
    </Frame>
  );
}
