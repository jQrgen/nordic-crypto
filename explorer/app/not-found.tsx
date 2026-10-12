import { Frame } from "@/components/frame";
import { Missing } from "@/components/states";
import { defaultChain } from "@/lib/chains";
import { socialMetadata, socialTitle } from "@/lib/social";

export const metadata = socialMetadata({
  title: socialTitle("Page not found"),
  description: "That page is not on the Nordic Crypto explorer.",
  path: "/404.html",
});

export default function NotFound() {
  return (
    <Frame chain={defaultChain}>
      <Missing q="" chainId={defaultChain} page />
    </Frame>
  );
}
