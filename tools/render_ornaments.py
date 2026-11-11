#!/usr/bin/env python3
"""Render transparent EPUB ornaments from the SVG masters (requires rsvg-convert)."""

from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORNAMENTS = ROOT / "reader" / "src" / "ornaments"
SVG = "{http://www.w3.org/2000/svg}"


def render(source: str, target: str, width: int, height: int, transform: str = "") -> None:
    root = ET.parse(ORNAMENTS / source).getroot()
    if transform:
        children = list(root)
        for child in children:
            root.remove(child)
        group = ET.SubElement(root, SVG + "g", {"transform": transform})
        group.extend(children)
    subprocess.run(
        ["rsvg-convert", "--width", str(width), "--height", str(height),
         "--output", str(ORNAMENTS / target)],
        input=ET.tostring(root), check=True,
    )


def main() -> None:
    if shutil.which("rsvg-convert") is None:
        raise SystemExit("Install librsvg2-bin to provide rsvg-convert")
    # Three pixels per displayed pixel keeps small details crisp on Retina screens.
    render("dragon.svg", "dragon.png", 120, 96)
    render("dragon.svg", "dragon-flip.png", 120, 96, "translate(640 0) scale(-1 1)")
    for suffix, transform in (
        ("tl", ""),
        ("tr", "translate(56 0) scale(-1 1)"),
        ("bl", "translate(0 56) scale(1 -1)"),
        ("br", "translate(56 56) scale(-1 -1)"),
    ):
        render("corner.svg", f"corner-{suffix}.png", 144, 144, transform)


if __name__ == "__main__":
    main()
