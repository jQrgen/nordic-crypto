# Newsletter social copy in Chinese and Russian (Weibo, VK)

`tools/social_translate.py` writes `newsletter/published/<id>/social.zh.json` (Weibo) and `social.ru.json` (VK) for a
newsletter issue. `tools/weibo_newsletter.py` and `tools/vk_newsletter.py` read these files. If a file is missing,
they skip the issue and never post it in English.

## How it fits the existing translation setup
The site has no live translation service. The UI strings for its 21 languages (`i18n/*.py`) and the story
translations (`summary_i18n` with `summary_i18n_source`) are AI-assisted translations, committed next to their
English source. This tool follows the same pattern:
- the translation is made once and committed;
- `source_sha` records which English text it was made from;
- `reviewed` works like `summary_i18n_review`.

The only new part is the model call. It goes to any OpenAI-compatible chat-completions endpoint, configured by
`SOCIAL_TRANSLATE_URL`, `SOCIAL_TRANSLATE_KEY` and `SOCIAL_TRANSLATE_MODEL`. If any of them is missing, the tool logs
one line and exits 0.

## When it runs
- **`./publish.sh --yes`:** runs it for the newest issue before `build.py`. The new files are committed to `main` with
  the rest of the publish (step 2). A failure only prints a warning; the publish goes on.
- **By hand:**
  - `python3 tools/social_translate.py --issue 002`
  - `python3 tools/social_translate.py --all`
  - `python3 tools/social_translate.py --dry-run` (no API call, writes nothing)

## Human edits are never overwritten
A file is regenerated only when all of these hold:
1. it does not have `"reviewed": true`;
2. its `content_sha` still matches its text, so any hand edit blocks regeneration (to regenerate, delete the file);
3. the English changed (`source_sha`), or `--force` is given.

## Rules
- **Brand:** "Nordic Crypto" is masked before translation and restored afterwards, so it is never translated.
- **Titles:** always `Nordic Crypto 第N期：…` (zh) or `Nordic Crypto №N: …` (ru).
- **Refused text:** AI disclaimers ("made with AI" in English, Chinese or Russian), "Crypto Nordic", and Kaupr
  described as a sponsor. Kaupr stays a plain news source.
- **Weibo length:** in zh, `【title】intro` plus the issue-link line fits Weibo's 140 characters. The intro is cut at a
  sentence, then at a character. A title that is too long fails the run, so a headline is never cut.
