import json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import social_translate as st

ZH = {"headline": "挪威议会出现暂停数据中心提案，瑞典发布新的诈骗警告",
      "intro": "2026年10月5日至12日，经编辑审核的⟦NC⟧北欧加密货币新闻。本期共有七条新闻。我们每周一发布一期。欢迎订阅。",
      "summary": "摘要。"}


def fake(lang, src, **over):
    head = over.get("headline", ZH["headline"] if lang == "zh" else "Предложения остановить дата-центры")
    intro = over.get("intro", ZH["intro"] if lang == "zh" else "Новости недели от ⟦NC⟧.")
    return {"headline": head, "intro": intro,
            "stories": [{"title": f"{lang}-{i}", "summary": over.get("summary", "Kaupr сообщает." if lang == "ru" else ZH["summary"])}
                        for i, _ in enumerate(src["stories"])]}, "test-model"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(st.PUBLISHED, os.path.join(self.tmp, "published"), ignore=shutil.ignore_patterns("*.mp4", "social.*.json"))
        self._pub, st.PUBLISHED = st.PUBLISHED, os.path.join(self.tmp, "published")
        self.meta = next(i for i in st.issues() if i["id"] == "002")

    def tearDown(self):
        st.PUBLISHED = self._pub
        shutil.rmtree(self.tmp)

    def path(self, lang):
        return os.path.join(st.PUBLISHED, "002", f"social.{lang}.json")

    def load(self, lang):
        return json.load(open(self.path(lang), encoding="utf-8"))


class Generate(Base):
    def test_writes_both_with_brand_and_weibo_limit(self):
        self.assertEqual(st.run(self.meta, ["zh", "ru"], False, False, translate=fake), 0)
        zh, ru = self.load("zh"), self.load("ru")
        self.assertTrue(zh["title"].startswith("Nordic Crypto 第2期："))
        self.assertTrue(ru["title"].startswith("Nordic Crypto №2: "))
        self.assertIn("Nordic Crypto", zh["intro"])          # mask restored, brand untranslated
        self.assertNotIn("⟦NC⟧", json.dumps(zh, ensure_ascii=False))
        url = "https://nordiccrypto.no/newsletter/002/"
        self.assertLessEqual(st.weibo_len(f"【{zh['title']}】{zh['intro']}" + st.WEIBO_TAIL.format(url=url)), st.WEIBO_LIMIT)
        self.assertEqual(len(zh["stories"]), 7)
        self.assertFalse(zh["reviewed"])
        self.assertEqual(zh["content_sha"], st.sha(st.content_of(zh)))

    def test_up_to_date_not_regenerated(self):
        st.run(self.meta, ["zh"], False, False, translate=fake)
        st.run(self.meta, ["zh"], False, False, translate=lambda *a: self.fail("should not translate"))

    def test_reviewed_never_overwritten(self):
        st.run(self.meta, ["zh"], False, False, translate=fake)
        d = self.load("zh"); d["reviewed"] = True
        json.dump(d, open(self.path("zh"), "w"), ensure_ascii=False)
        st.run(self.meta, ["zh"], False, True, translate=lambda *a: self.fail("reviewed file touched"))

    def test_hand_edited_never_overwritten(self):
        st.run(self.meta, ["ru"], False, False, translate=fake)
        d = self.load("ru"); d["intro"] = "Правка редактора."
        json.dump(d, open(self.path("ru"), "w"), ensure_ascii=False)
        st.run(self.meta, ["ru"], False, True, translate=lambda *a: self.fail("hand edit touched"))
        self.assertEqual(self.load("ru")["intro"], "Правка редактора.")

    def test_file_without_hash_counts_as_human(self):
        json.dump({"title": "x", "intro": "y", "stories": []}, open(self.path("zh"), "w"))
        self.assertEqual(st.decide(self.path("zh"), "abc", True)[0], False)

    def test_english_change_regenerates(self):
        st.run(self.meta, ["zh"], False, False, translate=fake)
        d = self.load("zh"); d["source_sha"] = "old"; d["content_sha"] = st.sha(st.content_of(d))
        json.dump(d, open(self.path("zh"), "w"), ensure_ascii=False)
        self.assertEqual(st.decide(self.path("zh"), st.sha(st.english(self.meta)), False), (True, "English changed"))

    def test_dry_run_writes_nothing(self):
        st.run(self.meta, ["zh", "ru"], True, False, translate=lambda *a: self.fail("dry run translated"))
        self.assertFalse(os.path.exists(self.path("zh")))


class Rules(Base):
    def bad(self, lang, **over):
        st.run(self.meta, [lang], False, False, translate=lambda l, s: fake(l, s, **over))
        return not os.path.exists(self.path(lang))

    def test_refuses_ai_disclaimer(self):
        self.assertTrue(self.bad("zh", intro="本期内容由AI生成。"))
        self.assertTrue(self.bad("ru", intro="Сделано с помощью ИИ."))

    def test_refuses_kaupr_sponsor(self):
        self.assertTrue(self.bad("ru", summary="Спонсор выпуска Kaupr."))

    def test_kaupr_as_source_is_fine(self):
        self.assertFalse(self.bad("ru"))

    def test_story_count_mismatch(self):
        st.run(self.meta, ["zh"], False, False, translate=lambda l, s: ({"headline": "h", "intro": "i", "stories": []}, "m"))
        self.assertFalse(os.path.exists(self.path("zh")))

    def test_too_long_zh_title_fails(self):
        self.assertTrue(self.bad("zh", headline="很长" * 70))

    def test_fit_weibo_trims_intro_at_sentence(self):
        title, url = "Nordic Crypto 第2期：" + "标题" * 15, "https://nordiccrypto.no/newsletter/002/"
        intro = st.fit_weibo(title, "第一句。" * 30, url)
        self.assertTrue(intro.endswith("。"))
        self.assertLessEqual(st.weibo_len(f"【{title}】{intro}" + st.WEIBO_TAIL.format(url=url)), st.WEIBO_LIMIT)

    def test_main_skips_without_endpoint(self):
        for k in ("SOCIAL_TRANSLATE_URL", "SOCIAL_TRANSLATE_KEY", "SOCIAL_TRANSLATE_MODEL"):
            os.environ.pop(k, None)
        self.assertEqual(st.main(["--issue", "002"]), 0)
        self.assertFalse(os.path.exists(self.path("zh")))


if __name__ == "__main__":
    unittest.main()
