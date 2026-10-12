# Threat model

The pool pays real NEX from the nexad wallet. The things that can go wrong are a stolen RPC credential, a forged share, a double payment, and a public page that invents numbers. This note is the model those controls are written against.

## What the pool trusts

- nexad on the same machine, reached only at `127.0.0.1`. The pool does not open the RPC port.
- The wallet that receives the coinbase. Miners are paid from that wallet after the coinbase has matured.
- The operator who sets `fee_address`. An empty or invalid fee address stops the process before it listens.
- SQLite on the local disk as the only ledger.

## Credentials

The RPC password is not in the repository. The client reads nexad's cookie file, or `NEXAPOOL_RPC_USER` and `NEXAPOOL_RPC_PASSWORD` from the environment. A wallet passphrase, if the wallet is encrypted, is a separate file outside the repository. The process never writes that passphrase to the log. The sample unit runs as the `nexa` user, which can already read the cookie nexad creates. Do not make the cookie or the passphrase file world-readable, and do not put either in the config file that might be copied around.

Anyone who can call `sendtoaddress` on this node can empty the wallet. Keep port 7227 on localhost. Keep the API on `127.0.0.1` and let nginx be the only public HTTP listener.

## Shares

A share is accepted only after NexaPow matches the published echelon construction, including the Bitcoin Cash Schnorr step, and the digest is at or below the miner's share target. The test vectors from the echelon specification are checked in `internal/nexa`. A repeated job-and-nonce, or a repeated proof hash, is a duplicate and is not paid twice. A share for an unknown job is stale. The solution nonce must be 1 to 16 bytes and must carry the session extranonce, so one connection cannot submit another connection's extranonce space as its own.

The username is the payout address. Anyone can mine to any valid address. That is the pool's account model: knowing an address lets you add hashrate to it, and it does not let you withdraw it. A submit whose address does not match the authorized session is rejected.

Variable difficulty starts at 0.2 and will not fall below 0.05, so a client cannot fill the database with a stream of near-zero shares. The listener also stops accepting connections past 4096 open sessions.

## Blocks, reorgs, and maturity

A share that also meets the network target is submitted with `submitminingsolution`. The coinbase is credited only after `getblock` reports at least the configured confirmations (5000 on mainnet, the coinbase maturity in nexad). Until then the credit is immature and `Payable` ignores it. If the block disappears from the node, the immature credit is dropped. A block that has already matured is not reversed: 5000 confirmations is past the node's rolling checkpoint, and clawing it back in the ledger would desync the wallet.

Maturity uses the coinbase value nexad reports, not a number typed into the config. If that value is missing, the block stays immature and is tried again.

## Payouts

A payout is inserted as `reserved` in the same transaction that checks the mature balance. Reserved and sent rows both reduce what is still payable, so a second pass cannot reserve the same coins. The wallet comment is `nexapool:` plus 16 random bytes. If the process dies after nexad has accepted the transaction and before the row is marked sent, the next pass finds that comment with `listtransactions` and records the txid instead of sending again.

A definite wallet error marks the payout failed and returns the coins to the balance. A timeout, a dropped connection, or an empty txid leaves the reservation in place. Those are the cases where the send might have happened.

The payout pass also reads the wallet balance and will not reserve more than it can spend. One NEX stays in the wallet by default so a transaction fee cannot drain the last coin. That reserve can leave a dust balance under the minimum; it is not paid out early.

The fee is one percent, floored. Rounding dust from the miner split is added to the fee so the credits sum to the coinbase and no miner is paid more than their work. With no shares in the window the whole reward is a fee credit.

## The public site and API

The API is read-only. It returns addresses, shares, balances, and payouts. It does not return idempotency keys, the cookie, or the passphrase. When the node is down, hashrate, miner count, network hashrate, and pool share are JSON null. The page leaves those figures hidden and says the node is not connected. If the request fails, the page says the API is not responding. It does not substitute an example hashrate.

Queries use bound parameters. Address lookup rejects anything that is not a mainnet Nexa cashaddr with a valid polymod, including the old help-text example whose checksum does not match.

## Tailstorm

Until Hard Fork 2 (mainnet activation time 1793495471, 1 November 2026), a zero previous-hash is the pre-Tailstorm hash. After the fork, nexad puts the real previous hash in the candidate and the pool binds the proof to it. Miners that still hash the old way will produce shares this pool rejects. That is the intended break.

## What this does not defend against

A miner with a lot of hashrate can take a large part of the PPLNS window. That is how the window works. A stolen copy of the wallet, or a person who can log in as `nexa` on the server, can spend the coinbase. The pool is not a second custody layer on top of the node.
