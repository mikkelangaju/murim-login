#!/usr/bin/env python3
"""Remove metric/imperial conversion footnotes from published reading copies.

Preview: python3 tools/remove_conversion_footnotes.py
Apply:   python3 tools/remove_conversion_footnotes.py --apply

Traditional-unit and cultural explanations survive, with imperial equivalents
removed. References to deleted notes are removed without renumbering other notes.
Historical review artifacts, source files, and workflow state are never edited.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_lock import hold_audit_locks

DEFINITION = re.compile(r"^ {0,3}\[\^(?P<id>[^\]]+)\]:[ \t]*(?P<body>.*)$", re.MULTILINE)
REFERENCE = re.compile(r"\[\^([^\]]+)\]")
METRIC = re.compile(
    r"\b(?:(?:milli|centi|kilo)?met(?:er|re)s?|(?:kilo)?grams?|"
    r"(?:milli)?lit(?:er|re)s?|Celsius|metric tons?|megatons?|km|cm|mm|kg|mg|ml|m|g)(?:[²³])?\b",
    re.IGNORECASE,
)
IMPERIAL_UNIT = (
    r"(?:feet|foot|inches?|miles?|yards?|pounds?|fahrenheit|gallons?|ounces?|"
    r"acres?|ft|mi|yd|lbs?|oz|mph|in)(?:[²³])?\b"
)
IMPERIAL = re.compile(
    r"\b(?:feet|foot|inches?|miles?|yards?|pounds?|fahrenheit|gallons?|ounces?|"
    r"acres?|ft|mi|yd|lbs?|oz|mph)(?:[²³])?\b|\d\s*in\b|(?:US|short|long) tons?",
    re.IGNORECASE,
)
IMPERIAL_VALUE = re.compile(
    r"\b\d[\d,.]*(?:[–-]\d[\d,.]*)?\s+"
    r"(?:(?:US|short|long|square|cubic|fl|fluid|degrees?|million)\s+)*"
    + IMPERIAL_UNIT,
    re.IGNORECASE,
)
CONTEXT = re.compile(
    r"\b(?:jang|zhang|ja|cheok|chi|li|ri|geun|jin|catty|catties|pyeong|seom|"
    r"nyang|don|hop|handspan|hand span|ppyeom|officetel|big three|Korean gym talk)\b",
    re.IGNORECASE,
)
ALTERNATIVE = re.compile(
    r",?\s+or\s+(?:(?:about|approximately|roughly)\s+)?" + IMPERIAL_VALUE.pattern,
    re.IGNORECASE,
)


def is_conversion(text: str) -> bool:
    return bool(METRIC.search(text) and IMPERIAL.search(text))


def clean_note(body: str) -> str | None:
    """None means delete the entire note; otherwise return its retained content."""
    if not is_conversion(body):
        return body
    if not CONTEXT.search(body):
        return None

    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“])", body):
        if is_conversion(sentence) and not CONTEXT.search(sentence):
            continue
        # A cultural explanation may end with a conversion after a semicolon.
        sentence = re.sub(
            r";\s*([^;]+)$",
            lambda m: "." if is_conversion(m[1]) and not CONTEXT.search(m[1]) else m[0],
            sentence,
        )
        sentence = re.sub(
            r"[ \t]+\([^()]*\)",
            lambda m: "" if IMPERIAL_VALUE.search(m[0]) and not METRIC.search(m[0]) else m[0],
            sentence,
        )
        sentence = ALTERNATIVE.sub("", sentence)
        if IMPERIAL_VALUE.search(sentence):
            raise ValueError(f"Unrecognized mixed conversion note: {body}")
        kept.append(sentence)
    return " ".join(kept) or None


def definitions(text: str) -> list[tuple[re.Match, int]]:
    """Include indented continuation lines and any intervening blank lines."""
    found = []
    for match in DEFINITION.finditer(text):
        end = match.end()
        cursor = end + (text[end:end + 1] == "\n")
        while cursor < len(text):
            line_end = text.find("\n", cursor)
            line_end = len(text) if line_end == -1 else line_end + 1
            line = text[cursor:line_end]
            if line.startswith(("    ", "\t")) and line.strip():
                end = line_end
            elif line.strip():
                break
            cursor = line_end
        found.append((match, end))
    return found


def prose(text: str) -> str:
    for match, end in reversed(definitions(text)):
        text = text[:match.start()] + text[end:]
    return REFERENCE.sub("", text).rstrip()


def transform(text: str) -> tuple[str, list[dict]]:
    changes = []
    removed = set()
    candidate = text
    for match, end in reversed(definitions(text)):
        body = text[match.start("body"):end].rstrip()
        cleaned = clean_note(body)
        if cleaned == body:
            continue
        label = match["id"]
        changes.append({"id": label, "before": body, "after": cleaned})
        if cleaned is None:
            removed.add(label)
            # Consume the definition's newline and following empty lines.
            while end < len(text) and text[end] == "\n":
                end += 1
            replacement = ""
        else:
            replacement = text[match.start():match.start("body")] + cleaned
            if text[end - 1:end] == "\n":
                replacement += "\n"
        candidate = candidate[:match.start()] + replacement + candidate[end:]

    if not changes:
        return text, []
    candidate = REFERENCE.sub(lambda m: "" if m[1] in removed else m[0], candidate).rstrip() + "\n"
    labels = [match["id"] for match, _ in definitions(candidate)]
    refs = set(REFERENCE.findall(DEFINITION.sub("", candidate)))
    if len(labels) != len(set(labels)) or refs != set(labels):
        raise ValueError("Footnote definitions and references are duplicated or do not match")
    if prose(text) != prose(candidate):
        raise ValueError("Chapter prose changed beyond footnote references")
    return candidate, list(reversed(changes))


def run(root: Path, apply: bool, report: Path | None) -> dict:
    plans = []
    paths = sorted((root / "translations").glob("[0-9][0-9][0-9][0-9].md"))
    if not paths:
        raise ValueError(f"No chapter reading copies found under {root / 'translations'}")
    # Plan and validate the entire corpus before writing any chapter.
    for path in paths:
        original = path.read_text(encoding="utf-8")
        try:
            updated, changes = transform(original)
        except ValueError as exc:
            raise ValueError(f"{path.relative_to(root)}: {exc}") from exc
        if changes:
            plans.append((path, original, updated, changes))
    result = {
        "applied": apply,
        "chapters_scanned": len(paths),
        "chapters_changed": len(plans),
        "notes_removed": sum(item["after"] is None for *_, changes in plans for item in changes),
        "notes_trimmed": sum(item["after"] is not None for *_, changes in plans for item in changes),
        "chapters": [{"path": str(path.relative_to(root)), "changes": changes} for path, _, _, changes in plans],
    }
    if apply:
        for path, original, _, _ in plans:
            if path.read_text(encoding="utf-8") != original:
                raise ValueError(f"Reading copy changed during planning: {path}")
        for path, _, updated, _ in plans:
            path.write_text(updated, encoding="utf-8")
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: preview only)")
    parser.add_argument("--report", type=Path, help="optional JSON report of every removed or trimmed note")
    args = parser.parse_args()
    try:
        with hold_audit_locks(ROOT, holder="remove-conversion-footnotes", stage="cleanup"):
            result = run(ROOT, args.apply, args.report)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps({key: value for key, value in result.items() if key != "chapters"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
