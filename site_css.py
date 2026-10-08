"""The site stylesheet, one file per part of the site in assets/css/. build.py inlines SITE into every page (build.CSS);
a page with its own module adds style(name) to its body, so the other pages do not carry those rules: who's who (orgchart), rules, regulation videos,
API docs, story (story pages), textpage (about, ethics, tip, columnist, changelog, API docs) and brand (the media kit).
Fonts come first, then tokens: every other module uses only the custom properties defined in tokens.css."""
import os
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "css")
SITE = ("fonts", "tokens", "base", "header", "footer", "components", "news", "events", "home", "markets", "newsletter", "talks", "push", "shoutbox")
def read(name):
    with open(os.path.join(DIR, name + ".css"), encoding="utf-8") as fh: return fh.read()
def bundle(names=SITE): return "".join(read(n) for n in names)
def style(name): return "<style>" + read(name) + "</style>"
