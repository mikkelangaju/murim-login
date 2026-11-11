#!/usr/bin/env python3
"""Build HTML, PDF, and EPUB editions from translation Markdown files.

HTML is an Astro reader in ``reader/``. PDF and EPUB still go through Pandoc:
PDF uses Typst, and EPUB uses Pandoc's file-scope mode with the book stylesheet.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "translations"
DEFAULT_OUTPUT = ROOT / "build"
FILTER = ROOT / "tools" / "system-window.lua"
STYLESHEET = ROOT / "tools" / "book.css"
COLOR_STYLESHEET = ROOT / "tools" / "epub-color.css"
SIMPLE_STYLESHEET = ROOT / "tools" / "epub-simple.css"
BOOK_TYP = ROOT / "tools" / "book.typ"
TYPST_TEMPLATE = ROOT / "tools" / "typst-template.typ"
COLOPHON_TYP = ROOT / "tools" / "colophon.typ"
FONT_DIR = ROOT / "tools" / "fonts"
COVER = ROOT / "cover.jpg"
READER = ROOT / "reader"
TITLE = "Murim Login"
RIGHTS = (
    "Translation by jimzrt, licensed under CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/). "
    "Source and credit: https://github.com/jimzrt/murim-login. "
    "Based on the Korean web novel Login Murim by Zerobic. All rights in the "
    "original novel belong to its rights holders and are not covered by this license."
)


def chapter_paths(source: Path, selected: list[int] | None) -> list[Path]:
    paths = sorted(source.glob("[0-9][0-9][0-9][0-9].md"))
    if selected is None:
        return paths
    wanted = {f"{number:04d}" for number in selected}
    return [path for path in paths if path.stem in wanted]


def require_binary(name: str, install_hint: str) -> str:
    binary = shutil.which(name)
    if binary is None:
        raise RuntimeError(f"{name} is required. Install it with: {install_hint}")
    return binary


def pandoc_base(paths: list[Path], output_format: str) -> list[str]:
    pandoc = require_binary("pandoc", "sudo pacman -S pandoc-cli")
    return [
        pandoc,
        *(str(path.resolve()) for path in paths),
        "--from=markdown",
        f"--to={output_format}",
        f"--lua-filter={FILTER}",
        "--file-scope",
        "--standalone",
        "--metadata=lang=en",
    ]


def run_pandoc(
    paths: list[Path],
    output: Path,
    output_format: str,
    css: Path | None = None,
    *,
    css_ref: str | None = None,
    epub_cover: Path | None = None,
    title: str = TITLE,
    pdf: bool = False,
    include_before: list[Path] | None = None,
    full_color_epub: bool = False,
) -> None:
    command = pandoc_base(paths, output_format)
    command.append(f"--metadata=title={title}")
    command.append(f"--metadata=rights={RIGHTS}")
    if output_format == "epub3" and full_color_epub:
        command.append("--metadata=full-color-epub:true")
    if css is not None:
        command.append(f"--css={css_ref or css.name}")
    if epub_cover is not None:
        command.append(f"--epub-cover-image={epub_cover.resolve()}")
    for prelude in include_before or ():
        command.append(f"--include-before-body={prelude.resolve()}")
    if pdf:
        command.extend(
            [
                "--pdf-engine=typst",
                "--pdf-engine-opt=--root=/",
                f"--pdf-engine-opt=--font-path={FONT_DIR.resolve()}",
                f"--template={TYPST_TEMPLATE}",
                "--toc",
                "--toc-depth=1",
                "--variable=papersize:a4",
                "--variable=fontsize:11.5pt",
                "--variable=mainfont:Noto Serif",
                "--variable=margin-left:26mm",
                "--variable=margin-right:24mm",
                "--variable=margin-top:26mm",
                "--variable=margin-bottom:24mm",
            ]
        )
    output = output.resolve()
    command.extend(["--output", str(output)])
    subprocess.run(command, cwd=output.parent, check=True)
    if output_format == "epub3" and full_color_epub:
        inline_epub_windows(output)


def inline_epub_windows(path: Path) -> None:
    """Copy the authored window class rules into self-contained zoomable tables.

    This deliberately reads only the marked simple-class section, not arbitrary
    CSS selectors or theme overrides. The same declarations style page and popup.
    """
    css = COLOR_STYLESHEET.read_text(encoding="utf-8")
    section = css.split("/* BEGIN SYSTEM WINDOW INLINE", 1)[1].split("/* END SYSTEM WINDOW INLINE */", 1)[0]
    section = section.split("*/", 1)[1]
    section = re.sub(r"/\*.*?\*/", "", section, flags=re.S)
    styles = {
        name: " ".join(declarations.split())
        for name, declarations in re.findall(r"\.(system-[\w-]+)\s*\{([^{}]*)\}", section)
    }
    # Keep raised note references when Books detaches a table from chapter CSS.
    reference_style = re.search(r"\.footnote-ref\s*\{([^{}]*)\}", STYLESHEET.read_text(encoding="utf-8"))
    styles["footnote-ref"] = " ".join(reference_style.group(1).split())
    tag_classes = {
        "p": "system-paragraph", "ul": "system-list", "ol": "system-list",
        "li": "system-item", "strong": "system-emphasis", "code": "system-code",
    }
    ns = "{http://www.w3.org/1999/xhtml}"
    ET.register_namespace("", ns[1:-1])
    ET.register_namespace("epub", "http://www.idpf.org/2007/ops")
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        target = Path(directory) / path.name
        with ZipFile(path) as source, ZipFile(target, "w") as output:
            for entry in source.infolist():
                data = source.read(entry)
                if entry.filename.endswith(".xhtml"):
                    doc = ET.fromstring(data)
                    windows = doc.findall(f".//{ns}table[@class='system-window']")
                    for window in windows:
                        for element in window.iter():
                            classes = element.get("class", "").split()
                            tag_class = tag_classes.get(element.tag.removeprefix(ns))
                            if tag_class:
                                classes.append(tag_class)
                            if "system-body" in classes and len(element):
                                last = element[-1]
                                last.set("class", (last.get("class", "") + " system-last").strip())
                            declarations = [styles[name] for name in classes if name in styles]
                            if declarations:
                                element.set("class", " ".join(classes))
                                element.set("style", "; ".join(filter(None, [element.get("style", ""), *declarations])))
                    if windows:
                        data = ET.tostring(doc, encoding="utf-8", xml_declaration=True)
                output.writestr(entry, data)
        target.replace(path)


def ensure_reader_dependencies(npm: str) -> None:
    if not (READER / "node_modules" / "astro").exists():
        subprocess.run([npm, "install"], cwd=READER, check=True)


def build_html(output: Path, selected: list[int] | None) -> list[Path]:
    npm = require_binary("npm", "install Node.js from https://nodejs.org")
    ensure_reader_dependencies(npm)
    html_root = output / "html"
    env = os.environ.copy()
    env["ASTRO_OUT_DIR"] = str(html_root.resolve())
    env["MURIM_ROOT"] = str(ROOT.resolve())
    if selected:
        env["MURIM_CHAPTERS"] = ",".join(str(number) for number in selected)
    else:
        env.pop("MURIM_CHAPTERS", None)
    subprocess.run([npm, "run", "build"], cwd=READER, check=True, env=env)
    index = html_root / "index.html"
    if not index.is_file():
        raise RuntimeError("Astro build did not produce html/index.html")
    chapters = sorted((html_root / "chapter").glob("*/index.html"))
    return [index, *chapters]


def write_pdf_cover(output: Path) -> Path:
    cover_image = (output / "cover.jpg").resolve()
    cover_typ = output / ".cover.typ"
    cover_typ.write_text(
        f"""#set page(paper: "a4", margin: 0pt, header: none, footer: none, numbering: none, fill: black)
