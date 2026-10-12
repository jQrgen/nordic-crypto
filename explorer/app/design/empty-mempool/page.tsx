import { Frame } from "@/components/frame";
import { EmptyMempool } from "@/components/states";
import { chains, defaultChain } from "@/lib/data";
import { onExplorer, socialMetadata, socialTitle } from "@/lib/social";

export const metadata = socialMetadata({
  title: socialTitle("Empty mempool"),
  description: onExplorer(chains[defaultChain].name, "An empty mempool"),
  path: "/design/empty-mempool/",
});

export default function EmptyMempoolDesign() {
  return (
    <Frame chain={defaultChain}>
      <EmptyMempool chainId={defaultChain} />
    </Frame>
  );
}
