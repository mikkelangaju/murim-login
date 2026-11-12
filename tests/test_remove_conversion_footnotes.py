"""Regression checks for a corpus-wide footnote cleanup."""

import tempfile
import unittest
from pathlib import Path

from tools.remove_conversion_footnotes import clean_note, run, transform


class ConversionFootnotesTest(unittest.TestCase):
    def test_deletes_repeated_references_without_renumbering_other_notes(self):
        original = (
            "# Chapter 1\n\nTen meters.[^1] Again.[^1] A goshiwon.[^2]\n\n"
            "[^1]: Ten meters is about 33 ft.\n"
            "[^2]: An inexpensive room for rent.\n"
        )
        updated, changes = transform(original)
        self.assertEqual(updated, (
            "# Chapter 1\n\nTen meters. Again. A goshiwon.[^2]\n\n"
            "[^2]: An inexpensive room for rent.\n"
        ))
        self.assertEqual(len(changes), 1)
        self.assertEqual(transform(updated), (updated, []))

    def test_traditional_units_keep_metric_explanation(self):
        examples = {
            "A pyeong is about 3.31 m² (35.6 ft²).": "A pyeong is about 3.31 m².",
            "A jang is about 3.03 meters or 9.94 feet.": "A jang is about 3.03 meters.",
            "A geun is 600 g, or about 1.32 lb.": "A geun is 600 g.",
            "A seom is about 180 liters or 48 US gallons.": "A seom is about 180 liters.",
            "A hop is approximately 180 mL or 6.1 US fl oz.": "A hop is approximately 180 mL.",
            "A handspan is roughly 20 cm (8 in).": "A handspan is roughly 20 cm.",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(clean_note(original), expected)

    def test_cultural_content_survives_separate_conversion_sentence_or_clause(self):
        self.assertEqual(
            clean_note("An officetel serves office and residential uses. 132 square meters is about 1,420 square feet."),
            "An officetel serves office and residential uses.",
        )
        self.assertEqual(
            clean_note("The big three are three lifts. In Korean gym talk, the total is in kilograms; five thousand kilograms is about 11,000 lb."),
            "The big three are three lifts. In Korean gym talk, the total is in kilograms.",
        )
        self.assertEqual(
            clean_note("Thirty meters is about 100 ft. The Korean uses ten jang."),
            "The Korean uses ten jang.",
        )

    def test_ordinary_feet_and_literary_unit_names_are_preserved(self):
        for note in (
            "Horse stance uses a wide stance with the feet set apart.",
            "Myriad-Mile Pursuit is an epithet.",
            "The name uses a liang, rendered as “ounce,” equal to 50 g, and a jin of 500 g.",
        ):
            self.assertEqual(clean_note(note), note)

    def test_qualitative_temperature_speed_and_volume_conversions_are_removed(self):
        for note in (
            "Several kilometers is roughly a few miles.",
            "Thirty-nine degrees Celsius is about 102 degrees Fahrenheit.",
            "160 kilometers per hour is about 99 miles per hour.",
            "Five hundred milliliters is about 16.9 US fl oz.",
            "Fifty megatons of TNT is about 55 million US tons of TNT.",
        ):
            self.assertIsNone(clean_note(note))

    def test_indented_definition_continuation_is_removed(self):
        original = "# Chapter 1\n\nTen meters.[^1]\n\n[^1]: Ten meters\n    is about 33 ft.\n"
        updated, _ = transform(original)
        self.assertEqual(updated, "# Chapter 1\n\nTen meters.\n")

    def test_invalid_later_chapter_prevents_any_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "translations").mkdir()
            first = root / "translations/0001.md"
            original = "# Chapter 1\n\nTen meters.[^1]\n\n[^1]: Ten meters is about 33 ft.\n"
            first.write_text(original)
            (root / "translations/0002.md").write_text(original + "\nDangling.[^2]\n")
            with self.assertRaises(ValueError):
                run(root, apply=True, report=None)
            self.assertEqual(first.read_text(), original)


if __name__ == "__main__":
    unittest.main()
