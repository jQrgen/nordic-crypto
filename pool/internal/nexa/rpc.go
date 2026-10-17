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
// TxID is GetId and is informational. TxIdem is GetIdem. Inputs are the
// prevout hashes the transaction spends. They are not interchangeable.
type SignedTx struct {
	TxID   string
	TxIdem string
	Raw    string
	Inputs []string
}

// TxView is what the node currently knows about a stored txidem.
// Conflict means an input is spent by a transaction with a different
// txidem. SpendConfs is that spender's confirmation count. A confirmed
// transaction with this txidem is the payment, whatever its txid is.
// OnChain means getrawtransaction found this txidem in a block.
// gettransaction does not report abandoned, and this view does not either.
type TxView struct {
	Payment
	InWallet    bool
	InMempool   bool
	OnChain     bool
	Conflict    bool
	SpendTxIdem string
	SpendConfs  int64
}

// CreatePayout selects coins itself, skipping avoid, then signs with
// createrawtransaction, fundrawtransaction, and signrawtransaction.
// fundrawtransaction's second argument is includeWatching, not a lock,
// so it is omitted. The selected outpoints are locked with lockunspent
// false immediately after funding and before signing. It does not broadcast.
func (c *Client) CreatePayout(address string, sats int64, avoid []string) (SignedTx, error) {
	if address == "" || sats <= 0 {
		return SignedTx{}, fmt.Errorf("nexa: payout output is empty")
	}
	if err := c.LockOutpoints(avoid, false); err != nil {
		return SignedTx{}, err
	}
	skip := outpointSet(avoid)
	coins, err := c.listUnspent()
	if err != nil {
		return SignedTx{}, err
	}
	var inputs []any
	var sum int64
	for _, coin := range coins {
		if skip[strings.ToLower(coin.Outpoint)] {
			continue
		}
		inputs = append(inputs, map[string]string{
			"outpoint": coin.Outpoint,
			"amount":   FormatNEX(coin.Amount),
		})
		sum += coin.Amount
		if sum >= sats {
			break
		}
	}
	if sum < sats || len(inputs) == 0 {
		return SignedTx{}, fmt.Errorf("nexa: not enough unlocked coins")
	}
	var raw string
	outs := map[string]string{address: FormatNEX(sats)}
	if err := c.Call("createrawtransaction", []any{inputs, outs}, &raw); err != nil {
		return SignedTx{}, err
	}
	var funded struct {
		Hex string `json:"hex"`
	}
	if err := c.Call("fundrawtransaction", []any{raw}, &funded); err != nil {
		return SignedTx{}, err
	}
	if funded.Hex == "" {
		return SignedTx{}, fmt.Errorf("nexa: fundrawtransaction returned no hex")
	}
	dec, err := c.decodeRaw(funded.Hex)
	if err != nil {
		return SignedTx{}, err
	}
	selected, err := fundedInputs(dec, skip)
	if err != nil {
		return SignedTx{}, err
	}
	if err := c.LockOutpoints(selected, false); err != nil {
		return SignedTx{}, err
	}
	var signed struct {
		Hex      string `json:"hex"`
		TxID     string `json:"txid"`
		TxIdem   string `json:"txidem"`
		Complete bool   `json:"complete"`
	}
	if err := c.Call("signrawtransaction", []any{funded.Hex}, &signed); err != nil {
		_ = c.LockOutpoints(selected, true)
		return SignedTx{}, err
	}
	if !signed.Complete || signed.Hex == "" {
		_ = c.LockOutpoints(selected, true)
		return SignedTx{}, fmt.Errorf("nexa: payout transaction was not fully signed")
	}
	if signed.TxID == "" || signed.TxIdem == "" {
		decSigned, err := c.decodeRaw(signed.Hex)
		if err != nil {
			_ = c.LockOutpoints(selected, true)
			return SignedTx{}, err
		}
		if signed.TxID == "" {
			signed.TxID = decSigned.TxID
		}
		if signed.TxIdem == "" {
			signed.TxIdem = decSigned.TxIdem
		}
	}
	if signed.TxID == "" || signed.TxIdem == "" {
		_ = c.LockOutpoints(selected, true)
		return SignedTx{}, fmt.Errorf("nexa: signed payout has no txid or txidem")
	}
	return SignedTx{TxID: signed.TxID, TxIdem: signed.TxIdem, Raw: signed.Hex, Inputs: selected}, nil
}

// LockOutpoints calls lockunspent. unlock false locks. An empty list
// does not call the node. The node's lock set is memory only.
func (c *Client) LockOutpoints(outpoints []string, unlock bool) error {
	var ids []string
	seen := map[string]bool{}
	for _, op := range outpoints {
		op = strings.TrimSpace(op)
		if op == "" || seen[strings.ToLower(op)] {
			continue
		}
		seen[strings.ToLower(op)] = true
		ids = append(ids, op)
	}
	if len(ids) == 0 {
		return nil
	}
	var raw json.RawMessage
	return c.Call("lockunspent", []any{unlock, ids}, &raw)
}

func fundedInputs(dec decodedTx, skip map[string]bool) ([]string, error) {
	var selected []string
	seen := map[string]bool{}
	for _, in := range dec.Vin {
		op := strings.TrimSpace(in.Outpoint)
		if op == "" {
			return nil, fmt.Errorf("nexa: funded input has no outpoint")
		}
		if skip[strings.ToLower(op)] {
			return nil, fmt.Errorf("nexa: funded input %s is already reserved", op)
		}
		if seen[strings.ToLower(op)] {
			continue
		}
		seen[strings.ToLower(op)] = true
		selected = append(selected, op)
	}
	if len(selected) == 0 {
		return nil, fmt.Errorf("nexa: funded transaction has no inputs")
	}
	return selected, nil
}

