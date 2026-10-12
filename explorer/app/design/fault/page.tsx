import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { Fault } from "@/components/states";

export const metadata: Metadata = { title: "Could not load" };

export default function FaultDesign() {
  return (
    <Frame chain="nexa">
      <Fault />
    </Frame>
  );
}
