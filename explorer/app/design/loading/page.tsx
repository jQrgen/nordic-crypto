import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { LoadingState } from "@/components/states";

export const metadata: Metadata = { title: "Loading" };

export default function LoadingDesign() {
  return (
    <Frame chain="nexa">
      <LoadingState />
    </Frame>
  );
}
