"""Opt-in WebKit layout regression: MURIM_WEBKIT_QA=1 python -m unittest discover
-s tests -p test_epub_layout.py. Requires Playwright and its WebKit browser.
"""

import os
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.build import epub_stylesheet, run_pandoc, validate_epub


@contextmanager
def color_chapter(text):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "chapter.md"
        source.write_text(text, encoding="utf-8")
        css = root / "book.css"
        css.write_text(epub_stylesheet(True), encoding="utf-8")
        epub = root / "test.epub"
        run_pandoc([source], epub, "epub3", css, full_color_epub=True)
        validate_epub(epub)
        with ZipFile(epub) as archive:
            archive.extractall(root / "unpacked")
        yield root / "unpacked/EPUB/text/ch001.xhtml"


@unittest.skipUnless(os.environ.get("MURIM_WEBKIT_QA") == "1", "opt-in WebKit layout QA")
class EpubLayoutTest(unittest.TestCase):
    def test_simple_panels_reflow_and_use_reader_colors(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "chapter.md"
            source.write_text(
                "# Chapter 0\n\n> **System**\n>\n"
                "> Applying the Integrated Language Pack.\n\nAfter.\n\n"
                "> **System**\n>\n> **Quest**\n>\n"
                "> Gather basic information and understand the situation.\n>\n"
                "> - Grade: Tutorial (Chain Quest)\n"
                "> - Restriction: First-time players\n"
                "> - Rewards: Sturdy Martial Uniform Set\n\n---\n\nNext scene.\n",
                encoding="utf-8",
            )
            (root / "book.css").write_text(epub_stylesheet(), encoding="utf-8")
            epub = root / "test.epub"
            run_pandoc([source], epub, "epub3", root / "book.css")
            validate_epub(epub)
            with ZipFile(epub) as archive:
                archive.extractall(root / "unpacked")
            with sync_playwright() as playwright:
                browser = playwright.webkit.launch()
                page = browser.new_page()
                for width, font_size, dark in ((320, 16, False), (320, 32, False), (390, 24, True), (700, 32, True)):
                    with self.subTest(width=width, font_size=font_size, dark=dark):
                        page.set_viewport_size({"width": width, "height": 1100})
                        page.goto((root / "unpacked/EPUB/text/ch001.xhtml").as_uri())
                        ink = "white" if dark else "black"
                        paper = "black" if dark else "white"
                        page.add_style_tag(content=f"body {{font-size:{font_size}px;color:{ink};background:{paper};}}")
                        panels = page.locator(".system-window-simple").evaluate_all("""es => es.map(e => {
                            const r=e.getBoundingClientRect(), s=getComputedStyle(e);
                            return {left:r.left, right:r.right, overflow:e.scrollWidth>r.width+1,
                                    border:s.borderTopColor, ink:s.color, fill:s.backgroundColor,
                                    images:e.querySelectorAll('img').length};
                        })""")
                        self.assertEqual(len(panels), 2)
                        for panel in panels:
                            self.assertGreaterEqual(panel["left"], 0)
                            self.assertLessEqual(panel["right"], width)
                            self.assertFalse(panel["overflow"])
                            self.assertEqual(panel["border"], panel["ink"])
                            self.assertEqual(panel["ink"], "rgb(255, 255, 255)" if dark else "rgb(0, 0, 0)")
                            self.assertEqual(panel["fill"], "rgba(0, 0, 0, 0)")
                            self.assertEqual(panel["images"], 0)
                browser.close()

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
            (root / "book.css").write_text(epub_stylesheet(True), encoding="utf-8")
            epub = root / "test.epub"
            run_pandoc([source], epub, "epub3", root / "book.css", full_color_epub=True)
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
                    (240, 16, "light"), (320, 32, "dark"), (1824, 32, "light"),
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
                            f".system-crest {{ font-size:{font_size}px !important; line-height:1.8 !important; }}"
                        ))
                        if theme == "dark":
                            # Books' night theme can replace solid panel colors
                            # while preserving gradient backgrounds.
                            page.add_style_tag(content=".system-content, .system-footer, .system-plaque { background-color: #000 !important; }")
                        results = page.locator("table.system-window").evaluate_all("""windows => windows.map(t => {
                            const rect = e => e.getBoundingClientRect();
                            const frame = rect(t);
                            const corners = [...t.querySelectorAll('img.system-corner-art')].map(rect);
                            const crest = rect(t.querySelector('.system-crest'));
                            return {
                                left: frame.left, right: frame.right,
                                top: frame.top, bottom: frame.bottom,
                                cornerEdges: corners.map(r => [r.left, r.right, r.top, r.bottom]),
                                centerError: Math.abs((crest.left+crest.right-frame.left-frame.right)/2),
                                dragons: [...t.querySelectorAll('img.system-dragon')].map(e => ({
                                    width: rect(e).width, height: rect(e).height,
                                    loaded: e.complete && e.naturalWidth > 0,
                                    top: rect(e).top - crest.top,
                                    inside: rect(e).left >= crest.left && rect(e).right <= crest.right
                                })),
                                fill: getComputedStyle(t.querySelector('.system-content')).backgroundImage,
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
                            for index, (left, right, top, bottom) in enumerate(result["cornerEdges"]):
                                self.assertAlmostEqual(left - result["left"] if index % 2 == 0 else result["right"] - right,
                                                       2, delta=0.1)
                                self.assertAlmostEqual(top - result["top"] if index < 2 else result["bottom"] - bottom,
                                                       (12 if index < 2 else 2), delta=0.1)
                            self.assertEqual(result["ink"], "rgb(255, 255, 255)")
                            expected_fill = "rgb(23, 57, 87)" if theme == "dark" else "rgb(45, 106, 173)"
                            self.assertIn(expected_fill, result["fill"])
                        for window in page.locator("table.system-window").all():
                            crest_left = window.locator(".system-crest").evaluate(
                                "e => e.getBoundingClientRect().left - e.closest('.system-window').getBoundingClientRect().left"
                            )
                            with Image.open(BytesIO(window.screenshot())) as image:
                                rgb = image.convert("RGB")
                                panel = (23, 57, 87) if theme == "dark" else (45, 106, 173)
                                # The side gutter retains its blue fill despite
                                # a reader's solid background-color override.
                                self.assertEqual(rgb.getpixel((12, rgb.height // 2)), panel)
                                # The top stroke continues through the crest,
                                # visible between each dragon and the label.
                                for offset in (31, 100):
                                    self.assertEqual(rgb.getpixel((round(crest_left + offset), 13)), (230, 200, 106))
                                # The gold lip is continuous outside all four
                                # corners; it masks subpixel art alignment.
                                for y in (11, rgb.height - 2):
                                    for x in range(1, rgb.width - 1):
                                        if y == 11 and crest_left <= x <= crest_left + 132:
                                            continue
                                        self.assertEqual(rgb.getpixel((x, y)), (230, 200, 106))
                                for x in (1, rgb.width - 2):
                                    for y in range(11, rgb.height - 1):
                                        red, green, blue = rgb.getpixel((x, y))
                                        self.assertGreater(red, blue)
                                        self.assertGreater(green, blue)
                browser.close()

    def test_detached_table_preserves_layout_without_chapter_stylesheet(self):
        from playwright.sync_api import sync_playwright

        source = ("# Chapter 0\n\n> **System**\n>\n> Points complete.\n\n"
                  "> **System**\n>\n> **Quest**\n>\n"
                  "> Gather basic information and understand the situation.\n>\n"
                  "> - Grade: Tutorial[^1]\n> - Rewards: Sturdy Martial Uniform Set\n\n[^1]: Tutorial note.\n")
        with color_chapter(source) as chapter, sync_playwright() as playwright:
            browser = playwright.webkit.launch()
            page = browser.new_page()
            for width, font_size in ((320, 16), (700, 32), (1824, 32)):
                with self.subTest(width=width, font_size=font_size):
                    page.set_viewport_size({"width": width, "height": 1400})
                    page.emulate_media(color_scheme="light")
                    page.goto(chapter.as_uri())
                    body_style = f"margin:0;padding:0;max-width:none;font-size:{font_size}px"
                    page.locator("body").evaluate("(e,s) => e.setAttribute('style',s)", body_style)
                    page.locator("table.system-window").evaluate_all("es => document.body.replaceChildren(...es)")
                    tables = page.locator("table.system-window")
                    baseline = [table.screenshot() for table in tables.all()]
                    # Isolate the table as a zoom web view may do: no linked CSS,
                    # no ancestor theme or custom properties, no table root class.
                    copies = tables.evaluate_all("es => es.map(e => { const copy=e.cloneNode(true); copy.removeAttribute('class'); return copy.outerHTML; }).join('')")
                    detached = chapter.with_name("detached.html")
                    detached.write_text(f'<html><head><base href="{chapter.as_uri()}"/></head>'
                                        f'<body style="{body_style}">{copies}</body></html>', encoding="utf-8")
                    page.goto(detached.as_uri())
                    for index, table in enumerate(page.locator("table").all()):
                        self.assertEqual(table.screenshot(), baseline[index])
                        self.assertEqual(table.locator("td").count(), 1)
                        self.assertEqual(table.locator(".system-dragon").count(), 2)
            browser.close()

    def test_footnote_references_are_raised_without_changing_line_height(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "notes.md"
            source.write_text("# Chapter 0\n\nText[^1].\n\n> **System**\n>\n> Panel[^2].\n\n"
                              "[^1]: Ordinary note.\n\n[^2]: System note.\n", encoding="utf-8")
            with sync_playwright() as playwright:
                browser = playwright.webkit.launch()
                page = browser.new_page(viewport={"width": 390, "height": 1000})
                for color in (False, True):
                    css = root / "book.css"
                    css.write_text(epub_stylesheet(color), encoding="utf-8")
                    epub = root / "notes.epub"
                    run_pandoc([source], epub, "epub3", css, full_color_epub=color)
                    validate_epub(epub)
                    with ZipFile(epub) as archive:
                        archive.extractall(root / "unpacked")
                    for font_size in (16, 32):
                        with self.subTest(color=color, font_size=font_size):
                            page.goto((root / "unpacked/EPUB/text/ch001.xhtml").as_uri())
                            page.add_style_tag(content=f"body {{font-size:{font_size}px;}}")
                            references = page.locator("a.footnote-ref").evaluate_all("""es => es.map(e => {
                                const p=e.closest('p'), style=getComputedStyle(e);
                                const probe=document.createElement('span');
                                probe.textContent='x'; e.before(probe);
                                const r=e.getBoundingClientRect(), b=probe.getBoundingClientRect();
                                const height=p.getBoundingClientRect().height;
                                const copy=p.cloneNode(true); copy.querySelector('a.footnote-ref').remove();
                                p.after(copy);
                                const without=copy.getBoundingClientRect().height;
                                copy.remove(); probe.remove();
                                return {font:parseFloat(style.fontSize), parentFont:parseFloat(getComputedStyle(p).fontSize),
                                    align:style.verticalAlign, raised:r.top+r.height/2 < b.top+b.height/2,
                                    height,without,target:!!document.getElementById(e.hash.slice(1)),
                                    nested:e.children.length,inline:e.getAttribute('style'),
                                    inWindow:!!e.closest('table.system-window')};
                            })""")
                            self.assertEqual(len(references), 2)
                            for reference in references:
                                self.assertEqual(reference["align"], "super")
                                self.assertAlmostEqual(reference["font"] / reference["parentFont"], 0.75, delta=0.01)
                                self.assertTrue(reference["raised"])
                                self.assertAlmostEqual(reference["height"], reference["without"], delta=0.1)
                                self.assertTrue(reference["target"])
                                self.assertEqual(reference["nested"], 0)
                                if reference["inWindow"]:
                                    self.assertIn("vertical-align: super", reference["inline"])
                browser.close()

    def test_crest_stays_on_the_same_page_as_its_table(self):
        from playwright.sync_api import sync_playwright

        # Leave too little room at the end of the first CSS column for a panel,
        # forcing the table to the next page as in the user's picture 7.
        source = ("# Chapter 0\n\nBefore.\n\n> **System**\n>\n"
                  "> **Quest**\n>\n> Gather basic information.\n>\n"
                  "> - Grade: Tutorial\n> - Rewards: Uniform\n\nAfter.\n")
        with color_chapter(source) as chapter, sync_playwright() as playwright:
            browser = playwright.webkit.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 750})
            for width, font_size in ((320, 16), (390, 24), (700, 32)):
                for remaining in (5, 40, 100):
                    with self.subTest(width=width, font_size=font_size, remaining=remaining):
                        page.goto(chapter.as_uri())
                        page.add_style_tag(content=(
                            "body {margin:0;padding:0;max-width:none;}"
                            f"section.level1 {{column-width:{width}px;column-gap:40px;column-fill:auto;"
                            f"width:{width}px;height:650px;font-size:{font_size}px;}}"
                            "section.level1 > h1, section.level1 > p {display:none;}"
                        ))
                        page.locator("section.level1").evaluate("""(section, height) => {
                            const spacer=document.createElement('div');
                            spacer.style.height=height+'px';
                            section.insertBefore(spacer,section.querySelector('table'));
                        }""", 650 - remaining)
                        result = page.locator("table.system-window").evaluate("""table => {
                            const r=table.getBoundingClientRect();
                            const header=table.querySelector('.system-header').getBoundingClientRect();
                            return {left:r.left,top:r.top,bottom:r.bottom,parts:table.getClientRects().length,
                                headerTop:header.top,headerBottom:header.bottom,
                                dragons:[...table.querySelectorAll('.system-dragon')].map(e=>{
                                    const d=e.getBoundingClientRect();
                                    return {left:d.left,right:d.right,top:d.top,bottom:d.bottom};
                                })};
                        }""")
                        self.assertGreaterEqual(result["left"], width + 40)
                        self.assertEqual(result["parts"], 1)
                        self.assertGreaterEqual(result["top"], 0)
                        self.assertLessEqual(result["bottom"], 650)
                        for dragon in result["dragons"]:
                            self.assertGreaterEqual(dragon["left"], result["left"])
                            self.assertGreaterEqual(dragon["top"], result["headerTop"])
                            self.assertLessEqual(dragon["bottom"], result["headerBottom"])
            browser.close()


if __name__ == "__main__":
    unittest.main()
