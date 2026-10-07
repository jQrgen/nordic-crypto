// Broadcast a signed testnet transaction. A mainnet URL is not used.
// The node answer is returned as text so a caller can tell a rejected
// input from a transaction the node could not decode.

const NEXA_ELECTRUM = "wss://testnet-electrum.nexa.org:30004";
// Chipnet. The old fullstack.cash HTTP route answers 405 and never sees the
// transaction. Electrum broadcast is what a chipnet node actually parses.
const BCH_ELECTRUM = [
  "wss://chipnet.imaginary.cash:50004",
  "wss://chipnet.bch.ninja:50004",
];

// JSON numbers above 15 digits are not exact. Token amounts use bit 63.
function parseRpc(text) {
  const safe = String(text).replace(/([:\[,]\s*)(-?\d{16,})(?=\s*[,}\]])/g, '$1"$2"');
  return JSON.parse(safe);
}

export function electrumCall(socket, method, params) {
  const id = 1;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      socket.close();
      reject(new Error("electrum_timeout"));
    }, 12000);
    const onMsg = (event) => {
      let msg;
      try { msg = parseRpc(typeof event.data === "string" ? event.data : ""); } catch { return; }
      if (msg.id !== id) return;
      clearTimeout(timer);
      socket.removeEventListener("message", onMsg);
      if (msg.error) resolve({ ok: false, error: msg.error });
      else resolve({ ok: true, result: msg.result });
    };
    socket.addEventListener("message", onMsg);
    socket.send(JSON.stringify({ id, method, params }));
  });
}

export async function broadcastNexa(hex, { WebSocketImpl = globalThis.WebSocket, url = NEXA_ELECTRUM } = {}) {
  const socket = new WebSocketImpl(url);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("electrum_timeout")), 12000);
    socket.addEventListener("open", () => { clearTimeout(timer); resolve(); });
    socket.addEventListener("error", () => { clearTimeout(timer); reject(new Error("electrum_unreachable")); });
  });
  try {
    await electrumCall(socket, "server.version", ["nordic-crypto-mint", "1.4"]);
    return await electrumCall(socket, "blockchain.transaction.broadcast", [hex]);
  } finally {
    socket.close();
  }
}

async function electrumOnce(url, calls, WebSocketImpl) {
  const socket = new WebSocketImpl(url);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("electrum_timeout")), 12000);
    socket.addEventListener("open", () => { clearTimeout(timer); resolve(); });
    socket.addEventListener("error", () => { clearTimeout(timer); reject(new Error("electrum_unreachable")); });
  });
  try {
    let last;
    for (const [method, params] of calls) last = await electrumCall(socket, method, params);
    return last;
  } finally {
    socket.close();
  }
}

export async function broadcastBch(hex, { WebSocketImpl = globalThis.WebSocket, urls = BCH_ELECTRUM } = {}) {
  let last = { ok: false, error: "electrum_unreachable" };
  for (const url of urls) {
    try {
      return await electrumOnce(url, [
        ["server.version", ["nordic-crypto-mint", "1.4"]],
        ["blockchain.transaction.broadcast", [hex]],
      ], WebSocketImpl);
    } catch (e) {
      last = { ok: false, error: e && e.message ? e.message : "electrum_unreachable", url };
    }
  }
  return last;
}

export async function electrumRequest(url, method, params, WebSocketImpl = globalThis.WebSocket) {
  return electrumOnce(url, [
    ["server.version", ["nordic-crypto-mint", "1.4"]],
    [method, params],
  ], WebSocketImpl);
}

export { NEXA_ELECTRUM, BCH_ELECTRUM };

export async function nexaTip({ WebSocketImpl = globalThis.WebSocket, url = NEXA_ELECTRUM } = {}) {
  const socket = new WebSocketImpl(url);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("electrum_timeout")), 12000);
    socket.addEventListener("open", () => { clearTimeout(timer); resolve(); });
    socket.addEventListener("error", () => { clearTimeout(timer); reject(new Error("electrum_unreachable")); });
  });
  try {
    return await electrumCall(socket, "blockchain.headers.subscribe", []);
  } finally {
    socket.close();
  }
}
