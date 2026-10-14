package nexa

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

// Client talks to a local nexad over JSON-RPC.
type Client struct {
	URL         string
	User        string
	Password    string
	HTTP        *http.Client
	PoolAddress string // coinbase output that counts as the pool reward
	// Log receives the wallet scan's final from. Nil uses the standard logger.
	Log *log.Logger
}

// Payment is a wallet send identified the way explorers do.
// TxID is nexad's transaction id (GetId), never the idem sendtoaddress returns.
// TxIdem is GetIdem, kept so a later gettransaction can resolve the id.
type Payment struct {
	TxID          string
	TxIdem        string
	Confirmations int64
}

// SendHeld means sendtoaddress may have been accepted but the canonical
// txid is not known yet. The idem, when set, is safe to store. The send
// must not be repeated.
type SendHeld struct {
	TxID   string
	TxIdem string
	Err    error
}

func (e *SendHeld) Error() string {
	msg := "send outcome unknown"
	if e != nil && e.Err != nil {
		msg = e.Err.Error()
	}
	return "nexa: " + msg
}

func (e *SendHeld) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

// HeldPayment is the identifier captured before the outcome was known.
func (e *SendHeld) HeldPayment() (string, string) { return e.TxID, e.TxIdem }

// Candidate is one getminingcandidate result.
type Candidate struct {
	ID               int64  `json:"id"`
	HeaderCommitment string `json:"headerCommitment"`
	NBits            string `json:"nBits"`
	PrevHash         string `json:"previousBlockHash"`
}

// MiningInfo is the subset of getmininginfo the pool publishes.
type MiningInfo struct {
	Blocks          int64   `json:"blocks"`
	Difficulty      float64 `json:"difficulty"`
	NetworkHashrate float64 `json:"networkhashps"`
}

// Block is a decoded getblock result, enough to judge maturity and reward.
type Block struct {
	Hash          string
	Height        int64
	Confirmations int64
	Reward        int64
	Time          int64
}

// NewClient builds a client. cookieFile is nexad's .cookie, "user:password".
// An explicit user and password replace the cookie.
func NewClient(url, user, password, cookieFile string) (*Client, error) {
	if user == "" && password == "" && cookieFile != "" {
		raw, err := ReadPrivateFile(cookieFile)
		if err != nil {
			return nil, fmt.Errorf("nexa: cookie: %w", err)
		}
		parts := strings.SplitN(strings.TrimSpace(string(raw)), ":", 2)
		if len(parts) != 2 || parts[0] == "" {
			return nil, fmt.Errorf("nexa: cookie file is not user:password")
		}
		user, password = parts[0], parts[1]
	}
	if url == "" {
		url = "http://127.0.0.1:7227/"
	}
	if err := RequireLoopbackURL(url); err != nil {
		return nil, err
	}
	return &Client{
		URL:      url,
		User:     user,
		Password: password,
		HTTP: &http.Client{
			Timeout: 30 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return errors.New("nexa: refusing redirect")
			},
		},
	}, nil
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func (e *rpcError) Error() string { return e.Message }

// Call performs one JSON-RPC request.
func (c *Client) Call(method string, params []any, out any) error {
	body, err := json.Marshal(map[string]any{
		"jsonrpc": "1.0",
		"id":      "nexapool",
		"method":  method,
		"params":  params,
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.URL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "text/plain")
	if c.User != "" || c.Password != "" {
		req.SetBasicAuth(c.User, c.Password)
	}
	res, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("nexa: %w", err)
	}
	defer res.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(res.Body, 8<<20))
	if err != nil {
		return err
	}
	var envelope struct {
		Result json.RawMessage `json:"result"`
		Error  *rpcError       `json:"error"`
	}
	if err := json.Unmarshal(raw, &envelope); err != nil {
		return fmt.Errorf("nexa: bad rpc response: %w", err)
	}
	if envelope.Error != nil {
		return envelope.Error
	}
	if out == nil {
		return nil
	}
	if len(envelope.Result) == 0 || string(envelope.Result) == "null" {
		return fmt.Errorf("nexa: empty result from %s", method)
	}
	return json.Unmarshal(envelope.Result, out)
}

