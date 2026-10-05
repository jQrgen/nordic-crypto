#!/usr/bin/env python3
"""Text gate (editor rule, 4 Oct 2026): our own Norwegian text (nn, nb) must never say "AI" or "KI" – write
«kunstig intelligens» in full. Fails (exit 1) on any hit; prints file/key and the offending snippet.
Checks everything WE write in Norwegian: i18n/nn.py, i18n/nb.py, templates/*.nn.html / *.nb.html, the nn/nb summaries
and event notes in queue/approved.json, nn/nb entries in changelog.json and the nn/nb strings of the rules page.
External headlines and quotes are not checked (they stay in the original language).
Usage: python3 tools/text_gate.py"""
import glob, importlib.util, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
BAD = re.compile(r"(?<![\w-])(?:AI|KI)(?![\w])|(?<![\w-])(?:AI|KI)-\w")
hits = []
def chk(where, text):
    for m in BAD.finditer(re.sub(r"https?://\S+", " ", text or "")):
        hits.append(f"{where}: …{text[max(0, m.start() - 30):m.end() + 30]}…")
def mod(path):
    spec = importlib.util.spec_from_file_location(os.path.basename(path), path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
for L in ("nn", "nb"):
    p = P("i18n", f"{L}.py")
    if os.path.exists(p):
        S = getattr(mod(p), "S", None) or getattr(mod(p), "STR", None)
        if isinstance(S, dict):
            for k, v in S.items(): chk(f"i18n/{L}.py {k}", v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        else: chk(f"i18n/{L}.py", open(p, encoding="utf-8").read())
    for t in glob.glob(P("templates", f"*.{L}.html")): chk(os.path.relpath(t, ROOT), re.sub(r"<[^>]+>", " ", open(t, encoding="utf-8").read()))
try: q = json.load(open(P("queue", "approved.json"), encoding="utf-8"))
except FileNotFoundError: q = {}
for i, it in enumerate(q.get("items", [])):
    for L in ("nn", "nb"): chk(f"approved.json items[{i}].summary_i18n.{L}", (it.get("summary_i18n") or {}).get(L))
for k, v in ((q.get("events") or {}).get("notes_i18n") or {}).items():
    for L in ("nn", "nb"): chk(f"approved.json events.notes_i18n.{k}.{L}", v.get(L))
def walk(o, path):
    if isinstance(o, dict):
        for k, v in o.items(): walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): walk(v, f"{path}[{i}]")
    elif isinstance(o, str) and re.search(r"\.(nn|nb)(\.|$)", path): chk(path, o)
try: walk(json.load(open(P("changelog.json"), encoding="utf-8")), "changelog.json")
except FileNotFoundError: pass
for name in ("rules_page.py", "regulation_videos.py"):
    rp = P("tools", name)
    if os.path.exists(rp):
        R = mod(rp).STR
        for L in ("nn", "nb"):
            for k, v in R.get(L, {}).items(): chk(f"{name} STR.{L}.{k}", v)
if hits:
    print("text gate: FAIL – «AI»/«KI» in Norwegian text (write «kunstig intelligens»):", file=sys.stderr)
    for h in hits: print("  " + h, file=sys.stderr)
    sys.exit(1)
print("text gate: OK (no «AI»/«KI» in our nn/nb text)")
