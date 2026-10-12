import Link from "next/link";

// Static export: send visitors to the Nexa overview without a server.
export default function Home() {
  return (
    <>
      <meta httpEquiv="refresh" content="0; url=/nexa/" />
      <p>
        <Link href="/nexa/">Nexa explorer</Link>
      </p>
    </>
  );
}
