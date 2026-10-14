# Newsletter → VK community (Russian)

`tools/vk_newsletter.py` posts each new Nordic Crypto issue once to the Nordic Crypto VK community, in Russian. The
brand stays "Nordic Crypto".

**Copy:** `newsletter/published/<id>/social.ru.json` holds the translated headline, intro and each story's headline and
summary, in issue order. Without it, the issue is skipped.

**Flow (API 5.199):**
1. `video.save(group_id, name, description, wallpost=0)` returns an upload URL.
2. The MP4 is uploaded there as `video_file`.
3. `wall.post(owner_id=-GROUP_ID, from_group=1, message, attachments=video…,<issue link>)`. The message holds the
   headline, intro, every story (headline, summary, link) and the issue link.

**Rules:** a real run only posts once the issue page answers 200. State is kept in `data/vk_posted.json`. An uploaded
video is reused if `wall.post` fails, so it is never uploaded twice.

```sh
python3 tools/vk_newsletter.py --issue 002 --dry-run
python3 -m pytest tests/test_vk_newsletter.py
```

## Secrets
- `VK_GROUP_ID`: the community's numeric id, without the minus sign.
- `VK_ACCESS_TOKEN`: a token with `video` and `wall` access. A community token works for wall posts. If `video.save` is
  refused with a community token, use the user token of a community admin (scopes `video,wall,groups,offline`).

If either is missing, the script logs `skipping: missing …` and exits 0.
