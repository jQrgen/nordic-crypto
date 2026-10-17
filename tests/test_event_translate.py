import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import event_description as ed, event_translate as et

EV = {"id": "x1", "description": {"text": "Når bankene omfavner kryptovaluta, hvem får makten over framtidens penger i Norge?", "lang": "nb",
      "source_url": "https://example.org/e", "source_name": "Ex"}}


class T(unittest.TestCase):
    def test_fill_then_show(self):
        cat, asked = {}, []
        def tr(text, src, langs):
            asked.append(langs)
            return {l: f"{l}: when banks embrace cryptocurrency, who controls the money of the future?" for l in langs}
        self.assertEqual(et.fill([EV], cat, tr), ["x1"])
        self.assertNotIn("nb", asked[0])
        text, lang, orig = ed.show(EV, "en", cat)
        self.assertTrue(text.startswith("en:")); self.assertEqual(lang, "en"); self.assertEqual(orig, EV["description"]["text"])
        self.assertEqual(et.fill([EV], cat, tr), [])

    def test_no_endpoint_skips(self):
        for k in et.ENV:
            os.environ.pop(k, None)
        self.assertEqual(et.run(log=lambda m: None), [])

    def test_failure_writes_nothing(self):
        def bad(*a): raise OSError("403")
        cat, msgs = {}, []
        self.assertEqual(et.fill([EV], cat, bad, msgs.append), []); self.assertEqual(cat, {}); self.assertTrue(msgs)


if __name__ == "__main__":
    unittest.main()
