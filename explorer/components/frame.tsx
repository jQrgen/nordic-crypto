"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { chainOrder, chains, defaultChain, isChainId } from "@/lib/chains";
import type { ChainId, Fiat } from "@/lib/types";
import { PricesProvider } from "./money";
import { PrefsProvider, usePrefs } from "./prefs";
import { SiteLinks } from "./site-links";

const FIATS: Fiat[] = ["NOK", "SEK", "DKK", "EUR", "USD"];

function Shield() {
  return (
    <svg className="shield" width="34" height="40" viewBox="6.4 2.4 51.2 60.2" aria-hidden="true">
      <path fill="#1E3A45" d="M8 4H32V61C18 56 8 46 8 30Z" />
      <path fill="#D9A034" d="M32 4H56V30C56 46 46 56 32 61Z" />
      <path fill="#D9A034" d="M32 8.5A8.5 8.5 0 0 0 32 25.5L32 20.8A3.8 3.8 0 0 1 32 13.2ZM28.6 24H32V49H28.6Z" />
      <path fill="#1E3A45" d="M32 8.5A8.5 8.5 0 0 1 32 25.5L32 20.8A3.8 3.8 0 0 0 32 13.2ZM32 24H35.4V49H32ZM35.4 36.5H45V41H40.5V44.5H45V49H35.4Z" />
      <path fill="none" stroke="#F0F1EC" strokeWidth="2.4" strokeLinejoin="round" d="M8 4H56V30C56 46 46 56 32 61C18 56 8 46 8 30Z" />
    </svg>
  );
}

