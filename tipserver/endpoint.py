#!/usr/bin/env python3
"""Prints the current public tip endpoint: tipserver/config.json -> public_endpoint (fixed hostname, takes precedence)
or else the quick-tunnel URL in tipserver/tunnel-url.txt (written by tipserver/tunnel.sh). Empty output = none."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
def current():
    try: cfg = json.load(open(os.path.join(H, "config.json"))) or {}
    except Exception: cfg = {}
    fixed = cfg.get("public_endpoint")
    if fixed: return fixed.strip().rstrip("/"), "fixed"
    if not cfg.get("quick_tunnel"): return "", None
    try: u = open(os.path.join(H, "tunnel-url.txt")).read().strip().rstrip("/")
    except FileNotFoundError: u = ""
    return (u, "quick-tunnel") if u.startswith("https://") else ("", None)
if __name__ == "__main__": print(current()[0])