// GetMiningCandidate asks nexad for a header commitment. address, when set,
// is the coinbase destination and must belong to the node wallet.
func (c *Client) GetMiningCandidate(address string) (Candidate, error) {
	params := []any{}
	if address != "" {
		params = []any{nil, address}
	}
	var cand Candidate
	if err := c.Call("getminingcandidate", params, &cand); err != nil {
		return Candidate{}, err
	}
	if cand.HeaderCommitment == "" || cand.NBits == "" {
		return Candidate{}, fmt.Errorf("nexa: mining candidate missing headerCommitment")
	}
	return cand, nil
}

// SubmitSolution submits a nonce for a candidate id. A non-empty Result
// string from nexad is a rejection (the block was not accepted).
func (c *Client) SubmitSolution(id int64, nonceHex string) (height int64, hash string, err error) {
	var raw json.RawMessage
	err = c.Call("submitminingsolution", []any{map[string]any{"id": id, "nonce": nonceHex}}, &raw)
	if err != nil {
		return 0, "", err
	}
	var asString string
	if json.Unmarshal(raw, &asString) == nil {
		return 0, "", fmt.Errorf("nexa: %s", asString)
	}
	var body struct {
		Height int64   `json:"height"`
		Hash   string  `json:"hash"`
		Result *string `json:"result"`
	}
	if err := json.Unmarshal(raw, &body); err != nil {
		return 0, "", err
	}
	if body.Result != nil && *body.Result != "" {
		return body.Height, body.Hash, fmt.Errorf("nexa: %s", *body.Result)
	}
	return body.Height, body.Hash, nil
}

// GetMiningInfo reads chain height, difficulty and network hashrate.
func (c *Client) GetMiningInfo() (MiningInfo, error) {
	var info MiningInfo
	err := c.Call("getmininginfo", []any{}, &info)
	return info, err
}

// GetBlock reads a block at verbosity 2 so the coinbase outputs are present.
func (c *Client) GetBlock(hash string) (Block, error) {
	var raw json.RawMessage
	if err := c.Call("getblock", []any{hash, 2}, &raw); err != nil {
		return Block{}, err
	}
	var body struct {
		Hash          string `json:"hash"`
		Height        int64  `json:"height"`
		Confirmations int64  `json:"confirmations"`
		Time          int64  `json:"time"`
		Tx            []struct {
			Vout []struct {
				Value        json.Number `json:"value"`
				ScriptPubKey struct {
					Addresses []string `json:"addresses"`
				} `json:"scriptPubKey"`
			} `json:"vout"`
		} `json:"tx"`
	}
	if err := json.Unmarshal(raw, &body); err != nil {
		return Block{}, err
	}
	var reward int64
	if len(body.Tx) > 0 {
		want := strings.ToLower(strings.TrimSpace(c.PoolAddress))
		if want == "" {
			return Block{}, fmt.Errorf("nexa: coinbase address is not set")
		}
		for _, out := range body.Tx[0].Vout {
			if !paysAddress(out.ScriptPubKey.Addresses, want) {
				continue
			}
			sats, err := ParseNEX(out.Value.String())
			if err != nil {
				return Block{}, err
			}
			reward += sats
		}
	}
	return Block{
		Hash: body.Hash, Height: body.Height, Confirmations: body.Confirmations,
		Time: body.Time, Reward: reward,
	}, nil
}

// SendToAddress pays amount from the node wallet. The comment is the
// payout idempotency key. nexad's sendtoaddress returns the transaction
// idem (GetIdem), not the id explorers show. This resolves the idem with
// gettransaction and returns GetId as Payment.TxID. If that lookup fails,
// the error is a SendHeld carrying the idem: the coins may already have
// moved, so the caller must store the idem and must not send again.
func (c *Client) SendToAddress(address string, sats int64, comment string) (Payment, error) {
	var idem string
	if err := c.Call("sendtoaddress", []any{address, FormatNEX(sats), comment, ""}, &idem); err != nil {
		return Payment{}, err
	}
	if idem == "" {
		return Payment{}, &SendHeld{Err: fmt.Errorf("empty send id")}
	}
	pay, found, err := c.getPayment(idem)
	if err != nil || !found || pay.TxID == "" {
		if err == nil {
			err = fmt.Errorf("gettransaction did not return a txid")
		}
		return Payment{TxIdem: idem}, &SendHeld{TxIdem: idem, Err: err}
	}
	if pay.TxIdem == "" {
		pay.TxIdem = idem
	}
	return pay, nil
}

