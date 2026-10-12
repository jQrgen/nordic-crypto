"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { chains } from "@/lib/chains";
import {
  CapdUnsupportedError,
  capdMethodLabel,
  CAPD_FAMILIES,
  hexPreview,
  loadCapd,
  unixSecondsIso,
  type CapdMessage,
  type CapdPage,
} from "@/lib/capd";
import { UnreachableError } from "@/lib/electrum";
import { formatBytes, formatNumber, formatWhen } from "@/lib/format";
import type { LoadState } from "./use-chain";
import { CopyButton } from "./copy-button";
import { Age } from "./age";
import { ServerLine } from "./server-line";
import { LoadingState, Unreachable } from "./states";

function useCapd(hashKey: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<LoadState<CapdPage> | { status: "unsupported"; error: CapdUnsupportedError }>({ status: "loading" });

  useEffect(() => {
    let cancel = false;
    setState({ status: "loading" });
    loadCapd(hashKey)
      .then((data) => {
        if (!cancel) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (cancel) return;
        if (error instanceof UnreachableError) setState({ status: "unreachable", servers: error.servers });
        else if (error instanceof CapdUnsupportedError) setState({ status: "unsupported", error });
        else setState({ status: "missing", message: error instanceof Error ? error.message : "The server did not return CAPD." });
      });
    return () => {
      cancel = true;
    };
  }, [hashKey, attempt]);

  return {
    state,
    retry: () => setAttempt((value) => value + 1),
  };
}

function Explain() {
  return (
    <section className="section" aria-labelledby="capd-about">
      <h2 id="capd-about">What CAPD is</h2>
      <p className="lead">
        Counterparty and Protocol Discovery is a short-lived message pool on Nexa full nodes. A wallet can announce that it wants a counterparty — an atomic swap, a mix, a trade, or any other brief protocol — without writing that announcement into a block. It is not the mempool, and it is not a payment.
      </p>
      <p className="lead">
        Nodes keep the messages in memory. Proof of work sets a priority, and that priority falls as the message gets older. When the pool is full, a higher-priority message replaces lower ones. A message can expire. A node that was offline does not catch up on what it missed. The first bytes of a message are how a client picks the protocol it cares about.
      </p>
      <p className="tries">
        The description is the <a href="https://spec.nexa.org/network/capd/">CAPD specification</a>. The node calls are <a href="https://nexa.gitlab.io/nexa/commands/capd/">capd info, capd list and capd get</a>.
      </p>
    </section>
  );
}

function formatPriority(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "Not reported";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs < 0.0001 || abs >= 1e12)) return value.toExponential(4);
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 6 }).format(value);
}

function formatDifficulty(bits: number | null): string {
  if (bits == null || !Number.isFinite(bits)) return "Not reported";
  return `0x${(bits >>> 0).toString(16).padStart(8, "0")}`;
}

function when(seconds: number | null): string | null {
  const iso = unixSecondsIso(seconds);
  return iso ? formatWhen(iso) : null;
}

