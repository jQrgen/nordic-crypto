"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Fiat } from "@/lib/types";

type Prefs = { fiat: Fiat; setFiat: (fiat: Fiat) => void };

const Ctx = createContext<Prefs>({ fiat: "NOK", setFiat: () => {} });

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [fiat, setFiatState] = useState<Fiat>("NOK");

  useEffect(() => {
    const stored = localStorage.getItem("nc-fiat");
    if (stored === "NOK" || stored === "SEK" || stored === "DKK" || stored === "EUR" || stored === "USD") {
      setFiatState(stored);
    }
  }, []);

  const setFiat = (next: Fiat) => {
    setFiatState(next);
    localStorage.setItem("nc-fiat", next);
  };

  return <Ctx.Provider value={{ fiat, setFiat }}>{children}</Ctx.Provider>;
}

export function usePrefs() {
  return useContext(Ctx);
}