// WalletBalance returns the spendable wallet balance in subunits.
func (c *Client) WalletBalance() (int64, error) {
	var raw json.RawMessage
	if err := c.Call("getbalance", []any{}, &raw); err != nil {
		return 0, err
	}
	var num json.Number
	if err := json.Unmarshal(raw, &num); err != nil {
		return 0, err
	}
	return ParseNEX(num.String())
}

// SignedTx is a funded and signed payout that has not been broadcast.
// TxID is GetId. TxIdem is GetIdem. They are not interchangeable.
type SignedTx struct {
	TxID   string
	TxIdem string
	Raw    string
}

// TxView is what the node currently knows about a stored payout transaction.
// Conflict means an input is spent by a different confirmed transaction,
// or the wallet already records this transaction at a negative depth.
// OnChain means getrawtransaction found it in a block, so a missing wallet
// entry is not a conflicting spend.
type TxView struct {
	Payment
	InWallet  bool
	InMempool bool
	OnChain   bool
	Abandoned bool
	Conflict  bool
}

// CreatePayout builds and signs a payout with createrawtransaction,
// fundrawtransaction, and signrawtransaction. It does not broadcast.
func (c *Client) CreatePayout(address string, sats int64) (SignedTx, error) {
	if address == "" || sats <= 0 {
		return SignedTx{}, fmt.Errorf("nexa: payout output is empty")
	}
	var raw string
	outs := map[string]string{address: FormatNEX(sats)}
	if err := c.Call("createrawtransaction", []any{[]any{}, outs}, &raw); err != nil {
		return SignedTx{}, err
	}
	var funded struct {
		Hex string `json:"hex"`
	}
	if err := c.Call("fundrawtransaction", []any{raw, false}, &funded); err != nil {
		return SignedTx{}, err
	}
	if funded.Hex == "" {
		return SignedTx{}, fmt.Errorf("nexa: fundrawtransaction returned no hex")
	}
	var signed struct {
		Hex      string `json:"hex"`
		TxID     string `json:"txid"`
		TxIdem   string `json:"txidem"`
		Complete bool   `json:"complete"`
	}
	if err := c.Call("signrawtransaction", []any{funded.Hex}, &signed); err != nil {
		return SignedTx{}, err
	}
	if !signed.Complete || signed.Hex == "" {
		return SignedTx{}, fmt.Errorf("nexa: payout transaction was not fully signed")
	}
	if signed.TxID == "" || signed.TxIdem == "" {
		dec, err := c.decodeRaw(signed.Hex)
		if err != nil {
			return SignedTx{}, err
		}
		if signed.TxID == "" {
			signed.TxID = dec.TxID
		}
		if signed.TxIdem == "" {
			signed.TxIdem = dec.TxIdem
		}
	}
	if signed.TxID == "" || signed.TxIdem == "" {
		return SignedTx{}, fmt.Errorf("nexa: signed payout has no txid or txidem")
	}
	return SignedTx{TxID: signed.TxID, TxIdem: signed.TxIdem, Raw: signed.Hex}, nil
}

// SendRaw broadcasts a previously signed transaction. It does not build
// another one. sendrawtransaction returns an id; the stored GetId and
// GetIdem from signing stay the identifiers.
func (c *Client) SendRaw(raw string) error {
	if strings.TrimSpace(raw) == "" {
		return fmt.Errorf("nexa: empty raw transaction")
	}
	var id string
	return c.Call("sendrawtransaction", []any{raw}, &id)
}

