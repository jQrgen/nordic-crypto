import { Frame } from "@/components/frame";
import { LoadingState } from "@/components/states";
import { defaultChain } from "@/lib/chains";
import { socialMetadata, socialTitle } from "@/lib/social";

export const metadata = socialMetadata({
  title: socialTitle("Loading"),
  description: "The Nordic Crypto explorer is loading.",
  path: "/design/loading/",
});

export default function LoadingDesign() {
  return (
    <Frame chain={defaultChain}>
      <LoadingState />
    </Frame>
  );
}