function Shell({ chain, children }: { chain?: ChainId; children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const segment = path.split("/")[1] ?? "";
  const resolved: ChainId = chain ?? (isChainId(segment) ? segment : defaultChain);
  const { fiat, setFiat } = usePrefs();
  const section = path.includes("/capd") ? "capd" : path.includes("/mempool") ? "mempool" : path.includes("/token") ? "tokens" : "overview";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT");
      if (event.key === "/" && !typing) {
        event.preventDefault();
        document.getElementById("lookup")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <a className="skip" href="#content">
        Skip to content
      </a>
      <header className="top">
        <div className="wrap">
          <div className="brandrow">
            <Link className="brand" href={`/${resolved}`} aria-label="Nordic Crypto Explorer, home">
              <Shield />
              <span>
                <span className="brand-name">
                  Nordic <span className="w">Crypto</span>
                </span>
                <span className="brand-sub">
                  <b>Explorer</b> · since 2026
                </span>
              </span>
            </Link>
            <nav className="chains" aria-label="Chain">
              {chainOrder.map((id) => (
                <Link key={id} href={`/${id}`} aria-current={id === resolved ? "page" : undefined}>
                  <span className={`pip ${id}`} aria-hidden="true" />
                  {chains[id].name}
                </Link>
              ))}
            </nav>
            <div className="hdrtools">
              <SiteLinks />
              <label className="fiat">
                <span className="vh">Fiat currency</span>
                <select value={fiat} onChange={(event) => setFiat(event.target.value as Fiat)} aria-label="Fiat currency">
                  {FIATS.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="iconbtn"
                aria-label="Switch colour theme"
                onClick={() => {
                  const dark = document.documentElement.getAttribute("data-theme") === "dark";
                  if (dark) document.documentElement.removeAttribute("data-theme");
                  else document.documentElement.setAttribute("data-theme", "dark");
                  localStorage.setItem("nc-theme", dark ? "light" : "dark");
                }}
              >
                <svg className="i-moon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                  <path fill="currentColor" d="M20.7 14.6A8.6 8.6 0 0 1 9.4 3.3a.6.6 0 0 0-.8-.7A9.8 9.8 0 1 0 21.4 15.4a.6.6 0 0 0-.7-.8z" />
                </svg>
                <svg className="i-sun" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                  <path fill="currentColor" d="M12 6.2a5.8 5.8 0 1 0 0 11.6 5.8 5.8 0 0 0 0-11.6zM12 1.5a.9.9 0 0 1 .9.9V4a.9.9 0 1 1-1.8 0V2.4a.9.9 0 0 1 .9-.9zm0 16.6a.9.9 0 0 1 .9.9v1.6a.9.9 0 1 1-1.8 0V19a.9.9 0 0 1 .9-.9zM4 11.1a.9.9 0 0 1 .9.9.9.9 0 0 1-.9.9H2.4a.9.9 0 1 1 0-1.8H4zm17.6 0a.9.9 0 1 1 0 1.8H20a.9.9 0 1 1 0-1.8h1.6zM6.1 4.8a.9.9 0 0 1 1.3 0l1.1 1.1a.9.9 0 1 1-1.3 1.3L6.1 6.1a.9.9 0 0 1 0-1.3zm10.4 10.4a.9.9 0 0 1 1.3 0l1.1 1.1a.9.9 0 1 1-1.3 1.3l-1.1-1.1a.9.9 0 0 1 0-1.3zM17.8 4.8a.9.9 0 0 1 0 1.3l-1.1 1.1a.9.9 0 1 1-1.3-1.3l1.1-1.1a.9.9 0 0 1 1.3 0zM7.4 15.2a.9.9 0 0 1 0 1.3L6.3 17.6a.9.9 0 1 1-1.3-1.3l1.1-1.1a.9.9 0 0 1 1.3 0z" />
                </svg>
              </button>
            </div>
          </div>
          <form
            className="search"
            role="search"
            action="/search"
            onSubmit={(event) => {
              const data = new FormData(event.currentTarget);
              const q = String(data.get("q") ?? "").trim();
              if (!q) return;
              event.preventDefault();
              router.push(`/search?chain=${resolved}&q=${encodeURIComponent(q)}`);
            }}
          >
            <label className="vh" htmlFor="lookup">
              Look up a block, transaction, address or token
            </label>
            <input id="lookup" name="q" type="search" placeholder="Block, transaction, address or token" autoComplete="off" enterKeyHint="search" />
            <input type="hidden" name="chain" value={resolved} />
            <button type="submit">Look up</button>
          </form>
          <nav className="sectionnav" aria-label="Section">
            <Link href={`/${resolved}`} aria-current={section === "overview" && path === `/${resolved}` ? "page" : undefined}>
              Overview
            </Link>
            <Link href={`/${resolved}/mempool`} aria-current={section === "mempool" ? "page" : undefined}>
              Mempool
            </Link>
            <Link href={`/${resolved}/tokens`} aria-current={section === "tokens" ? "page" : undefined}>
              Tokens
            </Link>
            {resolved === "nexa" ? (
              <Link href="/nexa/capd" aria-current={section === "capd" ? "page" : undefined}>
                CAPD
              </Link>
            ) : null}
          </nav>
        </div>
      </header>
      <main id="content" className="wrap" tabIndex={-1}>
        {children}
      </main>
      <footer className="foot">
        <div className="wrap footgrid">
          <div>
            <p className="word">
              Nordic <span>Crypto</span>
            </p>
            <p>A Bitcoin Cash and Nexa explorer, set in the same type as the news site.</p>
          </div>
          <div>
            <h2>Chains</h2>
            <ul>
              {chainOrder.map((id) => (
                <li key={id}>
                  <Link href={`/${id}`}>{chains[id].name}</Link>
                </li>
              ))}
              <li><Link href={`/${resolved}/mempool`}>Mempool</Link></li>
              <li><Link href={`/${resolved}/tokens`}>Tokens</Link></li>
              {resolved === "nexa" ? (
                <li>
                  <Link href="/nexa/capd">CAPD</Link>
                </li>
              ) : null}
            </ul>
          </div>
          <div>
            <h2>Read from</h2>
            <ul>
              <li><a href="https://nordiccrypto.no/api/">Bitcoin Cash Fulcrum, port 50004</a></li>
              <li><a href="https://nordiccrypto.no/api/">Nexa Rostrum, port 20004</a></li>
              <li><a href="https://nordiccrypto.no/">nordiccrypto.no</a></li>
              <li><a href="https://github.com/nordic-crypto-org/nordic-crypto">Source on GitHub</a></li>
            </ul>
          </div>
          <div>
            <h2>Layout states</h2>
            <ul>
              <li><Link href="/design/loading">Loading</Link></li>
              <li><Link href={`/search?q=not-a-thing&chain=${defaultChain}`}>Nothing found</Link></li>
              <li><Link href="/design/catching-up">Catching up</Link></li>
              <li><Link href="/design/empty-mempool">Empty mempool</Link></li>
              <li><Link href="/design/fault">Could not load</Link></li>
            </ul>
          </div>
        </div>
      </footer>
    </>
  );
}

export function Frame({ chain, children }: { chain?: ChainId; children: ReactNode }) {
  return (
    <PrefsProvider>
      <PricesProvider>
        <Shell chain={chain}>{children}</Shell>
      </PricesProvider>
    </PrefsProvider>
  );
}
