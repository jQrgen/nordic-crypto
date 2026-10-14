# Newsletter → Weibo (Simplified Chinese)

`tools/weibo_newsletter.py` posts each new Nordic Crypto issue to Weibo once, in Simplified Chinese. The brand stays
"Nordic Crypto".

**Copy:** `newsletter/published/<id>/social.zh.json` holds the translated headline, intro and each story's headline and
summary, in issue order. Add it when publishing an issue. Without it, the issue is skipped and never posted in English.

The file is written automatically when an issue is published: `./publish.sh --yes` runs `tools/social_translate.py`,
and the workflow fills any gap before posting. It never overwrites a file with `"reviewed": true` or one edited by
hand. See `docs/social-translate.md`. The dry run shows whether the copy is generated or reviewed.

**Post:** Weibo `statuses/share.json` allows 140 Chinese characters (2 Latin characters count as 1). The text must
include a link on the app's safe domain, so set that to `nordiccrypto.no`. The post holds:
- `【headline】intro`
- as many story headlines as fit
- the issue link, where the newsreel plays

**Video:** the public Open API has no video upload for ordinary apps.
- By default the issue cover (`thumbnail.png`) is attached as `pic`. This is the link + cover fallback.
- If Weibo grants the app a video upload endpoint, set `WEIBO_VIDEO_UPLOAD_URL`. The MP4 is uploaded there first and
  its `media_id` is attached. If that fails, the post falls back to link + cover.

**Rules:** a real run only posts once the issue page answers 200. State is kept in `data/weibo_posted.json`.

```sh
python3 tools/weibo_newsletter.py --issue 002 --dry-run
python3 -m pytest tests/test_weibo_newsletter.py
```

## Setup and caveats
- **Weibo account:** must be verified, which needs a Chinese (+86) mobile number.
- **Developer app:** must be approved at open.weibo.com, with `nordiccrypto.no` as its safe domain. The token goes in
  the `WEIBO_ACCESS_TOKEN` secret. If it is missing, the script logs `skipping: missing …` and exits 0.
- **Removal risk:** crypto content may be limited or removed in mainland China, and the account may be restricted.