// LookupTx reads gettransaction, then gettxpoolentry, then
// getrawtransaction. A miss of all three is not an error. When raw is set
// and the transaction is in none of those places, an input missing from
// the chain and from the txpool is a confirmed spend by a different
// transaction. getrawtransaction finding this same transaction in a block
// is not that spend.
func (c *Client) LookupTx(txid, txidem, raw string) (TxView, error) {
	var view TxView
	for _, id := range uniqueIDs(txid, txidem) {
		pay, found, abandoned, err := c.walletTx(id)
		if err != nil {
			return TxView{}, err
		}
		if !found {
			continue
		}
		view.Payment = pay
		view.InWallet = true
		// abandontransaction only succeeds for a transaction that is not
		// confirmed. A positive confirmation count is the payment, even
		// when a stale abandoned flag is still set.
		view.Abandoned = abandoned && pay.Confirmations <= 0
		// Negative confirmations are a conflict this wallet already lost.
		// walletconflicts on a transaction that still has zero or more
		// confirmations is the one that can still be mined, so it is not
		// a reason to pay again.
		if pay.Confirmations < 0 {
			view.Conflict = true
		}
		return view, nil
	}
	for _, id := range uniqueIDs(txid, txidem) {
		inPool, err := c.inTxPool(id)
		if err != nil {
			return TxView{}, err
		}
		if !inPool {
			continue
		}
		view.TxID = txid
		view.TxIdem = txidem
		view.InMempool = true
		return view, nil
	}
	for _, id := range uniqueIDs(txid, txidem) {
		pay, onChain, inPool, err := c.chainTx(id)
		if err != nil {
			return TxView{}, err
		}
		if !onChain && !inPool {
			continue
		}
		view.Payment = pay
		if view.TxID == "" {
			view.TxID = txid
		}
		if view.TxIdem == "" {
			view.TxIdem = txidem
		}
		view.OnChain = onChain
		view.InMempool = inPool
		return view, nil
	}
	if strings.TrimSpace(raw) == "" {
		return view, nil
	}
	spent, err := c.confirmedInputSpent(raw)
	if err != nil {
		return TxView{}, err
	}
	view.Conflict = spent
	view.TxID = txid
	view.TxIdem = txidem
	return view, nil
}

// FindComment is an informational wallet search. It is not used to decide
// a payment or a release: accounting entries are in wtxOrdered and not in
// mapWallet, so the scan can miss.
func (c *Client) FindComment(comment string) (Payment, bool, error) {
	return c.findComment(comment)
}

// LookupPayment reads gettransaction for a stored id. The comment is not
// searched. A payout is identified by the txid stored before broadcast.
func (c *Client) LookupPayment(comment, id string) (Payment, bool, error) {
	if id == "" {
		return Payment{}, false, nil
	}
	_ = comment
	return c.getPayment(id)
}

func (c *Client) getPayment(id string) (Payment, bool, error) {
	var raw json.RawMessage
	err := c.Call("gettransaction", []any{id, true}, &raw)
	if err != nil {
		if walletMiss(err) {
			return Payment{}, false, nil
		}
		return Payment{}, false, err
	}
	pay, err := decodePayment(raw)
	if err != nil {
		return Payment{}, false, err
	}
	if pay.TxID == "" && pay.TxIdem == "" {
		return Payment{}, false, fmt.Errorf("nexa: gettransaction returned no id")
	}
	return pay, true, nil
}

func uniqueIDs(ids ...string) []string {
	var out []string
	seen := map[string]bool{}
	for _, id := range ids {
		id = strings.TrimSpace(id)
		if id == "" || seen[strings.ToLower(id)] {
			continue
		}
		seen[strings.ToLower(id)] = true
		out = append(out, id)
	}
	return out
}

func (c *Client) walletTx(id string) (pay Payment, found, abandoned bool, err error) {
	var raw json.RawMessage
	if err = c.Call("gettransaction", []any{id, true}, &raw); err != nil {
		if walletMiss(err) {
			return Payment{}, false, false, nil
		}
		return Payment{}, false, false, err
	}
	var body struct {
		TxID          string `json:"txid"`
		TxIdem        string `json:"txidem"`
		Confirmations int64  `json:"confirmations"`
		Abandoned     bool   `json:"abandoned"`
	}
	if err = json.Unmarshal(raw, &body); err != nil {
		return Payment{}, false, false, err
	}
	if body.TxID == "" && body.TxIdem == "" {
		return Payment{}, false, false, fmt.Errorf("nexa: gettransaction returned no id")
	}
	return Payment{TxID: body.TxID, TxIdem: body.TxIdem, Confirmations: body.Confirmations}, true, body.Abandoned, nil
}

// chainTx reads getrawtransaction. A block hash, or a positive confirmation
// count, means the stored transaction itself is confirmed. That is not a
// spend by a different transaction.
func (c *Client) chainTx(id string) (pay Payment, onChain, inPool bool, err error) {
	var raw json.RawMessage
	if err = c.Call("getrawtransaction", []any{id, true}, &raw); err != nil {
		if poolMiss(err) {
			return Payment{}, false, false, nil
		}
		return Payment{}, false, false, err
	}
	var body struct {
		TxID          string `json:"txid"`
		TxIdem        string `json:"txidem"`
		Confirmations int64  `json:"confirmations"`
		BlockHash     string `json:"blockhash"`
	}
	if err = json.Unmarshal(raw, &body); err != nil {
		return Payment{}, false, false, err
	}
	if body.TxID == "" && body.TxIdem == "" {
		return Payment{}, false, false, fmt.Errorf("nexa: getrawtransaction returned no id")
	}
	pay = Payment{TxID: body.TxID, TxIdem: body.TxIdem, Confirmations: body.Confirmations}
	if body.BlockHash != "" || body.Confirmations > 0 {
		return pay, true, false, nil
	}
	return pay, false, true, nil
}