#align(center + horizon, image("{cover_image}", width: 100%, height: 100%, fit: "contain"))
""",
        encoding="utf-8",
    )
    return cover_typ


def build_pdf(paths: list[Path], output: Path) -> Path:
    target = output / "murim-login.pdf"
    cover_typ = write_pdf_cover(output)
    try:
        run_pandoc(
            paths,
            target,
            "pdf",
            title=TITLE,
            pdf=True,
            include_before=[cover_typ, COLOPHON_TYP, BOOK_TYP],
        )
    finally:
        cover_typ.unlink(missing_ok=True)
    return target


def build_epub(paths: list[Path], output: Path, css: Path, *, full_color_epub: bool = False) -> Path:
    target = output / ("murim-login-color.epub" if full_color_epub else "murim-login.epub")
    run_pandoc(paths, target, "epub3", css, epub_cover=output / "cover.jpg", title=TITLE,
               full_color_epub=full_color_epub)
    validate_epub(target)
    return target


def validate_epub(path: Path) -> None:
    with ZipFile(path) as archive:
        documents = {}
        for name in archive.namelist():
            if name.endswith((".xhtml", ".xml", ".opf", ".ncx", ".svg")):
                try:
                    documents[name] = ET.fromstring(archive.read(name))
                except ET.ParseError as error:
                    raise ValueError(f"invalid EPUB XML in {name}: {error}") from error
        identifiers = {
            name: {element.attrib["id"] for element in root.iter() if "id" in element.attrib}
            for name, root in documents.items()
        }
        for name, root in documents.items():
            if not name.endswith(".xhtml"):
                continue
            for element in root.iter("{http://www.w3.org/1999/xhtml}a"):
                href = element.get("href")
                if href is None:
                    continue
                link = urlsplit(href)
                if link.scheme or link.netloc:
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(link.path))) if link.path else name
                if target not in archive.namelist() or (
                    link.fragment and unquote(link.fragment) not in identifiers.get(target, set())
                ):
                    raise ValueError(f"broken EPUB link in {name}: {href}")


def epub_stylesheet(full_color_epub: bool = False) -> str:
    mode = COLOR_STYLESHEET if full_color_epub else SIMPLE_STYLESHEET
    return STYLESHEET.read_text(encoding="utf-8") + "\n" + mode.read_text(encoding="utf-8")


def copy_book_assets(output: Path, *, full_color_epub: bool = False) -> Path:
    css = output / ("book-color.css" if full_color_epub else "book-simple.css")
    css.write_text(epub_stylesheet(full_color_epub), encoding="utf-8")
    shutil.copyfile(COVER, output / "cover.jpg")
    return css


def build(args: argparse.Namespace) -> list[Path]:
    paths = chapter_paths(args.source, args.chapters or None)
    if not paths:
        raise ValueError("no translation files selected")

    args.output.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []

    if args.format in {"all", "html"}:
        produced.extend(build_html(args.output, args.chapters or None))
    if args.format in {"all", "pdf", "epub"}:
        css = copy_book_assets(args.output, full_color_epub=args.full_color_epub)
        if args.format in {"all", "pdf"}:
            produced.append(build_pdf(paths, args.output))
        if args.format in {"all", "epub"}:
            produced.append(build_epub(paths, args.output, css, full_color_epub=args.full_color_epub))
    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapters", nargs="*", type=int, help="chapter numbers; default: all translation files")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--format", choices=("all", "html", "pdf", "epub"), default="all")
    parser.add_argument("--full-color-epub", action="store_true",
                        help="use illustrated blue/gold EPUB panels and yin-yang scene breaks; default: simple monochrome EPUB")
    args = parser.parse_args(argv)
    try:
        for path in build(args):
            print(path)
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
