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
                            self.assertEqual(sum("footnote-ref" in element.get("class", "").split()
                                                 for element in doc.iter(f"{NS}a")), 1)
                            self.assertEqual(len(doc.findall(f".//{NS}li")), 2)
                            body = next(element for element in doc.iter()
                                        if "system-body" in element.get("class", "").split())
                            text.append(" ".join("".join(body.itertext()).split()))
                            if color:
                                window = next((element for element in doc.iter(f"{NS}div")
                                               if "system-window" in element.get("class", "").split()), None)
                                self.assertIsNotNone(window)
                                self.assertEqual(window.get("lang"), "en")
                                # Normal blocks bypass Books' recoloring native table viewer.
                                self.assertFalse(window.findall(f".//{NS}table"))
                                self.assertIn("ibooks-dark-theme-use-custom-text-color",
                                              window.find(f".//{NS}div").get("class", "").split())
                                for element in window.iter():
                                    if element.tag != f"{NS}img":
                                        self.assertIn("ibooks-dark-theme-use-custom-text-color",
                                                      element.get("class", "").split())
                                    self.assertIn("color: #ffffff !important", element.get("style", ""))
                                    self.assertIn("-webkit-text-fill-color: #ffffff !important", element.get("style", ""))
                                    self.assertIn('font-family: Georgia, "Times New Roman", serif !important',
                                                  element.get("style", ""))
                                    if "system-" in element.get("class", ""):
                                        self.assertTrue(element.get("style"))
                                self.assertEqual(len(doc.findall(f".//{NS}img[@class='system-dragon']")), 2)
                                self.assertEqual(len(doc.findall(f".//{NS}div[@class='scene-separator']")), 1)
                                opener = next(element for element in window.iter(f"{NS}a")
                                              if "system-open" in element.get("class", "").split())
                                popup_path = "EPUB/text/" + opener.get("href")
                                popup = ET.fromstring(archive.read(popup_path))
                                popup_body = next(element for element in popup.iter()
                                                  if "system-body" in element.get("class", "").split())
                                self.assertEqual("".join(body.itertext()), "".join(popup_body.itertext()))
                                self.assertFalse(popup.findall(f".//{NS}table"))
                                self.assertTrue(popup.find(f"{NS}head/{NS}style").text)
                                opf = "{http://www.idpf.org/2007/opf}"
                                package_name = next(n for n in archive.namelist() if n.endswith(".opf"))
                                package = ET.fromstring(archive.read(package_name))
                                item = next(element for element in package.iter(f"{opf}item")
                                            if element.get("href") == "text/" + opener.get("href"))
                                self.assertIn("scripted", item.get("properties", "").split())
                                self.assertIsNotNone(popup.find(f"{NS}head/{NS}script"))
                                reference = next(element for element in package.iter(f"{opf}itemref")
                                                 if element.get("idref") == item.get("id"))
                                self.assertEqual(reference.get("linear"), "no")
                            else:
                                self.assertIsNotNone(doc.find(f".//{NS}div[@class='system-window-simple']"))
                                self.assertFalse(doc.findall(f".//{NS}table"))
                                self.assertFalse(doc.findall(f".//{NS}img"))
                                self.assertEqual(len(doc.findall(f"./{NS}body/{NS}section[@class='level1']/{NS}hr")), 1)
                        bodies.append(text)
            self.assertEqual(bodies[0], bodies[1])


if __name__ == "__main__":
    unittest.main()
