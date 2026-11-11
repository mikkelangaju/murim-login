import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from tools.build import BOOK_TYP, COLOPHON_TYP, COVER, READER, RIGHTS, TYPST_TEMPLATE, chapter_paths, epub_stylesheet, pandoc_base, run_pandoc, validate_epub, write_pdf_cover


class BuildToolTest(unittest.TestCase):
    def test_epub_ornaments_have_real_transparency(self):
        from PIL import Image

        ornaments = READER / "src" / "ornaments"
        names = ("dragon.png", "dragon-flip.png", "corner-tl.png", "corner-tr.png", "corner-bl.png", "corner-br.png", "yin-yang.png")
        for name in names:
            with self.subTest(name=name), Image.open(ornaments / name) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                self.assertGreaterEqual(image.width, 120)

    def test_dragon_outline_is_not_clipped_by_the_canvas(self):
        from PIL import Image

        for name in ("dragon.png", "dragon-flip.png"):
            with self.subTest(name=name), Image.open(READER / "src/ornaments" / name) as image:
                bounds = image.getchannel("A").getbbox()
                self.assertIsNotNone(bounds)
                left, top, right, bottom = bounds
                self.assertGreater(left, 0)
                self.assertGreater(top, 0)
                self.assertLess(right, image.width)
                self.assertLess(bottom, image.height)

    def test_epub_scene_break_embeds_yin_yang(self):
        import posixpath

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "chapter.md"
            source.write_text("# Chapter 0\n\nBefore.\n\n---\n\nAfter.\n", encoding="utf-8")
            target = Path(temp) / "book.epub"
            run_pandoc([source], target, "epub3", full_color_epub=True)
            validate_epub(target)
            ns = "{http://www.w3.org/1999/xhtml}"
            with ZipFile(target) as archive:
                name = "EPUB/text/ch001.xhtml"
                root = ET.fromstring(archive.read(name))
                separators = root.findall(f".//{ns}div[@role='separator']")
                self.assertEqual(len(separators), 1)
                self.assertEqual(len(root.findall(f".//{ns}hr")), 0)
                image = separators[0].find(f".//{ns}img")
                self.assertEqual(image.get("class"), "scene-separator-art")
                embedded = posixpath.normpath(posixpath.join(posixpath.dirname(name), image.get("src")))
                self.assertEqual(archive.read(embedded), (READER / "src/ornaments/yin-yang.png").read_bytes())

    def test_epub_splits_chapters_and_keeps_reused_note_labels_local(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / f"{number:04d}.md" for number in (0, 1)]
            for number, path in enumerate(paths):
                path.write_text(f"# Chapter {number}\n\nText[^1].\n\n[^1]: Note for chapter {number}.\n", encoding="utf-8")
            target = Path(temp) / "book.epub"
            run_pandoc(paths, target, "epub3")
            validate_epub(target)
            with ZipFile(target) as archive:
                chapters = sorted(n for n in archive.namelist() if n.startswith("EPUB/text/ch") and n.endswith(".xhtml"))
                self.assertEqual(len(chapters), 2)
                for number, name in enumerate(chapters):
                    root = ET.fromstring(archive.read(name))
                    notes = root.findall(".//{http://www.w3.org/1999/xhtml}aside")
                    self.assertEqual(len(notes), 1)
                    self.assertIn(f"Note for chapter {number}.", "".join(notes[0].itertext()))

    def test_epub_validation_rejects_missing_link_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "broken.epub"
            for href in ("#missing-note", "missing.xhtml#fn1"):
                with ZipFile(target, "w") as archive:
                    archive.writestr("EPUB/text/ch001.xhtml", f'<html xmlns="http://www.w3.org/1999/xhtml"><a href="{href}">1</a></html>')
                with self.assertRaisesRegex(ValueError, "broken EPUB link"):
                    validate_epub(target)

    def test_epub_raw_breaks_produce_valid_xhtml(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "chapter.md"
            source.write_text("# Chapter 0\n\nBefore\n\n<br>\n\n**<Peace Guild>**\n\nAfter\n", encoding="utf-8")
            target = Path(temp) / "book.epub"
            run_pandoc([source], target, "epub3")
            validate_epub(target)
            with ZipFile(target) as archive:
                content = b"".join(archive.read(n) for n in archive.namelist() if n.endswith(".xhtml"))
            self.assertIn(b"<br />", content)
            self.assertIn(b"&lt;Peace Guild&gt;", content)

    def test_epub_validation_rejects_mismatched_tags(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "broken.epub"
            with ZipFile(target, "w") as archive:
                archive.writestr("EPUB/text/ch001.xhtml", "<html><p><br></p></html>")
            with self.assertRaisesRegex(ValueError, "invalid EPUB XML in EPUB/text/ch001.xhtml"):
                validate_epub(target)

    def test_chapter_selection_is_numeric_and_ordered(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            for number in (3, 1, 12):
                (source / f"{number:04d}.md").write_text("# Chapter\n", encoding="utf-8")
            selected = chapter_paths(source, [12, 1])
            self.assertEqual([path.stem for path in selected], ["0001", "0012"])

    def test_default_selection_ignores_non_chapter_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / "0000.md").write_text("# Chapter\n", encoding="utf-8")
            (source / "notes.md").write_text("# Notes\n", encoding="utf-8")
            self.assertEqual([path.stem for path in chapter_paths(source, None)], ["0000"])

    def test_combined_exports_use_file_scope_for_chapter_local_notes(self):
        command = pandoc_base([Path("0001.md"), Path("0002.md")], "epub3")
        self.assertIn("--file-scope", command)

    def test_cover_asset_exists(self):
        self.assertTrue(COVER.is_file())

    def test_pdf_cover_does_not_insert_a_blank_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            text = write_pdf_cover(Path(temp)).read_text(encoding="utf-8")
        self.assertIn("#set page", text)
        self.assertIn(" image(", text)
        self.assertIn('fit: "contain"', text)  # the title lettering is part of the 2:3 cover; never crop it
        self.assertNotIn("#pagebreak", text)

    def test_ebooks_carry_license_and_source_credit(self):
        for text in (RIGHTS, COLOPHON_TYP.read_text(encoding="utf-8")):
            self.assertIn("CC BY 4.0", text)
            self.assertIn("https://github.com/jimzrt/murim-login", text)
            self.assertIn("Zerobic", text)

    def test_html_reader_scaffold_exists(self):
        self.assertTrue((READER / "package.json").is_file())
        self.assertTrue((READER / "astro.config.ts").is_file())
        self.assertTrue((READER / "src" / "pages" / "chapter" / "[id].astro").is_file())

    def test_pdf_system_ornaments_exist(self):
        self.assertTrue((READER / "src" / "ornaments" / "corner.svg").is_file())
        self.assertTrue((READER / "src" / "ornaments" / "dragon.svg").is_file())
        lua = (READER.parent / "tools" / "system-window.lua").read_text(encoding="utf-8")
        self.assertIn("ornament(\"corner.svg\")", lua)
        self.assertIn("ornament(\"dragon.svg\")", lua)
        self.assertIn("murim-plaque", lua)
        self.assertIn('dragon.png', lua)
        self.assertIn('dragon-flip.png', lua)
        self.assertIn('corner-tl.png', lua)
        self.assertIn('system-crest', lua)
        self.assertTrue((READER / "src" / "ornaments" / "dragon.png").is_file())
        self.assertTrue((READER / "src" / "ornaments" / "dragon-flip.png").is_file())
        for name in ("corner-tl.png", "corner-tr.png", "corner-bl.png", "corner-br.png"):
            self.assertTrue((READER / "src" / "ornaments" / name).is_file(), name)
        self.assertTrue(BOOK_TYP.is_file())
        book = BOOK_TYP.read_text(encoding="utf-8")
        self.assertIn("#let murim-plaque", book)
        self.assertIn('font: ("Noto Sans", "Noto Sans Mono")', book)
        self.assertIn('rgb("#3470aa")', book)
        self.assertIn('rgb("#2d6aad")', book)
        self.assertNotIn('rgb("#245a96")', book)
        css = epub_stylesheet(True)
        self.assertNotIn("#20242b", css)
        self.assertNotIn("--paper", css)
        self.assertNotIn("color-scheme: light", css)
        self.assertIn("color: inherit", css)
        self.assertNotIn("#3470aa", css)
        self.assertIn("#e6c86a", css)
        self.assertIn("sans-serif", css)
        self.assertNotIn("Courier", css)
        self.assertIn("text(style: \"italic\"", book)
        self.assertIn("pagebreak(weak: true)", book)
        self.assertIn("it.outlined", book)
        self.assertIn("#counter(page).update(1)", book)
        self.assertIn('paper: "a4"', book)
        self.assertIn("pad(x: 8%", book)
        self.assertTrue(TYPST_TEMPLATE.is_file())
        template = TYPST_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("$template.typst()", template)
        self.assertNotIn("  title: [$title$],", template)
        self.assertIn("#set document(title: [$title$])", template)
        self.assertIn("title: [Contents]", template)
        self.assertIn("Page geometry is owned", template)


if __name__ == "__main__":
    unittest.main()
