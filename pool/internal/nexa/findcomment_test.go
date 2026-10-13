package nexa

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestFindCommentMissesACommentOutsideTheLatest200(t *testing.T) {
	const want = "nexapool:0123456789abcdef0123456789abcdef"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body := new(strings.Builder)
		body.WriteString(`[`)
		// Newest-first, matching listtransactions before its final reverse.
		// The payout comment sits just past the 200 entries the client asks for.
		for i := 0; i < 200; i++ {
			if i > 0 {
				body.WriteByte(',')
			}
			fmt.Fprintf(body, `{"txid":"new-%d","comment":"other-%d"}`, i, i)
		}
		body.WriteString(`]`)
		fmtResult(w, body.String())
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	// The node still has the comment, one entry older than the window.
	// FindComment never asks for it.
	txid, found, err := c.FindComment(want)
	if err != nil {
		t.Fatal(err)
	}
	if found || txid != "" {
		t.Fatalf("comment outside the window was returned: %q found %v", txid, found)
	}
}

func TestFindCommentReadsTheCommentField(t *testing.T) {
	const want = "nexapool:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(raw), `"listtransactions"`) {
			t.Errorf("method %s", raw)
		}
		fmtResult(w, `[{"txid":"real-txid","txidem":"idem-value","comment":"`+want+`"}]`)
	}))
	defer srv.Close()
	c, _ := NewClient(srv.URL, "u", "p", "")
	txid, found, err := c.FindComment(want)
	if err != nil || !found || txid != "real-txid" {
		t.Fatalf("txid %q found %v err %v", txid, found, err)
	}
}
