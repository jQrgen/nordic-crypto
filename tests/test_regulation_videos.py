#!/usr/bin/env python3
"""Regulation explainer slots: five countries, placeholders until an MP4 exists, Iceland called out."""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build
import regulation_videos

COUNTRIES = ["NO", "SE", "DK", "FI", "IS"]

def page_html(lang, site):
    build.SITE = site
    build.LANG = lang
    build.PREVIEW = False
    org = build.load(build.P("data", "orgchart.json"), {})
    regulation_videos.build(build, {"ents": [], "org": org})
    path = os.path.join(site, "" if lang == "en" else lang, "regulation-videos", "index.html")
    return open(path, encoding="utf-8").read()

def main():
    fails = []
    if "text-align:center" in regulation_videos.CSS or "justify-content:center" in regulation_videos.CSS:
        fails.append("slot CSS centers content")
    with tempfile.TemporaryDirectory() as tmp:
        html = page_html("en", tmp)
        opener = html.split("<footer")[0]
        if "<video" in opener:
            fails.append("placeholder slot embedded a video")
        if "Video coming soon" not in opener:
            fails.append("missing coming-soon placeholder")
        if "The films are not rendered yet." not in opener:
            fails.append("opener claims the films exist")
        low = opener.lower()
        if "made with" in low or "artificial intelligence" in low:
            fails.append("opener mentions how the film was made")
        if "kaupr" in low:
            fails.append("Kaupr named on the explainer page")
        if "The Nordic Crypto team" not in opener:
            fails.append("sign-off missing")
        for c in COUNTRIES:
            if f'id="{c}"' not in opener:
                fails.append("missing slot " + c)
        if "not the EU" not in opener or "Fjármálaeftirlit" not in opener or "Seðlabanki Íslands" not in opener:
            fails.append("Iceland EEA / Fjármálaeftirlit callout missing")
        if "European Economic Area" not in opener:
            fails.append("EEA wording missing")
        for needle in ("lovdata.no", "riksdagen.se", "retsinformation.dk", "finlex.fi", "althingi.is", "eur-lex.europa.eu"):
            if needle not in opener:
                fails.append("source missing " + needle)
        if "Good evening. This is Nordic Crypto." not in opener:
            fails.append("narrator notes missing")
        if 'href="../rules/"' not in opener:
            fails.append("rules link missing")
        for lang in ("nn", "nb", "sv", "da", "fi", "is"):
            other = page_html(lang, tmp)
            if "Fjármálaeftirlit" not in other.split("<footer")[0]:
                fails.append(lang + " missing Iceland callout")
            if 'lang="en"' not in other:
                fails.append(lang + " narrator notes not marked English")
        # one rendered file turns that slot into an HTML5 video and leaves the others as placeholders
        media = os.path.join(ROOT, "regulation-videos", "media")
        sample = os.path.join(media, "video-is.mp4")
        try:
            open(sample, "wb").write(b"\0not-a-real-movie")
            played = page_html("en", tmp)
        finally:
            if os.path.exists(sample):
                os.remove(sample)
        body = played.split("<footer")[0]
        if body.count("<video") != 1:
            fails.append("expected one HTML5 video, got %s" % body.count("<video"))
        if 'src="../../regulation-videos/video-is.mp4"' not in body and 'src="../regulation-videos/video-is.mp4"' not in body:
            fails.append("Iceland video source missing")
        if body.count("Video coming soon") != 4:
            fails.append("expected four placeholders beside the Iceland film")
        # posters copied for the placeholder slots
        if not os.path.exists(os.path.join(tmp, "regulation-videos", "poster-no.png")):
            fails.append("poster not copied")
        if not os.path.exists(os.path.join(tmp, "regulation-videos", "video-is.mp4")):
            fails.append("mp4 not copied into the site")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("regulation-videos: ok")
    return 0

if __name__ == "__main__":
    sys.exit(main())
