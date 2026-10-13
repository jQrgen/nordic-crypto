package nexa

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
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
		want := strings.ToLower(c.PoolAddress)
		for _, out := range body.Tx[0].Vout {
			if want == "" || !paysAddress(out.ScriptPubKey.Addresses, want) {
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

// LookupPayment finds a payout by a stored txid or txidem, then by comment.
// found is false only after gettransaction misses and listtransactionsfrom
// has been read to the end of the wallet. There is no fixed row window.
// The returned TxID is GetId. A lookup error means the search did not
// finish; it is not evidence that the send is absent.
func (c *Client) LookupPayment(comment, id string) (Payment, bool, error) {
	if id != "" {
		pay, found, err := c.getPayment(id)
		if err != nil {
			return Payment{}, false, err
		}
		if found {
			return pay, true, nil
		}
	}
	if comment == "" {
		return Payment{}, false, nil
	}
	return c.findComment(comment)
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

// findComment walks the wallet from the oldest entry. listtransactions
// only returns a caller-chosen window of the newest rows, which is how a
// crashed payout used to be sent twice. listtransactionsfrom pages until
// a short page, so a comment cannot scroll out of view.
func (c *Client) findComment(comment string) (Payment, bool, error) {
	const page = 1000
	from := 0
	for {
		var raw json.RawMessage
		if err := c.Call("listtransactionsfrom", []any{"*", page, from, true}, &raw); err != nil {
			return Payment{}, false, err
		}
		var txs []walletTx
		if err := json.Unmarshal(raw, &txs); err != nil {
			return Payment{}, false, err
		}
		for _, tx := range txs {
			if tx.Comment != comment {
				continue
			}
			pay := tx.payment()
			return pay, true, nil
		}
		if len(txs) < page {
			return Payment{}, false, nil
		}
		next := from + len(txs)
		if next <= from {
			return Payment{}, false, fmt.Errorf("nexa: listtransactionsfrom did not advance")
		}
		from = next
	}
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
