package nexa

import (
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"
)

// ReadPrivateFile reads a secret file. It refuses a symlink, anything that
// is not a regular file, and any mode that grants group or world access.
// The contents are never logged by the caller.
func ReadPrivateFile(path string) ([]byte, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, err
	}
	if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() {
		return nil, fmt.Errorf("nexa: %s must be a regular file, not a symlink", path)
	}
	if info.Mode().Perm()&0o077 != 0 {
		return nil, fmt.Errorf("nexa: %s is readable by group or world (mode %o)", path, info.Mode().Perm())
	}
	return os.ReadFile(path)
}

// LoopbackHost reports whether host is a loopback name or address.
func LoopbackHost(host string) bool {
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// RequireLoopbackURL rejects a node URL that is not http(s) on loopback,
// or that embeds credentials. The RPC cookie must not leave the machine,
// including by a redirect.
func RequireLoopbackURL(rawURL string) error {
	u, err := url.Parse(rawURL)
	if err != nil || u.Host == "" {
		return fmt.Errorf("nexa: node url is not absolute")
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("nexa: node url must be http or https")
	}
	if u.User != nil {
		return fmt.Errorf("nexa: node url must not embed credentials")
	}
	if !LoopbackHost(u.Hostname()) {
		return fmt.Errorf("nexa: node url must stay on localhost")
	}
	return nil
}
