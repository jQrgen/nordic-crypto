"use client";

import { useEffect, useState } from "react";
import { formatAge, formatWhen } from "@/lib/format";

/** Relative time after mount, so the server render and the browser agree. */
export function Age({ iso }: { iso: string | null }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
  }, [iso]);
  if (!iso) return <>Waiting</>;
  if (now == null) return <>{formatWhen(iso).split(" · ")[0]}</>;
  return <>{formatAge(iso, now)}</>;
}