func (c *Client) inTxPool(id string) (bool, error) {
	var raw json.RawMessage
	err := c.Call("gettxpoolentry", []any{id}, &raw)
	if err != nil {
		if poolMiss(err) {
			return false, nil
		}
		return false, err
	}
	if len(raw) == 0 || string(raw) == "null" {
		return false, nil
	}
	return true, nil
}

func poolMiss(err error) bool {
	if walletMiss(err) {
		return true
	}
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "not in") || strings.Contains(s, "no such") || strings.Contains(s, "empty result")
}

// confirmedInputSpent reports whether an input of raw is gone from both
// the confirmed UTXO set and the txpool. The caller has already found that
// this transaction itself is not in the wallet and not in the txpool, so
// the spend belongs to a different confirmed transaction.
func (c *Client) confirmedInputSpent(raw string) (bool, error) {
	dec, err := c.decodeRaw(raw)
	if err != nil {
		return false, err
	}
	if len(dec.Vin) == 0 {
		return false, nil
	}
	for _, in := range dec.Vin {
		if in.Outpoint == "" {
			return false, fmt.Errorf("nexa: signed transaction input has no outpoint")
		}
		inChain, err := c.outputVisible(in.Outpoint, false)
		if err != nil {
			return false, err
		}
		if inChain {
			continue
		}
		inPool, err := c.outputVisible(in.Outpoint, true)
		if err != nil {
			return false, err
		}
		if !inPool {
			return true, nil
		}
	}
	return false, nil
}

func (c *Client) outputVisible(outpoint string, includePool bool) (bool, error) {
	var raw json.RawMessage
	err := c.Call("gettxout", []any{outpoint, -1, includePool}, &raw)
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "empty result") || walletMiss(err) {
			return false, nil
		}
		return false, err
	}
	return len(raw) > 0 && string(raw) != "null", nil
}

func (c *Client) decodeRaw(raw string) (decodedTx, error) {
	var dec decodedTx
	if err := c.Call("decoderawtransaction", []any{raw}, &dec); err != nil {
		return decodedTx{}, err
	}
	return dec, nil
}

type decodedTx struct {
	TxID   string `json:"txid"`
	TxIdem string `json:"txidem"`
	Vin    []struct {
		Outpoint string `json:"outpoint"`
	} `json:"vin"`
}

// walletPage is the item count passed to listtransactionsfrom. nexad
// counts wtxOrdered items, then emits zero or more JSON rows per item.
const walletPage = 1000

// walletItemMargin is added to getwalletinfo.txcount*3. txcount is
// mapWallet.size()/3, so txcount*3 is at most 2 below mapWallet.size().
// One extra page covers items that arrive after that call. mapWallet.size()
// upper-bounds wtxOrdered while every wallet item has a map entry. nexad
// does not report wtxOrdered.size(). A run of zero-row items longer than
// two pages that starts past this bound is treated as the end of the wallet.
const walletItemMargin = 2 + walletPage

