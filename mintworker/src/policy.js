// Hard caps for a mint. Pure: no I/O, no logging, no key material.
// One NexaID may mint once per event on Nexa (the card kind does not grant a second mint).
// Bitcoin Cash uses the same shape with the receiving address as the identity.

export function draw(chainCaps) {
  return chainCaps.network + chainCaps.airdrop;
}

export function treasuryStatus(balance, chainCaps) {
  const cost = draw(chainCaps);
  if (balance == null || balance <= chainCaps.reserve || balance < cost) return "empty";
  if (balance < chainCaps.low_below) return "low";
  return "ok";
}

function deny(reason, balance, chainCaps) {
  const status = treasuryStatus(balance, chainCaps);
  return {
    allow: false,
    reason,
    status,
    needs_funding: status !== "ok",
    above_target: balance != null && balance > chainCaps.hot_balance_target,
  };
}

export function evaluate(caps, state, req) {
  const chainCaps = caps[req.chain];
  if (!chainCaps) return { allow: false, reason: "unknown_chain", status: "empty", needs_funding: true, above_target: false };
  const balance = req.balance;
  const above = balance != null && balance > chainCaps.hot_balance_target;
  if (balance == null) return deny("balance_unknown", balance, chainCaps);
  if (balance <= chainCaps.reserve || balance < draw(chainCaps)) return deny("below_reserve", balance, chainCaps);
  const claims = state.claims || new Set();
  if (claims.has(req.identityHash)) {
    const status = treasuryStatus(balance, chainCaps);
    return { allow: false, reason: "identity_used", status, needs_funding: status !== "ok", above_target: above };
  }
  const eventKey = req.chain + "|" + req.eventId;
  const dayKey = req.chain + "|" + req.day;
  const eventN = (state.eventCounts && state.eventCounts[eventKey]) || 0;
  const dayN = (state.dayCounts && state.dayCounts[dayKey]) || 0;
  if (eventN >= chainCaps.per_event) {
    const status = treasuryStatus(balance, chainCaps);
    return { allow: false, reason: "event_cap", status, needs_funding: status !== "ok", above_target: above };
  }
  if (dayN >= chainCaps.per_day) {
    const status = treasuryStatus(balance, chainCaps);
    return { allow: false, reason: "day_cap", status, needs_funding: status !== "ok", above_target: above };
  }
  const status = treasuryStatus(balance, chainCaps);
  return {
    allow: true,
    reason: null,
    status,
    needs_funding: status !== "ok",
    above_target: above,
    draw: draw(chainCaps),
  };
}

export function claimKey(chain, eventId, day) {
  return { eventKey: chain + "|" + eventId, dayKey: chain + "|" + day };
}
