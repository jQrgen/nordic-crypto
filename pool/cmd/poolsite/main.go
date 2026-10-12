package main

import (
	"flag"
	"log"
	"os"
	"path/filepath"

	"github.com/jQrgen/nordic-crypto/pool/web"
)

func main() {
	out := flag.String("out", "web/public", "directory for the static site")
	assets := flag.String("assets", "", "path to the repository assets directory")
	flag.Parse()
	dir := *assets
	if dir == "" {
		for _, candidate := range []string{"../assets", "assets", "../../assets"} {
			if _, err := os.Stat(filepath.Join(candidate, "brand", "shield.svg")); err == nil {
				dir = candidate
				break
			}
		}
	}
	if dir == "" {
		log.Fatal("assets directory not found; pass -assets")
	}
	if err := web.Generate(*out, dir); err != nil {
		log.Fatal(err)
	}
	log.Printf("wrote %s", *out)
}