function MessageRows({ messages }: { messages: CapdMessage[] }) {
  return (
    <table className="ledger">
      <caption className="vh">CAPD messages</caption>
      <thead>
        <tr>
          <th>Hash</th>
          <th>Created</th>
          <th>Expiry</th>
          <th>Priority</th>
          <th>Difficulty</th>
          <th>Size</th>
          <th>Data</th>
        </tr>
      </thead>
      <tbody>
        {messages.map((message) => {
          const created = unixSecondsIso(message.created);
          return (
            <tr key={message.hash}>
              <td data-label="Hash">
                <Link className="mono" href={`/nexa/capd/?hash=${message.hash}`}>
                  {message.hash.slice(0, 16)}…
                </Link>
              </td>
              <td data-label="Created" title={created ? formatWhen(created) : undefined}>
                {created ? <Age iso={created} /> : "Not reported"}
              </td>
              <td data-label="Expiry">{when(message.expires) ?? "None"}</td>
              <td data-label="Priority" className="r">
                {formatPriority(message.priority)}
              </td>
              <td data-label="Difficulty" className="mono">
                {formatDifficulty(message.difficultyBits)}
              </td>
              <td data-label="Size">{message.size == null ? "Not reported" : formatBytes(message.size)}</td>
              <td data-label="Data">
                <span className="mono">{message.dataHex ? hexPreview(message.dataHex) : "—"}</span>
                {message.text ? (
                  <span className="muted" style={{ display: "block" }}>
                    {message.text}
                  </span>
                ) : null}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Lookup({ page }: { page: CapdPage }) {
  const router = useRouter();
  const message = page.lookup?.message;
  return (
    <section className="section" aria-labelledby="capd-lookup">
      <h2 id="capd-lookup">Look up a message</h2>
      <form
        className="search"
        onSubmit={(event) => {
          event.preventDefault();
          const hash = String(new FormData(event.currentTarget).get("hash") ?? "").trim();
          router.push(hash ? `/nexa/capd/?hash=${encodeURIComponent(hash)}` : "/nexa/capd/");
        }}
      >
        <label className="vh" htmlFor="capd-hash">
          Message hash, 64 hex characters
        </label>
        <input
          key={page.lookup?.query || "empty"}
          id="capd-hash"
          name="hash"
          defaultValue={page.lookup?.query ?? ""}
          placeholder="Message hash, 64 hex characters"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit">Look up</button>
      </form>
      {page.lookup?.error ? <p className="lead">{page.lookup.error}</p> : null}
      {message ? (
        <>
          <div className="hashrow">
            <code>{message.hash}</code>
            <CopyButton value={message.hash} />
          </div>
          <dl className="facts">
            <div>
              <dt>Created</dt>
              <dd>{when(message.created) ?? "Not reported"}</dd>
            </div>
            <div>
              <dt>Expiry</dt>
              <dd>{when(message.expires) ?? "None"}</dd>
            </div>
            <div>
              <dt>Priority</dt>
              <dd>{formatPriority(message.priority)}</dd>
            </div>
            <div>
              <dt>Initial priority</dt>
              <dd>{formatPriority(message.initialPriority)}</dd>
            </div>
            <div>
              <dt>Difficulty</dt>
              <dd>{formatDifficulty(message.difficultyBits)}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{message.size == null ? "Not reported" : formatBytes(message.size)}</dd>
            </div>
          </dl>
          {message.powTarget ? (
            <p className="mono">
              Proof-of-work target {message.powTarget}
            </p>
          ) : null}
          {message.text ? <p>{message.text}</p> : null}
          <p className="mono">{message.dataHex ? `${message.dataHex.slice(0, 256)}${message.dataHex.length > 256 ? "…" : ""}` : "The server sent no data."}</p>
        </>
      ) : null}
    </section>
  );
}

function Pool({ page }: { page: CapdPage }) {
  const chain = chains.nexa;
  const { info } = page;
  const empty = info.count === 0;
  const listNote =
    page.listed == null
      ? "This server reported the pool and did not return a message list."
      : info.count > page.messages.length
        ? `Showing the ${formatNumber(page.messages.length)} newest of ${formatNumber(page.read ?? page.messages.length)} highest-priority messages read. The pool has ${formatNumber(info.count)}. The list walks from the lowest priority upward, and priority falls with age, so newer messages are at the end.`
        : null;
  return (
    <>
      <p className="eyebrow">Nexa · CAPD</p>
      <h1>{empty ? "The pool is empty" : `${formatNumber(info.count)} ${info.count === 1 ? "message" : "messages"}`}</h1>
      <p className="lead">
        {empty
          ? "The server reported a message count of zero. Nothing is standing in for that."
          : "Messages in this node’s CAPD pool right now. They are not confirmed, and they will not be here later just because they were here now."}
      </p>
      <ServerLine label={page.serverLabel} version={page.serverVersion} fallback={page.fallback} apiHref={chain.apiHref} />
      <section className="stats" aria-label="CAPD pool">
        <div className="stat">
          <span className="eyebrow">Messages</span>
          <b className="num">{formatNumber(info.count)}</b>
          <span className="sub">In the pool on this server</span>
        </div>
        <div className="stat">
          <span className="eyebrow">Pool size</span>
          <b className="num">{formatBytes(info.size)}</b>
          <span className="sub">Bytes the server reports</span>
        </div>
        <div className="stat">
          <span className="eyebrow">Minimum priority</span>
          <b className="num">{formatPriority(info.minPriority)}</b>
          <span className="sub">
            {info.maxPriority == null ? "Lowest priority still in the pool" : `Highest is ${formatPriority(info.maxPriority)}`}
            {". The pool does not report a separate minimum difficulty."}
          </span>
        </div>
        <div className="stat">
          <span className="eyebrow">Relay priority</span>
          <b className="num">{formatPriority(info.relayPriority)}</b>
          <span className="sub">Lowest priority this node will forward</span>
        </div>
      </section>
      <Explain />
      <section className="sheet" aria-labelledby="capd-list">
        <div className="sheethead">
          <h2 id="capd-list">Recent messages</h2>
        </div>
        {page.messages.length === 0 ? (
          <p className="lead" style={{ padding: "0 10px 12px" }}>
            {empty ? "No messages to list." : listNote}
          </p>
        ) : (
          <MessageRows messages={page.messages} />
        )}
      </section>
      {page.messages.length > 0 && listNote ? <p className="tries">{listNote}</p> : null}
      <Lookup page={page} />
    </>
  );
}

function Unsupported({ error, onRetry }: { error: CapdUnsupportedError; onRetry: () => void }) {
  return (
    <>
      <p className="eyebrow">Nexa · CAPD</p>
      <h1>These servers do not speak CAPD</h1>
      <p className="lead">
        Each server below completed the Electrum handshake. None of them implement a CAPD method, so this page has no message count, pool size, or message list to show.
      </p>
      <ul>
        {error.answered.map((server) => (
          <li key={server.label} className="mono">
            {server.label}
            {server.version ? ` · ${server.version}` : ""}
            {server.primary ? "" : " · fallback"}
          </li>
        ))}
      </ul>
      {error.silent.length > 0 ? (
        <>
          <p className="lead">These did not answer:</p>
          <ul>
            {error.silent.map((label) => (
              <li key={label} className="mono">
                {label}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="lead">
        Asked {error.methods.join(", ")}. Each came back as an unknown method. Rostrum does not forward nexad’s <span className="mono">capd info</span>, <span className="mono">capd list</span> or <span className="mono">capd get</span>. Those calls stay on the node RPC port, which a browser cannot open. A read-only Electrum method with those three calls, or a public read-only proxy that allows only them, is what this page is waiting for. It will not invent a pool in the meantime.
      </p>
      <p className="tries">
        The same three names are what a future server should answer: {CAPD_FAMILIES.map((family) => capdMethodLabel(family, "info")).join(", ")}. <span className="mono">capd list</span> should return hashes, and <span className="mono">capd get</span> one message, in the shape nexad already uses.
      </p>
      <p>
        <button className="btn" type="button" onClick={onRetry}>
          Try again
        </button>
      </p>
      <Explain />
    </>
  );
}

export function CapdScreen() {
  const hashKey = (useSearchParams().get("hash") ?? "").trim();
  const { state, retry } = useCapd(hashKey);
  if (state.status === "loading") return <LoadingState chainId="nexa" />;
  if (state.status === "unreachable") return <Unreachable chainId="nexa" servers={state.servers} onRetry={retry} />;
  if (state.status === "unsupported") return <Unsupported error={state.error} onRetry={retry} />;
  if (state.status === "missing") {
    return (
      <>
        <p className="eyebrow">Nexa · CAPD</p>
        <h1>No CAPD data</h1>
        <p className="lead">{state.message}</p>
        <p>
          <Link className="btn" href="/nexa/">
            Back to Nexa
          </Link>
        </p>
        <Explain />
      </>
    );
  }
  return <Pool page={state.data} />;
}