func outpointSet(ids []string) map[string]bool {
	m := map[string]bool{}
	for _, id := range ids {
		id = strings.ToLower(strings.TrimSpace(id))
		if id != "" {
			m[id] = true
		}
	}
	return m
}

type spendable struct {
	Outpoint string
	Amount   int64
}

func (c *Client) listUnspent() ([]spendable, error) {
	var raw json.RawMessage
	if err := c.Call("listunspent", []any{int64(1)}, &raw); err != nil {
		return nil, err
	}
	var rows []struct {
		Outpoint string          `json:"outpoint"`
		Amount   json.RawMessage `json:"amount"`
	}
	if err := json.Unmarshal(raw, &rows); err != nil {
		return nil, err
	}
	var out []spendable
	for _, row := range rows {
		if strings.TrimSpace(row.Outpoint) == "" {
			continue
		}
		amt, err := parseAmount(row.Amount)
		if err != nil {
			return nil, err
		}
		if amt <= 0 {
			continue
		}
		out = append(out, spendable{Outpoint: row.Outpoint, Amount: amt})
	}
	return out, nil
}

func parseAmount(raw json.RawMessage) (int64, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return 0, fmt.Errorf("nexa: empty amount")
	}
	return ParseNEX(strings.Trim(string(raw), `"`))
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
// getrawtransaction, all keyed by txidem. txid is not a lookup key.
// A miss of all three is not an error and is not a conflict. A result
// with zero or more confirmations is this payment, even when its txid
// is not the one that was stored. Negative confirmations are a conflict
// only when walletconflicts names a transaction with a different txidem
// and a positive confirmation count. A missing UTXO is not that proof.
func (c *Client) LookupTx(txidem string) (TxView, error) {
	var view TxView
	txidem = strings.TrimSpace(txidem)
	if txidem == "" {
		return view, nil
	}
	pay, found, conflicts, err := c.walletTx(txidem)
	if err != nil {
		return TxView{}, err
	}
	if found {
		view.Payment = pay
		if view.TxIdem == "" {
			view.TxIdem = txidem
		}
		if pay.Confirmations >= 0 {
			view.InWallet = true
			return view, nil
		}
		spendID, spendConfs, ok, err := c.otherSpender(txidem, conflicts)
		if err != nil {
			return TxView{}, err
		}
		if ok {
			view.Conflict = true
			view.SpendTxIdem = spendID
			view.SpendConfs = spendConfs
		}
		return view, nil
	}
	inPool, err := c.inTxPool(txidem)
	if err != nil {
		return TxView{}, err
	}
	if inPool {
		view.TxIdem = txidem
		view.InMempool = true
		return view, nil
	}
	pay, onChain, inPool, err := c.chainTx(txidem)
	if err != nil {
		return TxView{}, err
	}
	if !onChain && !inPool {
		return view, nil
	}
	view.Payment = pay
	if view.TxIdem == "" {
		view.TxIdem = txidem
	}
	view.OnChain = onChain
	view.InMempool = inPool
	return view, nil
}

// otherSpender returns the different txidem among conflicts that has the
// most confirmations. A conflict with this same txidem is a malleated
// copy of the stored payment and is ignored. A non-positive depth is not
// a spend that can release coins.
func (c *Client) otherSpender(ours string, conflicts []string) (string, int64, bool, error) {
	var best string
	var bestConfs int64
	for _, id := range conflicts {
		id = strings.TrimSpace(id)
		if id == "" {
			continue
		}
		pay, found, _, err := c.walletTx(id)
		if err != nil {
			return "", 0, false, err
		}
		if !found || pay.TxIdem == "" || strings.EqualFold(pay.TxIdem, ours) || pay.Confirmations <= 0 {
			continue
		}
		if pay.Confirmations > bestConfs {
			best = pay.TxIdem
			bestConfs = pay.Confirmations
		}
	}
	if best == "" {
		return "", 0, false, nil
	}
	return best, bestConfs, true, nil
}

// FindComment is an informational wallet search. It is not used to decide
// a payment or a release: accounting entries are in wtxOrdered and not in
// mapWallet, so the scan can miss.
func (c *Client) FindComment(comment string) (Payment, bool, error) {
	return c.findComment(comment)
}

// LookupPayment reads gettransaction for a stored id. The comment is not
// searched. A payout is identified by the txidem stored before broadcast.
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

func (c *Client) walletTx(id string) (pay Payment, found bool, conflicts []string, err error) {
	var raw json.RawMessage
	if err = c.Call("gettransaction", []any{id, true}, &raw); err != nil {
		if walletMiss(err) {
			return Payment{}, false, nil, nil
		}
		return Payment{}, false, nil, err
	}
	var body struct {
		TxID            string   `json:"txid"`
		TxIdem          string   `json:"txidem"`
		Confirmations   int64    `json:"confirmations"`
		WalletConflicts []string `json:"walletconflicts"`
	}
	if err = json.Unmarshal(raw, &body); err != nil {
		return Payment{}, false, nil, err
	}
	if body.TxID == "" && body.TxIdem == "" {
		return Payment{}, false, nil, fmt.Errorf("nexa: gettransaction returned no id")
	}
	return Payment{TxID: body.TxID, TxIdem: body.TxIdem, Confirmations: body.Confirmations}, true, body.WalletConflicts, nil
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
