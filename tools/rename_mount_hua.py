#!/usr/bin/env python3
"""Rename Huashan in the reading copies and terminology references.

Preview with --diff and write with --apply.
"""

from __future__ import annotations

import argparse
import re
from difflib import unified_diff
from pathlib import Path
from stat import S_IMODE

try:
    from tools.mastering import atomic_text
    from tools.run_lock import hold_audit_locks
except ModuleNotFoundError:
    from mastering import atomic_text
    from run_lock import hold_audit_locks


ROOT = Path(__file__).resolve().parents[1]
SECT = "Mount Hua Sect"
MOUNTAIN = "Mount Hua"
OLD_NAME = re.compile(r"\bHuashan\b(?: Sect\b)?", re.IGNORECASE)
TITLE = re.compile(r"(?: Divine Dragon| Gale Sword|[’']s (?:Lone Crane|Last Crane|Invincible Divine Sword))\b")
ATTRIBUTIVE = re.compile(
    r" (?:Leader|Daoists?|[Dd]isciples?|druid|elite|internal-energy technique|junior|lay disciple|"
    r"martial (?:art|arts|artist)|master|outsider|reinforcements|specialty)\b"
)
DETERMINER = re.compile(r"\b(?:the|a|an|our|their|your|a different)\s*[*_]*$", re.IGNORECASE)
SECT_LEADER = re.compile(r"Mount Hua Sect[’']s (?:(current|former|future) )?Sect Leader\b")
GLOSSARY_ROW = re.compile(r"^(\| (?P<key>화산파?) +\| )(?P<english>\*\*Huashan\*\* +)\|$", re.MULTILINE)
GLOSSARY_NAMES = {"화산파": SECT, "화산": MOUNTAIN}

# These excerpts identify uses of the place name, including travel to the mountain.
MOUNTAIN_CONTEXTS = (
    "Peak on Huashan", "Lotus Peak at Huashan", "peaks of Huashan", "peak on Huashan",
    "plum blossoms of Huashan, which he had left", "seen that fool at Huashan",
    "I left Huashan because of you", "ran away from Huashan less than two months",
    "still on Huashan", "combed through Huashan", "Huashan had nearly become a real volcano",
    "remained at Huashan", "lived on Huashan", "born on Huashan", "came to Huashan when I was",
    "referred to Huashan, which lay near", "climbing Huashan", "Huashan was as famous for its breathtaking scenery",
    "go to Huashan, take in some lofty spirit", "Huashan is crawling with martial artists",
    "What about Huashan? What about Lotus Peak?", "Huashan! Lotus Peak!", "Huashan has been sealed off",
    "sealed Huashan tight", "searching Huashan", "since leaving Huashan", "Huashan, one of the Five Sacred Mountains",
    "cooped up on Huashan", "Set fire to Huashan", "Huashan is practically your home",
    "Huashan had been peaceful", "blue sky over Huashan", "tour of Huashan", "grass at Huashan",
    "been happy on Huashan", "Cheongpung left Huashan and ventured", "so glad I left Huashan",
    "Huashan in Shaanxi? Or", "plum blossoms from Huashan filled the ridge", "want to return to Huashan?",
    "Huashan’s beautiful scenery", "slopes of Huashan", "Historic city near Huashan",
    "Name for Huashan among the Five Great Mountains", "Huashan peak exceeding",
    "his defeat at Huashan", "always lived on Huashan", "Great Hero Mae descended from Huashan",
)
PLACE = re.compile("|".join(map(re.escape, MOUNTAIN_CONTEXTS)))

