"""RU/EN translation key parity (P3)."""
from __future__ import annotations

import unittest

from src.shared.i18n.translator import TRANSLATIONS


class I18nParityTests(unittest.TestCase):
    def test_ru_and_en_have_same_keys(self):
        ru_keys = set(TRANSLATIONS["ru"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())
        missing_in_en = sorted(ru_keys - en_keys)
        missing_in_ru = sorted(en_keys - ru_keys)
        self.assertEqual(
            missing_in_en,
            [],
            f"Keys missing in EN: {missing_in_en[:20]}",
        )
        self.assertEqual(
            missing_in_ru,
            [],
            f"Keys missing in RU: {missing_in_ru[:20]}",
        )


if __name__ == "__main__":
    unittest.main()
