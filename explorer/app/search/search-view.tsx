"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Frame } from "@/components/frame";
import { Missing, Results } from "@/components/states";
import { resolveChain } from "@/lib/chains";
import { interpretQuery } from "@/lib/lookup";

export function SearchView() {
  const sp = useSearchParams();
  const router = useRouter();
  const q = (sp.get("q") ?? "").trim();
  const chain = resolveChain(sp.get("chain"));
  const hits = q ? interpretQuery(q, chain) : [];
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
