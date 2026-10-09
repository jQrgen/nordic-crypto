#!/usr/bin/env python3
"""Licensed story pictures, and the ban on newspaper photographs.
  python3 tests/test_illustrations.py
Does not fetch, and does not run apply_approvals.py."""
import json, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import api_feed
import build
import illustrations
import press_images

PRESS_HOSTS = ("aftenposten.no", "svd.se", "dr.dk", "hs.fi", "mbl.is", "reuters.com")


def main():
    fails = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    illustrations.reset()
    press_images.reset_ignored()
    data = illustrations.validate()
    check(data.get("fallback") == "original-crypto", "fallback")

    def assigned(topics, country, iid=None):
        item = {"topics": topics, "country": country}
        if iid:
            item["illustration_id"] = iid
        return (illustrations.assign(item) or {}).get("id")

    check(assigned(["regulation", "aml"], "SE") == "official-riksbank", "SE aml")
    check(assigned(["crime"], "NO") == "commons-court", "crime")
    check(assigned(["business"], "SE") == "original-exchange", "business")
    check(assigned(["bitcoin", "community"], "FI") == "commons-bitcoin", "bitcoin")
    check(assigned(["funds"], "NO") == "official-norges-bank", "NO funds")
    check(assigned(["regulation", "mica"], "SE") == "commons-se", "SE regulation")
    check(assigned(["mining"], "IS") == "commons-mining", "mining")
    check(assigned(["policy"], "DK") == "original-regulation", "policy")
    check(assigned(["events"], "DK") == "commons-dk", "events")
    check(assigned(["tax"], "FI") == "original-regulation", "tax")
    check(assigned([], "IS") == "commons-is", "country fallback")
    check(assigned(["unknown-topic"], "") == "original-crypto", "no country")
    check(assigned(["crime"], "NO", "original-mining") == "original-mining", "catalogue override")
    check(assigned(["crime"], "NO", "https://aftenposten.no/x.jpg") == "commons-court", "url override ignored")

    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
    realtid = next(i for i in news["items"] if i.get("id") == "e6727b4858b5")
    check(illustrations.assign(realtid)["id"] == "official-riksbank", "realtid row")
    for item in news["items"]:
        for path, url in press_images.walk_press_urls(item):
            fails.append(f"press url in news.json {item.get('id')} {path}")

    row = {"id": "abc", "status": "published", "summary": "Kept.", "url": "https://example.no/a",
           "og_image": "https://aftenposten.no/photo.jpg", "media_content": [{"url": "https://svd.se/a.jpg"}],
           "illustration_id": "https://dr.dk/pic.webp"}
    removed = press_images.strip_press_images(row)
    check(row.get("status") == "published" and row.get("summary") == "Kept.", "strip keeps status")
    check("og_image" not in row and "media_content" not in row and "illustration_id" not in row, "strip drops pictures")
    check("og_image" in removed and "illustration_id" in removed, "strip reports keys")
    check(press_images.note_og_image("https://hs.fi/x.jpg") is None, "og dropped")
    check(press_images.entry_carries_article_image({"enclosures": [{"type": "image/jpeg", "href": "https://mbl.is/a.jpg"}]}), "enclosure counted")

    rec = illustrations.assign({"topics": ["crime"], "country": "NO"})
    for key in ("source", "author", "license", "url"):
        check(rec.get(key), f"catalogue {key}")
    fig = illustrations.figure_html(rec, "", {"ill_photo": "Photo", "ill_licence": "Licence", "ill_source": "Source"})
    check('loading="lazy"' in fig and 'class="credit"' in fig and "Mahlum" in fig, "figure credit")
    check("text-align:center" not in fig and "margin:auto" not in fig, "figure not centered")
    check("text-align:start" in build.CSS and ".credit{font-size:12px" in build.CSS, "css credit")
    ill_rule = build.CSS.split(".ill{")[1].split("}")[0]
    check("text-align:start" in ill_rule and "margin:0 auto" not in ill_rule, "ill block starts at the left")

    with tempfile.TemporaryDirectory() as tmp:
        feed = api_feed.Feed(tmp, False, build.BASE)
        item = feed.news_item(realtid)
        ill = item.get("illustration") or {}
        for key in ("source", "author", "license", "url"):
            check(ill.get(key), "api " + key)
        check(str(ill.get("file_url") or "").startswith(build.BASE), "file on our host")
        check("riksbank.se" in (ill.get("url") or ""), "riksbank source url")
        check(item.get("html_url", "").endswith("/stories/e6727b4858b5/"), "external story page")
        own = feed.news_item({"id": "story-demo", "own_story": True, "url": "stories/demo/", "title": "Ours", "status": "published"})
        check("/stories/demo/" in (own.get("html_url") or "") and own["html_url"].count("/stories/demo/") == 1, "own url once")
        dumped = json.dumps(item)
        for host in PRESS_HOSTS:
            if host in dumped and any(ext in dumped for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                # A host mention inside a summary is fine. A picture URL is not.
                if press_images.is_press_image_url(dumped):
                    fails.append("press picture url in api item")
        for path, _url in press_images.walk_press_urls(item):
            fails.append("press picture in api item " + path)

        poisoned = dict(realtid)
        poisoned["og_image"] = "https://realtid.se/wp-content/uploads/hero.jpg"
        clean = feed.news_item(poisoned)
        check("og_image" not in clean, "api omits og_image")
        for path, _url in press_images.walk_press_urls(clean):
            fails.append("poisoned url survived " + path)

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("illustrations ok")


if __name__ == "__main__":
    main()
