import type { Metadata } from "next";
import { Frame } from "@/components/frame";

export const metadata: Metadata = { title: "Catching up · Bitcoin Cash" };

export default function CatchingUp() {
  return (
    <Frame chain="bch">
      <div className="banner" role="status">
        <strong>Bitcoin Cash is still catching up.</strong>
        <p>This is the layout for a server that is behind the network tip. It is not a chain reading, and it does not fill in numbers of its own.</p>
      </div>
      <p className="lead">The overview shows the tip the connected server actually reports.</p>
    </Frame>
  );
}
