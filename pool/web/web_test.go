package web

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestGenerateAllLanguages(t *testing.T) {
	dir := t.TempDir()
	if err := Generate(dir, filepath.Join("..", "..", "assets")); err != nil {
		t.Fatal(err)
	}
	en, err := os.ReadFile(filepath.Join(dir, "index.html"))
	if err != nil {
		t.Fatal(err)
	}
	page := string(en)
	if !strings.Contains(page, HeroEN) {
		t.Fatal("english hero missing")
	}
	if !strings.Contains(page, APIDownEN) {
		t.Fatal("api message missing")
	}
	for _, needle := range []string{
		"stratum+tcp://pool.nordiccrypto.no:3333",
		"https://nordiccrypto.no/budget/",
		"https://wallywallet.org/",
		"https://x.com/nordiccryptobot",
		"https://t.me/nordiccryptochat",
		"https://github.com/jQrgen/nordic-crypto",
		"https://nordiccrypto.no/newsletter/",
		"https://nordiccrypto.no/rss.xml",
		"https://testflight.apple.com/join/nQ2fpjZn",
		"lolMiner --algo NEXA",
		"bzminer -a nexa",
		"rigel -a nexapow",
		"SRBMiner-MULTI --algorithm nexa",
		`id="copy"`,
		`id="figures" hidden`,
		"shield.svg",
	} {
		if !strings.Contains(page, needle) {
			t.Fatalf("missing %s", needle)
		}
	}
	if strings.Contains(page, "TH/s") || strings.Contains(page, "mailto:") || strings.Contains(page, "1.23") {
		t.Fatal("page contains a fabricated figure or an email address")
	}
	if strings.Contains(page, "xcryptonordic") {
		t.Fatal("old X account is still linked")
	}
	if strings.Contains(page, "unsafe-inline") || strings.Contains(page, "window.POOL_TEXT") {
		t.Fatal("page still embeds an inline script")
	}
	for _, tag := range regexp.MustCompile(`(?i)<script\b[^>]*>`).FindAllString(page, -1) {
		if !strings.Contains(tag, " src=") {
			t.Fatalf("inline script %s", tag)
		}
	}
	text, err := os.ReadFile(filepath.Join(dir, "pool-text.js"))
	if err != nil || !strings.Contains(string(text), "window.POOL_TEXT") {
		t.Fatalf("pool-text.js: %v", err)
	}
	csp, err := os.ReadFile(filepath.Join("..", "deploy", "nginx-pool.nordiccrypto.no.conf"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(csp), "unsafe-inline") {
		t.Fatal("content security policy allows inline scripts")
	}
	bad := regexp.MustCompile(`(?:^|[^0-9A-Za-z_-])(?:AI|KI)(?:[^0-9A-Za-z_-]|$)`)
	for _, code := range []string{"nn", "nb"} {
		raw, err := os.ReadFile(filepath.Join(dir, code, "index.html"))
		if err != nil {
			t.Fatal(err)
		}
		if bad.Find(raw) != nil {
			t.Fatalf("%s contains a forbidden word: %s", code, bad.Find(raw))
		}
		if !strings.Contains(string(raw), "stratum+tcp://pool.nordiccrypto.no:3333") {
			t.Fatalf("%s missing stratum url", code)
		}
	}
	ar, err := os.ReadFile(filepath.Join(dir, "ar", "index.html"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(ar), `dir="rtl"`) {
		t.Fatal("arabic is not right to left")
	}
	for _, lang := range Languages {
		path := filepath.Join(dir, "index.html")
		if lang.Code != "en" {
			path = filepath.Join(dir, lang.Code, "index.html")
		}
		if _, err := os.Stat(path); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := os.Stat(filepath.Join(dir, "fonts", "OFL.txt")); err != nil {
		t.Fatal(err)
	}
}
