import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { LoadingState } from "@/components/states";
import { defaultChain } from "@/lib/data";

export const metadata: Metadata = { title: "Loading" };

export default function LoadingDesign() {
  return (
    <Frame chain={defaultChain}>
      <LoadingState />
    </Frame>
  );
}