// findComment walks the wallet from the oldest entry. listtransactions
// only returns a caller-chosen window of the newest rows, which is how a
// crashed payout used to be sent twice.
//
// nexad's listtransactionsfrom counts wtxOrdered items in from and count.
// ListTransactions then appends one JSON object per output. A change-only
// debit and a conflicted receive emit none, so a page can be shorter than
// the requested count while later items still exist. from advances by the
// requested item count, not by the JSON length. A short page is not the end.
//
// The scan stops only when two consecutive pages return zero rows and from
// is past txcount*3 plus walletItemMargin. If that bound cannot be read,
// the scan is unfinished and is not a miss. The final from is logged.
func (c *Client) findComment(comment string) (Payment, bool, error) {
	from := 0
	empty := 0
	for {
		if from > 5_000_000 {
			return c.finishScan(from, 0, Payment{}, false, fmt.Errorf("nexa: wallet scan did not finish"))
		}
		var raw json.RawMessage
		if err := c.Call("listtransactionsfrom", []any{"*", walletPage, from, true}, &raw); err != nil {
			return c.finishScan(from, 0, Payment{}, false, err)
		}
		var txs []walletTx
		if err := json.Unmarshal(raw, &txs); err != nil {
			return c.finishScan(from, 0, Payment{}, false, err)
		}
		for _, tx := range txs {
			if tx.Comment != comment {
				continue
			}
			return c.finishScan(from, 0, tx.payment(), true, nil)
		}
		if len(txs) == 0 {
			empty++
		} else {
			empty = 0
		}
		if empty >= 2 {
			bound, err := c.walletItemBound()
			if err != nil {
				return c.finishScan(from, 0, Payment{}, false, err)
			}
			if from > bound {
				return c.finishScan(from, bound, Payment{}, false, nil)
			}
		}
		next := from + walletPage
		if next <= from {
			return c.finishScan(from, 0, Payment{}, false, fmt.Errorf("nexa: listtransactionsfrom did not advance"))
		}
		from = next
	}
}

// walletItemBound is an upper bound on the wallet item count:
// getwalletinfo.txcount*3 plus walletItemMargin. A missing count is an
// error. It is not a completed scan.
func (c *Client) walletItemBound() (int, error) {
	var info struct {
		TxCount *int64 `json:"txcount"`
	}
	if err := c.Call("getwalletinfo", []any{}, &info); err != nil {
		return 0, fmt.Errorf("nexa: wallet item bound: %w", err)
	}
	if info.TxCount == nil || *info.TxCount < 0 {
		return 0, fmt.Errorf("nexa: getwalletinfo did not report txcount")
	}
	bound := *info.TxCount*3 + walletItemMargin
	if *info.TxCount > 0 && bound < *info.TxCount {
		return 0, fmt.Errorf("nexa: wallet item bound overflow")
	}
	return int(bound), nil
}

func (c *Client) finishScan(from, bound int, pay Payment, found bool, err error) (Payment, bool, error) {
	logger := c.Log
	if logger == nil {
		logger = log.Default()
	}
	switch {
	case err != nil:
		logger.Printf("nexa: wallet scan unfinished from=%d: %v", from, err)
	case found:
		logger.Printf("nexa: wallet scan found from=%d", from)
	default:
		logger.Printf("nexa: wallet scan miss from=%d bound=%d", from, bound)
	}
	return pay, found, err
}

// MedianTime is the node's median time past, from getblockchaininfo.
// Fork decisions compare this with an operator override. They do not
// compare it with the machine clock.
func (c *Client) MedianTime() (int64, error) {
	var info struct {
		MedianTime int64 `json:"mediantime"`
	}
	if err := c.Call("getblockchaininfo", []any{}, &info); err != nil {
		return 0, err
	}
	if info.MedianTime <= 0 {
		return 0, fmt.Errorf("nexa: node did not report mediantime")
	}
	return info.MedianTime, nil
}

type walletTx struct {
	TxID          string `json:"txid"`
	TxIdem        string `json:"txidem"`
	Comment       string `json:"comment"`
	Confirmations int64  `json:"confirmations"`
}

func (t walletTx) payment() Payment {
	return Payment{TxID: t.TxID, TxIdem: t.TxIdem, Confirmations: t.Confirmations}
}

func decodePayment(raw json.RawMessage) (Payment, error) {
	var tx walletTx
	if err := json.Unmarshal(raw, &tx); err != nil {
		return Payment{}, err
	}
	return tx.payment(), nil
}

func walletMiss(err error) bool {
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "not found") || strings.Contains(s, "invalid or non-wallet")
}

func paysAddress(addresses []string, want string) bool {
	for _, addr := range addresses {
		if strings.EqualFold(addr, want) {
			return true
		}
	}
	return false
}

// Unlock unlocks the wallet for timeout seconds when a passphrase is set.
func (c *Client) Unlock(passphrase string, timeout int) error {
	if passphrase == "" {
		return nil
	}
	return c.Call("walletpassphrase", []any{passphrase, timeout}, nil)
}

// Lock locks the wallet. A missing passphrase means the wallet stays as it was.
func (c *Client) Lock(passphrase string) error {
	if passphrase == "" {
		return nil
	}
	return c.Call("walletlock", []any{}, nil)
}
