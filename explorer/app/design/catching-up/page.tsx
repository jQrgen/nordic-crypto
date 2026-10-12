import type { Metadata } from "next";
import { Frame } from "@/components/frame";
import { Overview } from "@/components/overview";

export const metadata: Metadata = { title: "Catching up · Bitcoin Cash" };

export default function CatchingUp() {
  return (
    <Frame chain="bch">
      <Overview chainId="bch" syncing={{ have: 972102, network: 972618, behind: "about 8 hours" }} />
    </Frame>
  );
}
