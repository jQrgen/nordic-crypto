"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Frame } from "@/components/frame";
import { Missing, Results } from "@/components/states";
import { searchAll } from "@/lib/lookup";
import type { ChainId } from "@/lib/types";

export function SearchView() {
  const sp = useSearchParams();
  const router = useRouter();
  const q = (sp.get("q") ?? "").trim();
  const chain: ChainId = sp.get("chain") === "bch" ? "bch" : "nexa";
  const hits = q ? searchAll(q, chain) : [];
  const only = hits.length === 1 ? hits[0].href : null;

  useEffect(() => {
    if (only) router.replace(only);
  }, [only, router]);

  if (only) return null;
  return (
    <Frame chain={chain}>
      {hits.length > 1 ? <Results q={q} hits={hits} /> : <Missing q={q} chainId={chain} />}
    </Frame>
  );
}
