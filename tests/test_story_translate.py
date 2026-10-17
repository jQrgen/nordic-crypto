#!/usr/bin/env python3
"""tools/story_translate.py fills headline, summary and blurb in every site language, and never replaces text."""
import json, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import story_translate as st

FA = "این یک جمله است. این جمله دوم است."


def fake(system, user):
    """Answers every requested code and field from the spec lines of the prompt."""
    out = {}
    for line in system.splitlines():
        if line.startswith('- "'):
            code = line.split('"')[1]
            fields = [f.strip() for f in line.split(":", 1)[1].split(",")]
            text = {"fa": FA, "ar": "هذه جملة. وهذه جملة ثانية.", "zh": "这是一句。这是第二句。", "ja": "これは文です。二つ目です。",
                    "hi": "यह वाक्य है। दूसरा वाक्य।", "mr": "हे वाक्य आहे। दुसरे वाक्य।", "bn": "এটি বাক্য। দ্বিতীয় বাক্য।",
                    "ur": "یہ جملہ ہے۔ دوسرا جملہ۔", "ru": "Это фраза. Вторая фраза.", "uk": "Це речення. Друге речення."}.get(code, f"Tekst {code} en. Tekst {code} to.")
            out[code] = {f: text for f in fields}
    return out


class StoryTranslate(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "data"))
        os.makedirs(os.path.join(self.root, "queue"))
        self.item = {"id": "abc", "url": "https://example.no/sak", "title": "Avviser krypto-på-kammerset-påstand",
                     "title_en": "Industry body rejects claim", "language": "Norwegian", "status": "published",
                     "summary": "One. Two.", "summary_i18n": {"nb": "En. To."}, "approved_at": "2026-10-17T04:00:00+02:00"}
        self._w("data/news.json", {"items": [self.item, {**self.item, "id": "rej", "url": "https://x.no/r", "status": "rejected"}]})
        self._w("data/title_i18n.json", {"_note": "", "langs": ["nn"], "items": {"abc": {"source": self.item["title"], "nn": "Avviser påstanden"}}})
        self._w("data/frontpage_blurbs.json", {"langs": ["en"], "items": {"abc": {"en": "First. Second."}}})
        self._w("queue/approved.json", {"items": [{"url": "https://example.no/sak", "summary": "One. Two.", "summary_i18n": {"nb": "En. To."}}]})

    def _w(self, rel, obj):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)

    def _r(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return json.load(fh)

    def test_fills_every_language_and_keeps_existing_text(self):
        st.run(self.root, translate=fake, log=lambda m: None, workers=2)
        story = next(i for i in self._r("data/news.json")["items"] if i["id"] == "abc")
        self.assertEqual(set(story["summary_i18n"]), set(st.LANGS))
        self.assertEqual(story["summary_i18n"]["nb"], "En. To.")
        self.assertEqual(story["summary_i18n"]["fa"], FA)
        heads = self._r("data/title_i18n.json")["items"]["abc"]
        self.assertEqual(heads["nn"], "Avviser påstanden")
        self.assertNotIn("nb", heads)  # the source headline is already Bokmål
        self.assertEqual(set(heads) - {"source"}, set(st.LANGS) - {"nb"})
        self.assertEqual(self._r("data/frontpage_blurbs.json")["items"]["abc"]["fa"], FA)
        ap = self._r("queue/approved.json")["items"][0]
        self.assertEqual(ap["summary_i18n"]["fa"], FA)
        self.assertEqual(ap["summary_i18n_source"], "One. Two.")
        rej = next(i for i in self._r("data/news.json")["items"] if i["id"] == "rej")
        self.assertEqual(rej["summary_i18n"], {"nb": "En. To."})

    def test_second_run_has_nothing_to_do(self):
        st.run(self.root, translate=fake, log=lambda m: None)
        calls = []
        st.run(self.root, translate=lambda s, u: calls.append(1) or {}, log=lambda m: None)
        self.assertEqual(calls, [])

    def test_wrong_script_and_reversed_brand_are_dropped(self):
        self.assertTrue(st.valid("fa", "summary", "English text only here.", "x"))
        self.assertTrue(st.valid("de", "summary", "Crypto Nordic berichtet.", "Nordic Crypto reports."))
        self.assertTrue(st.valid("de", "summary", "Der Bericht.", "Nordic Crypto reports."))
        self.assertTrue(st.valid("de", "summary", "Kaupr ist Sponsor.", "Kaupr reports."))
        self.assertEqual(st.valid("fa", "headline", "سازمان NDI ادعا را رد می‌کند", "NDI rejects claim"), "")
        self.assertEqual(st.tidy("Krypto\u2011Mining"), "Krypto-Mining")

    def test_without_credentials_nothing_is_written(self):
        env = {k: os.environ.pop(k) for k in ("CF_AI_TOKEN", "CLOUDFLARE_AI_TOKEN", "CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID") if k in os.environ}
        try:
            before = self._r("data/news.json")
            st.run(self.root, log=lambda m: None)
            self.assertEqual(self._r("data/news.json"), before)
        finally:
            os.environ.update(env)


if __name__ == "__main__":
    unittest.main()
