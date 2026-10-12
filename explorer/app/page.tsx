import Link from "next/link";
import { chains, defaultChain, homePath } from "@/lib/chains";

// Static export: send visitors to the Bitcoin Cash overview without a server.
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
