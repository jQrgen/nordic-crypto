import { Frame } from "@/components/frame";
import { Missing } from "@/components/states";
import { defaultChain } from "@/lib/data";

export default function NotFound() {
  return (
    <Frame chain={defaultChain}>
      <Missing q="" chainId={defaultChain} page />
    </Frame>
  );
}
