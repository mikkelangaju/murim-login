# Korean raw file analysis

Analyzed on 2026-11-15. The local input is `Murim login raw.txt` at the
repository root. `.gitignore` excludes this file; the Korean text is not
included in this report.

## File and chapter coverage

- Size: 15,579,949 bytes (approximately 14.86 MiB).
- Encoding: valid UTF-8 without a BOM; Windows CRLF line endings.
- File SHA-256: `e3db49e2f01ba99f82234f8e245c8317b6db15bc9ab0d9154a2e821dac981cc1`.
- Contains 1,105 chapters, numbered **0 through 1104**, inclusive.
- Chapter 0 is the short opening/prologue, followed by chapters 1–1104.
- Chapter headings are consecutive, with no missing, repeated, or reordered
  chapter numbers. There are no empty chapter bodies.
- Chapters 0–1056 use fullwidth-hash headings (`＃N화`); chapters 1057–1104
  use bare headings (`N화`). The existing chapter parser accepts both.
- No Unicode replacement characters, NUL bytes, or unexpected ASCII control
  characters were found.
- The repository contains translations numbered 0–1191. This input does not
  contain chapters **1105–1191**, a total of 87 chapters.

## Comparison with the Korean source used by this repository

Each chapter was extracted in memory using the marker and text handling in
`tools/chapter.py`: normalize line endings to LF, preserve the chapter
heading and body, strip trailing whitespace at the end of the chapter, and
append one final newline. The input file itself was not modified.

Each extracted chapter's UTF-8 SHA-256 was compared with `source_sha256` in
both `reviews/mastering/NNNN/state.json` and
`reviews/final/NNNN/state.json`.

| Reference records | Chapters compared | Exact hash matches | Mismatches |
| --- | ---: | ---: | ---: |
| Mastering | 1,105 | 1,105 | 0 |
| Final pass | 1,105 | 1,105 | 0 |

All reference records were present, and the two sets of source hashes agree
for every chapter. This establishes that the supplied chapters match the
Korean source text previously used by this repository, after its normal
chapter extraction and newline handling. This was not an independent
comparison against a publisher's edition or a review of English translation
accuracy.

## Local source installation

The raw input was split with the repository's existing tool:

```bash
python3 tools/chapter.py --split 'Murim login raw.txt'
```

This created `source/0000.txt` through `source/1104.txt`: one chapter per
file, four-digit filenames, UTF-8 encoding, LF line endings, the original
chapter heading, and one final newline. All 1,105 files were verified against
both sets of recorded source hashes and read successfully through the chapter
and context loaders. The existing `/source/` ignore rule covers every file;
none is tracked by Git.

Chapters 1105–1191 remain unavailable locally. The reader's published source
count was not changed to reflect this partial local installation.

Detailed local analysis results are in `.work/raw-file-inventory.json` and
`.work/raw-file-verification.json`, both ignored by Git. No translation,
chapter transaction, or generated continuity state was changed.