# Preserve the source distinction where replacing the name alone would leave
# an awkward construction, a duplicate label, or the old stuttered consonant.
PHRASES = {
    "Huashan was a place he both missed and remembered with pain.":
        "The Mount Hua Sect brought back memories both fond and painful.",
    "but Huashan was still the sect he would be proud of for the rest of his life. "
    "It was a tremendous relief that Huashan had not become entangled":
        "but he would be proud of the Mount Hua Sect for the rest of his life. "
        "It was a tremendous relief that the sect had not become entangled",
    "with that magnificent Huashan martial arts": "with those magnificent Mount Hua Sect martial arts",
    "Huashan’s main sect": "the Mount Hua Sect’s main branch",
    "Sect Leader of Huashan": "Sect Leader of the Mount Hua Sect",
    "pillar of Huashan": "pillar of the Mount Hua Sect",
    "name *Huashan*": "name *Mount Hua Sect*",
    "H-Huashan? Why would you go there?": "T-the Mount Hua Sect? Why would you go there?",
    "H-Huashan’s": "M-Mount Hua’s",
    "The Huashan’s Lone Crane buff": "The buff from Mount Hua’s Lone Crane",
    "Huashan-something": "Mount Hua something-or-other",
    "our Huashan": "our Mount Hua Sect",
    "*your* Huashan": "*your* Mount Hua Sect",
    "Huashan–Zhongnan": "Mount Hua–Zhongnan",
    "Zhongnan–Huashan": "Zhongnan–Mount Hua",
    "junior_martial_artist_to_Huashan_elite": "junior_martial_artist_to_mount_hua_sect_elite",
}
SPECIAL_PHRASE = re.compile("|".join(map(re.escape, PHRASES)))


def rename_line(line: str, *, include_articles: bool) -> str:
    line = SPECIAL_PHRASE.sub(lambda match: PHRASES[match[0]], line)
    place_spans = [match.span() for match in PLACE.finditer(line)]

    def replacement(match: re.Match[str]) -> str:
        start, end = match.span()
        if any(left <= start < right for left, right in place_spans) or TITLE.match(line, end):
            return MOUNTAIN
        if not include_articles or DETERMINER.search(line[:start]) or ATTRIBUTIVE.match(line, end):
            return SECT
        prefix = line[:start].rstrip(" \t*_'‘“>\"")
        sentence_start = not prefix or prefix.endswith((".", "?", "!"))
        return ("The " if sentence_start else "the ") + SECT

    renamed = OLD_NAME.sub(replacement, line)
    return SECT_LEADER.sub(lambda match: f"{match[1]} {SECT} Leader" if match[1] else f"{SECT} Leader", renamed)


def rename_document(path: Path, text: str) -> str:
    if path.name == "compendium.md":
        def replace_glossary_row(match: re.Match[str]) -> str:
            english = f"**{GLOSSARY_NAMES[match['key']]}**"
            return f"{match[1]}{english.ljust(len(match['english']))}|"

        return GLOSSARY_ROW.sub(replace_glossary_row, text)
    include_articles = path.name != "NAMES.md"
    return "".join(
        rename_line(line, include_articles=include_articles) for line in text.splitlines(keepends=True)
    )


def plan(root: Path) -> list[tuple[Path, str, str]]:
    chapters = sorted((root / "translations").glob("[0-9][0-9][0-9][0-9].md"))
    references = [root / "compendium.md", root / "docs/NAMES.md", root / "docs/ADDRESS.md"]
    references.extend(sorted((root / "characters").glob("*.md")))
    changes = []
    for path in [*references, *chapters]:
        original = path.read_text(encoding="utf-8")
        updated = rename_document(path, original)
        if OLD_NAME.search(updated):
            raise ValueError(f"Old name remains in {path.relative_to(root)}")
        if original != updated:
            changes.append((path, original, updated))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--diff", action="store_true", help="show the proposed changes")
    args = parser.parse_args()
    try:
        with hold_audit_locks(ROOT, holder="rename-mount-hua", stage="terminology"):
            changes = plan(ROOT)
            if args.apply:
                for path, before, _ in changes:
                    if path.read_text(encoding="utf-8") != before:
                        raise ValueError(f"File changed during planning: {path.relative_to(ROOT)}")
            for path, before, after in changes:
                if args.diff:
                    label = str(path.relative_to(ROOT))
                    diff = unified_diff(
                        before.splitlines(keepends=True), after.splitlines(keepends=True),
                        fromfile=label, tofile=label, n=0,
                    )
                    print("".join(diff), end="")
                if args.apply:
                    mode = S_IMODE(path.stat().st_mode)
                    atomic_text(path, after)
                    path.chmod(mode)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    chapters = sum(path.parent.name == "translations" for path, _, _ in changes)
    action = "Updated" if args.apply else "Would update"
    print(f"{action} {chapters} reading copies and {len(changes) - chapters} reference files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
