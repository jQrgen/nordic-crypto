import Link from "next/link";
import { chains, defaultChain, homePath } from "@/lib/chains";
import { rootSocial } from "@/lib/social";

// Static export: send visitors to the Bitcoin overview without a server.
// nginx also 302s `/` to that page. This file is the export root, so crawlers
// that do not follow the redirect still receive the Bitcoin card.
export const metadata = rootSocial();

export default function Home() {
  return (
    <>
      <meta httpEquiv="refresh" content={`0; url=${homePath}`} />
      <p>
        <Link href={homePath}>{chains[defaultChain].name} explorer</Link>
      </p>
    </>
  );
}
