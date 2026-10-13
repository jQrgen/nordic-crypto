// Package web builds the static pool site. English is at the root and every
// other site language is a subdirectory, the same layout as nordiccrypto.no.
package web

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"os"
	"path/filepath"
)

//go:embed locales.json
var localeJSON []byte

//go:embed static/pool.css
var css []byte

//go:embed static/pool.js
var script []byte

// HeroEN is the English hero, byte for byte.
const HeroEN = "Nordic Crypto Nexa Pool – 1% fee that funds independent Nordic crypto journalism"

// APIDownEN is the English message shown when the stats API does not answer.
const APIDownEN = "The pool API is not responding."

// Languages is the site language list, in the same order as i18n.ALL_LANGS.
var Languages = []Lang{
	{"en", "English", false},
	{"nn", "Nynorsk", false},
	{"nb", "Bokmål", false},
	{"sv", "Svenska", false},
	{"da", "Dansk", false},
	{"fi", "Suomi", false},
	{"is", "Íslenska", false},
	{"zh", "中文", false},
	{"hi", "हिन्दी", false},
	{"es", "Español", false},
	{"fr", "Français", false},
	{"ar", "العربية", true},
	{"bn", "বাংলা", false},
	{"pt", "Português", false},
	{"ru", "Русский", false},
	{"ur", "اردو", true},
	{"id", "Bahasa Indonesia", false},
	{"de", "Deutsch", false},
	{"ja", "日本語", false},
	{"sw", "Kiswahili", false},
	{"mr", "मराठी", false},
	{"fa", "فارسی", true},
	{"uk", "Українська", false},
}

// Lang is one published language.
type Lang struct {
	Code string
	Name string
	RTL  bool
}

var required = []string{
	"title", "description", "hero", "heroLink",
	"navStart", "navStatus", "navStats", "navTerms", "navAbout",
	"startTitle", "startLead", "stratumLabel", "copy", "copied", "startUser", "startWallet", "wally", "examples",
	"statusTitle", "hashrate", "miners", "network", "share", "since", "blocks",
	"loading", "apiDown", "nodeDown", "noBlock", "emptyBlocks", "liveLine",
	"statsTitle", "statsLead", "addressLabel", "lookup",
	"statsHash", "statsShares", "statsBalance", "statsImmature", "statsPaid", "statsPayouts",
	"statsEmpty", "statsBad", "statsNoPay", "valid", "invalid",
	"statusImmature", "statusMature", "statusOrphan", "blockLink",
	"termsTitle", "termFee", "termPplns", "termMin", "termFreq",
	"aboutTitle", "aboutWho", "aboutFee", "aboutHow",
	"newsletter", "langLabel",
}

var fontFiles = []string{
	"CormorantGaramond-SemiBold.ttf",
	"CormorantGaramond-Bold-latin.woff2",
	"CormorantGaramond-Bold-latin-ext.woff2",
	"SchibstedGrotesk-Regular.ttf",
	"SchibstedGrotesk-Medium.ttf",
	"SchibstedGrotesk-Bold-latin.woff2",
	"SchibstedGrotesk-Bold-latin-ext.woff2",
	"IBMPlexMono-Medium-latin.woff2",
	"IBMPlexMono-Medium-latin-ext.woff2",
	"OFL.txt",
}

// Locales parses the embedded translations.
func Locales() (map[string]map[string]string, error) {
	var all map[string]map[string]string
	if err := json.Unmarshal(localeJSON, &all); err != nil {
		return nil, err
	}
	if all["en"]["hero"] != HeroEN {
		return nil, fmt.Errorf("web: English hero drifted")
	}
	if all["en"]["apiDown"] != APIDownEN {
		return nil, fmt.Errorf("web: English API message drifted")
	}
	for _, lang := range Languages {
		table := all[lang.Code]
		if table == nil {
			return nil, fmt.Errorf("web: missing language %s", lang.Code)
		}
		for _, key := range required {
			if table[key] == "" {
				return nil, fmt.Errorf("web: %s.%s is empty", lang.Code, key)
			}
		}
	}
	return all, nil
}

