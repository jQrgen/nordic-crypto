#!/usr/bin/env python3
"""Fødselsnummer must match real IDs and ignore decimal prices. python3 tests/test_privacy_gate.py"""
import contextlib, io, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import privacy_gate
from tools.privacy_gate import RULES

FNR = RULES["fødselsnummer"]
KONTO = RULES["kontonummer"]
PHONE = RULES["telefonnummer"]


class PrivacyGateNumbers(unittest.TestCase):
    def test_fodselsnummer_with_and_without_space(self):
        for text in ("01019012345", "010190 12345", "fnr 01019012345.", "fnr, 010190 12345,"):
            self.assertIsNotNone(FNR.search(text), text)

    def test_fodselsnummer_ignores_decimals_and_longer_digit_runs(self):
        for text in (
            "0.00006648965",
            "1,23456789012",
            '"mid": "0.00006648965"',
            "0.00006669655",
            "0.00000000395",
            "1,01019012345",
            "01019012345.67",
            "01019012345,67",
            "010190123456",
            "abc01019012345",
            "01019012345abc",
        ):
            self.assertIsNone(FNR.search(text), text)

    def test_kontonummer_still_matches_real_accounts(self):
        for text in ("1234.56.78901", "1234 56 78901", "konto 1234.56.78901.", "kontonr.1234.56.78901"):
            self.assertIsNotNone(KONTO.search(text), text)

    def test_kontonummer_ignores_decimal_fragments(self):
        for text in ("12.3456.78.90123", "0.1234.56.78901", "1,2345.67.89012", "0.00006648965", "1,23456789012"):
            self.assertIsNone(KONTO.search(text), text)

    def test_phone_already_ignores_decimals(self):
        for text in ("0.00006648965", "1,23456789012", "0.22345678", "1,22345678"):
            self.assertIsNone(PHONE.search(text), text)
        for text in ("22345678", "+47 22 33 44 55", "22 33 44 55", "223 45 678", "tlf. 22345678"):
            self.assertIsNotNone(PHONE.search(text), text)


class PrivacyGateMain(unittest.TestCase):
    """main() reports every hit at every file:line, also when the same line repeats (clean lines are memoised)."""

    def run_gate(self, priv, site):
        old_priv, old_rules = privacy_gate.PRIV, dict(RULES)
        buf = io.StringIO()
        try:
            privacy_gate.PRIV = priv
            with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(buf):
                privacy_gate.main(["privacy_gate.py", site])
        finally:
            privacy_gate.PRIV = old_priv; RULES.clear(); RULES.update(old_rules)
        return cm.exception.code, buf.getvalue()

    def test_repeated_hit_lines_are_all_reported(self):
        with tempfile.TemporaryDirectory() as d:
            priv = os.path.join(d, "terms.json"); site = os.path.join(d, "site"); os.mkdir(site)
            with open(priv, "w", encoding="utf-8") as f: f.write("{}")
            for name in ("a.html", "b.html"):
                with open(os.path.join(site, name), "w", encoding="utf-8") as f:
                    f.write("<p>ren</p>\n<p>tlf 22 33 44 55</p>\n<p>ren</p>\n")
            code, err = self.run_gate(priv, site)
        self.assertEqual(code, 1)
        for name in ("a.html", "b.html"):
            self.assertIn(f"{name}:2  regel «telefonnummer»", err)
        self.assertEqual(err.count("regel «"), 2)
        self.assertIn("FEIL, 2 treff i 2 filer", err)

    def test_missing_terms_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            code, err = self.run_gate(os.path.join(d, "missing.json"), d)
        self.assertEqual(code, 1)
        self.assertIn("mangler state/private_terms.json", err)


if __name__ == "__main__":
    unittest.main()
