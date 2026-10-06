#!/usr/bin/env python3
"""Fødselsnummer must match real IDs and ignore decimal prices. python3 tests/test_privacy_gate.py"""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
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


if __name__ == "__main__":
    unittest.main()
