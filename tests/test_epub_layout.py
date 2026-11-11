"""Opt-in WebKit layout regression: MURIM_WEBKIT_QA=1 python -m unittest discover
-s tests -p test_epub_layout.py. Requires Playwright and its WebKit browser.
"""

import os
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.build import STYLESHEET, run_pandoc, validate_epub


@unittest.skipUnless(os.environ.get("MURIM_WEBKIT_QA") == "1", "opt-in WebKit layout QA")
class EpubLayoutTest(unittest.TestCase):
    def test_frame_and_dragons_survive_reader_image_rules(self):
        from PIL import Image
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "chapter.md"
            source.write_text(
                "# Chapter 0\n\n> **System**\n>\n"
                "> Applying the Integrated Language Pack.\n\n"
                "> **System**\n>\n> **Quest**\n>\n> Tutorial—Stage 1\n>\n"
                "> Gather basic information and understand the situation.\n>\n"
                "> - Grade: Tutorial (Chain Quest)\n"
                "> - Restriction: First-time players\n"
                "> - Rewards: Sturdy Martial Uniform Set\n\n---\n\nNext scene.\n",
                encoding="utf-8",
            )
            (root / "book.css").write_bytes(STYLESHEET.read_bytes())
            epub = root / "test.epub"
            run_pandoc([source], epub, "epub3", root / "book.css")
            validate_epub(epub)
            with ZipFile(epub) as archive:
                archive.extractall(root / "unpacked")
            chapter = root / "unpacked" / "EPUB" / "text" / "ch001.xhtml"
            with sync_playwright() as playwright:
                browser = playwright.webkit.launch()
                page = browser.new_page()
                for width, font_size, theme in (
                    (320, 16, "light"), (390, 24, "light"),
                    (700, 16, "light"), (390, 24, "dark"), (700, 16, "dark"),
                    (390, 32, "light"), (700, 32, "dark"),
                ):
                    with self.subTest(width=width, font_size=font_size, theme=theme):
                        page.set_viewport_size({"width": width, "height": 1100})
                        page.emulate_media(color_scheme=theme)
                        page.goto(chapter.as_uri())
                        # This responsive-image rule reproduces zero-width dragons
                        # in the released EPUB's nested auto-layout header table.
                        page.add_style_tag(content=(
                            "img { max-width:100%; height:auto; }"
                            f"body {{ font-size:{font_size}px; }}"
                            # Readers can scale the header's font as well as body text.
                            f"td.system-crest {{ font-size:{font_size}px !important; line-height:1.8 !important; }}"
                        ))
                        if theme == "dark":
                            # Books' night theme can replace solid cell colors
                            # while preserving gradient backgrounds.
                            page.add_style_tag(content="td { background-color: #000 !important; }")
                        results = page.locator("table.system-window").evaluate_all("""tables => tables.map(t => {
                            const rect = e => e.getBoundingClientRect();
                            const frame = rect(t);
                            const corners = [...t.querySelectorAll('img.system-corner-art')].map(rect);
                            const crest = rect(t.querySelector('.system-crest'));
                            return {
                                left: frame.left, right: frame.right,
                                cornerEdges: corners.map(r => [r.left, r.right]),
                                centerError: Math.abs((crest.left+crest.right-frame.left-frame.right)/2),
                                dragons: [...t.querySelectorAll('img.system-dragon')].map(e => ({
                                    width: rect(e).width, height: rect(e).height,
                                    loaded: e.complete && e.naturalWidth > 0,
                                    top: rect(e).top - crest.top,
                                    inside: rect(e).left >= crest.left && rect(e).right <= crest.right
                                })),
                                fill: getComputedStyle(t.querySelector('.system-body')).backgroundImage,
                                ink: getComputedStyle(t.querySelector('.system-body p')).webkitTextFillColor,
                                overflow: t.scrollWidth > frame.width+1
                            };
                        })""")
                        self.assertEqual(len(results), 2)
                        separator = page.locator("img.scene-separator-art").evaluate("""e => {
                            const r = e.getBoundingClientRect();
                            return {width:r.width, height:r.height, center:(r.left+r.right)/2,
                                    loaded:e.complete && e.naturalWidth > 0};
                        }""")
                        self.assertTrue(separator["loaded"])
                        self.assertAlmostEqual(separator["center"], width / 2, delta=1)
                        self.assertAlmostEqual(separator["width"], 1.35 * font_size, delta=0.1)
                        self.assertAlmostEqual(separator["height"], separator["width"], delta=0.1)
                        for result in results:
                            self.assertGreaterEqual(result["left"], 0)
                            self.assertLessEqual(result["right"], width)
                            self.assertLessEqual(result["centerError"], 1)
                            self.assertFalse(result["overflow"])
                            self.assertEqual(len(result["dragons"]), 2)
                            for dragon in result["dragons"]:
                                self.assertTrue(dragon["loaded"] and dragon["inside"])
                                self.assertGreaterEqual(dragon["width"], 24)
                                self.assertGreaterEqual(dragon["height"], 19)
                                self.assertAlmostEqual(dragon["top"], 3.75, delta=0.1)
                            for index, (left, right) in enumerate(result["cornerEdges"]):
                                self.assertAlmostEqual(left if index % 2 == 0 else right,
                                                       result["left"] if index % 2 == 0 else result["right"], delta=1)
                            self.assertEqual(result["ink"], "rgb(255, 255, 255)")
                            expected_fill = "rgb(23, 57, 87)" if theme == "dark" else "rgb(45, 106, 173)"
                            self.assertIn(expected_fill, result["fill"])
                        for window in page.locator("table.system-window").all():
                            crest_left = window.locator(".system-crest").evaluate(
                                "e => e.getBoundingClientRect().left - e.closest('table').getBoundingClientRect().left"
                            )
                            with Image.open(BytesIO(window.screenshot())) as image:
                                rgb = image.convert("RGB")
                                panel = (23, 57, 87) if theme == "dark" else (45, 106, 173)
                                # The side gutter must retain the blue fill even
                                # when every cell's background-color is black.
                                self.assertEqual(rgb.getpixel((12, rgb.height // 2)), panel)
                                # The top stroke continues through the crest,
                                # visible between each dragon and the label.
                                for offset in (31, 100):
                                    self.assertEqual(rgb.getpixel((round(crest_left + offset), 13)), (230, 200, 106))
                                # Gold reaches both outer edges from the upper
                                # corners down through the lower corners.
                                for x in (1, rgb.width - 2):
                                    for y in range(12, rgb.height - 1):
                                        red, green, blue = rgb.getpixel((x, y))
                                        self.assertGreater(red, blue)
                                        self.assertGreater(green, blue)
                browser.close()


if __name__ == "__main__":
    unittest.main()
