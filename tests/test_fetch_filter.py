#!/usr/bin/env python3
"""Keyword filter and dead-feed isolation. Does not import a live news run.
python3 tests/test_fetch_filter.py
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch

def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)
    samples = [
        "Ny rapport om kryptovaluta",
        "Kryptovaluutta ja lohkoketju",
        "Rafmyntir og peningaþvætti",
        "Hvidvask via darknet",
        "Penningtvätt på mörka nätet",
        "Hvitvasking og bitcoin",
        "Rahanpesu ja virtuaalivaluutta",
    ]
    for text in samples:
        if not fetch.matches(text):
            fails.append("no keyword hit: " + text)
    check(not fetch.matches("Værmelding for Bergen i morgen"), "weather is not crypto")
    err = fetch.guarded_call(lambda: (_ for _ in ()).throw(RuntimeError("dead feed")))
    check(err and err.startswith("RuntimeError"), "dead feed becomes an error string")
    check(fetch.guarded_call(lambda: None) is None, "success is none")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("fetch filter ok")

if __name__ == "__main__":
    main()
