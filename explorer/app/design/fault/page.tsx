import { Frame } from "@/components/frame";
import { Fault } from "@/components/states";
import { defaultChain } from "@/lib/chains";
import { socialMetadata, socialTitle } from "@/lib/social";

export const metadata = socialMetadata({
  title: socialTitle("Could not load"),
  description: "The Nordic Crypto explorer could not load this page.",
  path: "/design/fault/",
});

export default function FaultDesign() {
  return (
    <Frame chain={defaultChain}>
      <Fault />
    </Frame>
  );
}