// Generate writes the static site into dir. assets is the repository assets
// directory (the one that contains brand/ and fonts/).
func Generate(dir, assets string) error {
	locales, err := Locales()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(dir, "fonts"), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "pool.css"), css, 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "pool.js"), script, 0o644); err != nil {
		return err
	}
	shield, err := os.ReadFile(filepath.Join(assets, "brand", "shield.svg"))
	if err != nil {
		return fmt.Errorf("web: shield: %w", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "shield.svg"), shield, 0o644); err != nil {
		return err
	}
	for _, name := range fontFiles {
		if err := copyFile(filepath.Join(assets, "fonts", name), filepath.Join(dir, "fonts", name)); err != nil {
			return err
		}
	}
	tpl, err := template.New("page").Parse(pageTpl)
	if err != nil {
		return err
	}
	for _, lang := range Languages {
		prefix := ""
		hrefRoot := ""
		out := filepath.Join(dir, "index.html")
		if lang.Code != "en" {
			prefix = "../"
			hrefRoot = "../"
			out = filepath.Join(dir, lang.Code, "index.html")
			if err := os.MkdirAll(filepath.Dir(out), 0o755); err != nil {
				return err
			}
		}
		raw, err := json.Marshal(jsText(locales[lang.Code]))
		if err != nil {
			return err
		}
		var buf bytes.Buffer
		dirAttr := "ltr"
		if lang.RTL {
			dirAttr = "rtl"
		}
		err = tpl.Execute(&buf, map[string]any{
			"Lang": lang.Code, "Dir": dirAttr, "Prefix": prefix,
			"C":     locales[lang.Code],
			"Langs": langLinks(lang.Code, hrefRoot),
		})
		if err != nil {
			return err
		}
		if err := os.WriteFile(out, buf.Bytes(), 0o644); err != nil {
			return err
		}
		body := append([]byte("window.POOL_TEXT = "), raw...)
		body = append(body, ";\n"...)
		if err := os.WriteFile(filepath.Join(filepath.Dir(out), "pool-text.js"), body, 0o644); err != nil {
			return err
		}
	}
	return nil
}

func jsText(c map[string]string) map[string]string {
	keys := []string{
		"copy", "copied", "loading", "apiDown", "nodeDown", "noBlock", "emptyBlocks",
		"since", "liveLine", "blockLink", "statsHash", "statsShares", "statsBalance",
		"statsImmature", "statsPaid", "statsPayouts", "statsEmpty", "statsBad", "statsNoPay",
		"valid", "invalid", "statusImmature", "statusMature", "statusOrphan",
	}
	out := make(map[string]string, len(keys))
	for _, key := range keys {
		out[key] = c[key]
	}
	return out
}

type langLink struct {
	Code, Name, Href string
	Current          bool
}

func langLinks(current, hrefRoot string) []langLink {
	out := make([]langLink, len(Languages))
	for i, lang := range Languages {
		href := hrefRoot
		if lang.Code != "en" {
			href = hrefRoot + lang.Code + "/"
		}
		if href == "" {
			href = "/"
		}
		out[i] = langLink{Code: lang.Code, Name: lang.Name, Href: href, Current: lang.Code == current}
	}
	return out
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Close()
}

