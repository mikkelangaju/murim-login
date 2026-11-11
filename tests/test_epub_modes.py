import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from tools.build import main, validate_epub

NS = "{http://www.w3.org/1999/xhtml}"


class EpubModesTest(unittest.TestCase):
    def test_cli_builds_both_editions_without_overwriting_either(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            for number in (0, 1):
                (source / f"{number:04d}.md").write_text(
                    f"# Chapter {number}\n\nBefore[^1].\n\n"
                    "> **System**\n>\n> **Quest**\n>\n"
                    "> - Accept\n> - Decline\n\n"
                    "> An ordinary quote.\n\n---\n\n"
                    "**<Peace Guild>**\n\n<br>\n\n"
                    f"[^1]: Note for chapter {number}.\n",
                    encoding="utf-8",
                )
            output = root / "output"
            arguments = ["--format", "epub", "--source", str(source), "--output", str(output)]
            self.assertEqual(main(arguments), 0)
            simple = output / "murim-login.epub"
            original = simple.read_bytes()
            self.assertEqual(main([*arguments, "--full-color-epub"]), 0)
            self.assertEqual(simple.read_bytes(), original)
            bodies = []
            for color, target in ((False, simple), (True, output / "murim-login-color.epub")):
                with self.subTest(color=color):
                    validate_epub(target)
                    with ZipFile(target) as archive:
                        chapters = sorted(n for n in archive.namelist() if n.startswith("EPUB/text/ch") and n.endswith(".xhtml"))
                        self.assertEqual(len(chapters), 2)
                        css = "\n".join(archive.read(n).decode() for n in archive.namelist() if n.endswith(".css"))
                        self.assertIn(".footnotes > hr", css)
                        if color:
                            self.assertIn("#2d6aad", css)
                            self.assertNotIn(".system-window-simple", css)
                        else:
                            self.assertNotIn("#2d6aad", css)
                            self.assertIn("border: 1px solid currentColor", css)
                            self.assertFalse(any(n.endswith(".png") for n in archive.namelist()))
                        text = []
                        for number, name in enumerate(chapters):
                            doc = ET.fromstring(archive.read(name))
                            self.assertEqual(len(doc.findall(f".//{NS}blockquote")), 1)
                            self.assertIn(f"Note for chapter {number}.", "".join(doc.itertext()))
                            self.assertEqual(len(doc.findall(f".//{NS}a[@class='footnote-ref']")), 1)
                            self.assertEqual(len(doc.findall(f".//{NS}li")), 2)
                            body = doc.find(f".//*[@class='system-body']")
                            text.append(" ".join("".join(body.itertext()).split()))
                            if color:
                                window = doc.find(f".//{NS}table[@class='system-window']")
                                self.assertIsNotNone(window)
                                # One cell preserves Books' zoom without decorative columns.
                                self.assertEqual(len(window.findall(f".//{NS}td")), 1)
                                for element in window.iter():
                                    if "system-" in element.get("class", ""):
                                        self.assertTrue(element.get("style"))
                                self.assertEqual(len(doc.findall(f".//{NS}img[@class='system-dragon']")), 2)
                                self.assertEqual(len(doc.findall(f".//{NS}div[@class='scene-separator']")), 1)
                            else:
                                self.assertIsNotNone(doc.find(f".//{NS}div[@class='system-window-simple']"))
                                self.assertFalse(doc.findall(f".//{NS}table"))
                                self.assertFalse(doc.findall(f".//{NS}img"))
                                self.assertEqual(len(doc.findall(f"./{NS}body/{NS}section[@class='level1']/{NS}hr")), 1)
                        bodies.append(text)
            self.assertEqual(bodies[0], bodies[1])


if __name__ == "__main__":
    unittest.main()
