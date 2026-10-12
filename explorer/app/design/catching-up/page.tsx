import { Frame } from "@/components/frame";
import { Overview } from "@/components/overview";
import { onExplorer, socialMetadata, socialTitle } from "@/lib/social";

export const metadata = socialMetadata({
  title: socialTitle("Catching up · Bitcoin Cash"),
  description: onExplorer("Bitcoin Cash", "Catching up to the chain tip"),
  path: "/design/catching-up/",
});

export default function CatchingUp() {
  return (
    <Frame chain="bch">
      <Overview chainId="bch" syncing={{ have: 972102, network: 972618, behind: "about 8 hours" }} />
    </Frame>
  );
}