const pageTpl = `<!DOCTYPE html>
<html lang="{{.Lang}}" dir="{{.Dir}}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{.C.title}}</title>
<meta name="description" content="{{.C.description}}">
<link rel="icon" href="{{.Prefix}}shield.svg" type="image/svg+xml">
<link rel="stylesheet" href="{{.Prefix}}pool.css">
</head>
<body>
<header class="site">
  <div class="wrap bar">
    <a class="brand" href="https://nordiccrypto.no/"><img src="{{.Prefix}}shield.svg" width="36" height="36" alt=""> Nordic Crypto</a>
    <nav class="sections" aria-label="{{.C.title}}">
      <a href="#start">{{.C.navStart}}</a>
      <a href="#status">{{.C.navStatus}}</a>
      <a href="#stats">{{.C.navStats}}</a>
      <a href="#terms">{{.C.navTerms}}</a>
      <a href="#about">{{.C.navAbout}}</a>
    </nav>
  </div>
  <nav class="langs wrap" aria-label="{{.C.langLabel}}">
    {{range .Langs}}<a href="{{.Href}}" lang="{{.Code}}"{{if .Current}} aria-current="page"{{end}}>{{.Name}}</a> {{end}}
  </nav>
</header>
<main>
  <section class="hero">
    <div class="wrap">
      <p class="kicker">Nexa</p>
      <h1>{{.C.hero}}</h1>
      <p><a href="https://nordiccrypto.no/budget/">{{.C.heroLink}}</a></p>
    </div>
  </section>
  <section id="start">
    <div class="wrap">
      <h2>{{.C.startTitle}}</h2>
      <hr class="rule">
      <p class="lead">{{.C.startLead}}</p>
      <p>{{.C.stratumLabel}}</p>
      <div class="urlrow">
        <code id="stratum">stratum+tcp://pool.nordiccrypto.no:3333</code>
        <button type="button" id="copy">{{.C.copy}}</button>
      </div>
      <p>{{.C.startUser}}</p>
      <p>{{.C.startWallet}} <a href="https://wallywallet.org/" rel="noopener">{{.C.wally}}</a></p>
      <h3>{{.C.examples}}</h3>
      <ul class="examples">
        <li><p class="miner">lolMiner</p><pre>lolMiner --algo NEXA --pool stratum+tcp://pool.nordiccrypto.no:3333 --user nexa:ADDRESS</pre></li>
        <li><p class="miner">BzMiner</p><pre>bzminer -a nexa -p stratum+tcp://pool.nordiccrypto.no:3333 -w nexa:ADDRESS</pre></li>
        <li><p class="miner">Rigel</p><pre>rigel -a nexapow -o stratum+tcp://pool.nordiccrypto.no:3333 -u nexa:ADDRESS</pre></li>
        <li><p class="miner">SRBMiner</p><pre>SRBMiner-MULTI --algorithm nexa --pool stratum+tcp://pool.nordiccrypto.no:3333 --wallet nexa:ADDRESS</pre></li>
      </ul>
    </div>
  </section>
  <section id="status">
    <div class="wrap">
      <h2>{{.C.statusTitle}}</h2>
      <hr class="rule">
      <p id="status-msg" role="status"></p>
      <dl class="figures" id="figures" hidden>
        <div><dt>{{.C.hashrate}}</dt><dd id="pool-hash"></dd></div>
        <div><dt>{{.C.miners}}</dt><dd id="miner-count"></dd></div>
        <div><dt>{{.C.network}}</dt><dd id="net-hash"></dd></div>
        <div><dt>{{.C.share}}</dt><dd id="pool-share"></dd></div>
      </dl>
      <p id="since"></p>
      <p id="live-line"></p>
      <h3>{{.C.blocks}}</h3>
      <ul id="blocks"></ul>
      <noscript><p class="notice">{{.C.apiDown}}</p></noscript>
    </div>
  </section>
  <section id="stats">
    <div class="wrap">
      <h2>{{.C.statsTitle}}</h2>
      <hr class="rule">
      <p class="lead">{{.C.statsLead}}</p>
      <form id="lookup">
        <label for="addr">{{.C.addressLabel}}</label>
        <div class="urlrow">
          <input id="addr" name="address" autocomplete="off" spellcheck="false">
          <button type="submit">{{.C.lookup}}</button>
        </div>
      </form>
      <div id="mine"></div>
    </div>
  </section>
  <section id="terms">
    <div class="wrap">
      <h2>{{.C.termsTitle}}</h2>
      <hr class="rule">
      <ul>
        <li>{{.C.termFee}}</li>
        <li>{{.C.termPplns}}</li>
        <li>{{.C.termMin}}</li>
        <li>{{.C.termFreq}}</li>
      </ul>
    </div>
  </section>
  <section id="about">
    <div class="wrap about">
      <h2>{{.C.aboutTitle}}</h2>
      <hr class="rule">
      <p>{{.C.aboutWho}}</p>
      <p>{{.C.aboutFee}}</p>
      <p>{{.C.aboutHow}}</p>
    </div>
  </section>
</main>
<footer class="site-foot">
  <div class="wrap">
    <ul class="social">
      <li><a href="https://nordiccrypto.no/">Nordic Crypto</a></li>
      <li><a href="https://nordiccrypto.no/budget/">{{.C.heroLink}}</a></li>
      <li><a href="https://t.me/nordiccryptochat" rel="noopener">Telegram</a></li>
      <li><a href="https://x.com/nordiccryptobot" rel="noopener">X @nordiccryptobot</a></li>
      <li><a href="https://github.com/jQrgen/nordic-crypto" rel="noopener">GitHub</a></li>
      <li><a href="https://nordiccrypto.no/newsletter/">{{.C.newsletter}}</a></li>
      <li><a href="https://nordiccrypto.no/rss.xml">RSS</a></li>
      <li><a href="https://testflight.apple.com/join/nQ2fpjZn" rel="noopener">TestFlight</a></li>
    </ul>
  </div>
</footer>
<script src="pool-text.js"></script>
<script src="{{.Prefix}}pool.js"></script>
</body>
</html>
`
