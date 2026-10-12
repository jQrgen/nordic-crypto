"use client";

import { chains } from "@/lib/data";
import { formatFeeRateLabel, formatFiat, formatUnitPrice } from "@/lib/format";
import type { ChainId, Fiat } from "@/lib/types";
import { usePrefs } from "./prefs";

export function FeeRate({ rate, prices }: { rate: string; prices: Record<Fiat, number> }) {
  const { fiat } = usePrefs();
  const { quote, note } = formatFeeRateLabel(rate, prices[fiat], fiat);
  return (
    <span className="feerate">
      {quote}
      {note ? <span className="muted"> {note}</span> : null}
    </span>
  );
}

export function Money({ coin, chainId }: { coin: number; chainId: ChainId }) {
  const { fiat } = usePrefs();
  return <>{formatFiat(coin * chains[chainId].prices[fiat], fiat)}</>;
}

export function UnitPrice({ chainId }: { chainId: ChainId }) {
  const { fiat } = usePrefs();
  return <>{formatUnitPrice(chains[chainId].prices[fiat], fiat)}</>;
}

export function UsdPrice({ chainId }: { chainId: ChainId }) {
  const { fiat } = usePrefs();
  if (fiat === "USD") return null;
  return <>{formatUnitPrice(chains[chainId].prices.USD, "USD")}</>;
}
