"use client";

import { useEffect, useRef, useState } from "react";
import { dropSession, getSession, MissingError, UnreachableError, type Session } from "@/lib/electrum";
import type { ChainId } from "@/lib/types";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "unreachable"; servers: string[] }
  | { status: "missing"; message: string }
  | { status: "ready"; data: T };

export function useChainLoad<T>(chainId: ChainId, key: string, load: (session: Session) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancel = false;
    setState({ status: "loading" });
    getSession(chainId)
      .then((session) => loadRef.current(session))
      .then((data) => {
        if (!cancel) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (cancel) return;
        if (error instanceof UnreachableError) setState({ status: "unreachable", servers: error.servers });
        else if (error instanceof MissingError) setState({ status: "missing", message: error.message });
        else setState({ status: "missing", message: "The server did not return this." });
      });
    return () => {
      cancel = true;
    };
  }, [chainId, key, attempt]);

  return {
    state,
    retry: () => {
      dropSession(chainId);
      setAttempt((value) => value + 1);
    },
  };
}
