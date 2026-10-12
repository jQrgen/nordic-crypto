"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { chains } from "@/lib/chains";
import { formatCoin, formatFiat, formatSatPerByte, formatUnitPrice } from "@/lib/format";
import { fiatAmount, fiatPerKilobyte, loadPrices, type PriceBook } from "@/lib/prices";
import type { ChainId, Fiat } from "@/lib/types";
import { usePrefs } from "./prefs";

type PriceStatus = { status: "loading" } | { status: "unavailable" } | { status: "ready"; book: PriceBook };

const Ctx = createContext<PriceStatus>({ status: "loading" });

export function PricesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PriceStatus>({ status: "loading" });
  useEffect(() => {
    let cancel = false;
    loadPrices().then((book) => {
      if (cancel) return;
      setState(book ? { status: "ready", book } : { status: "unavailable" });
    });
    return () => {
      cancel = true;
    };
  }, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export function usePriceStatus() {
  return useContext(Ctx).status;
}

export function useUnitPrice(chainId: ChainId, fiat: Fiat): number | null {
  const state = useContext(Ctx);
  if (state.status !== "ready") return null;
  const price = state.book[chainId]?.quotes[fiat];
  return typeof price === "number" ? price : null;
}

export function useChange(chainId: ChainId, fiat: Fiat): number | null {
  const state = useContext(Ctx);
  if (state.status !== "ready") return null;
  const change = state.book[chainId]?.change[fiat];
  return typeof change === "number" ? change : null;
}

export function FiatOnly({ coin, chainId }: { coin: number; chainId: ChainId }) {
  const { fiat } = usePrefs();
  const value = fiatAmount(coin, useUnitPrice(chainId, fiat));
  if (value == null) return null;
  return <>{formatFiat(value, fiat)}</>;
}

export function CoinWithFiat({ coin, chainId }: { coin: number; chainId: ChainId }) {
  const { fiat } = usePrefs();
  const price = useUnitPrice(chainId, fiat);
  const fiatValue = fiatAmount(coin, price);
  return (
    <>
      {formatCoin(coin, chains[chainId])}
      {fiatValue != null ? <> · {formatFiat(fiatValue, fiat)}</> : null}
    </>
  );
}

export function UnitPrice({ chainId }: { chainId: ChainId }) {
  const { fiat } = usePrefs();
  const price = useUnitPrice(chainId, fiat);
  if (price == null) return null;
  return <>{formatUnitPrice(price, fiat)}</>;
}

export function UsdPrice({ chainId }: { chainId: ChainId }) {
  const { fiat } = usePrefs();
  const price = useUnitPrice(chainId, "USD");
  if (fiat === "USD" || price == null) return null;
  return <>{formatUnitPrice(price, "USD")}</>;
}

/** Fee rate, with the live fiat value of one kilobyte at that rate when a price is known. */
export function FeeRate({ satPerByte, chainId }: { satPerByte: number; chainId: ChainId }) {
  const { fiat } = usePrefs();
  const price = useUnitPrice(chainId, fiat);
  const fiatValue = fiatPerKilobyte(satPerByte, chains[chainId].subunits, price);
  return (
    <>
      {formatSatPerByte(satPerByte)}
      {fiatValue != null ? <> · {formatFiat(fiatValue, fiat)}/kB</> : null}
    </>
  );
}
