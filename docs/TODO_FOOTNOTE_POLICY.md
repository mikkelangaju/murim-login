# TODO: Reverse the final-pass footnote priorities

Status: planned. This document describes future work; it does not change the
active final-pass instructions or existing chapters.

## Goal

Use footnotes to explain unfamiliar concepts that help readers understand the
story. Stop adding notes solely to convert ordinary modern metric quantities
into imperial units.

The current policy in [FINAL.md](../FINAL.md) does the opposite: it requires
metric conversions while explicitly banning explanations of standing series
vocabulary such as **dantian**.

## 1. Stop mandatory modern metric conversion notes

- [ ] Revise both the opening instruction under **Units** and the paragraph
  beginning “Also footnote metric quantities already in the English.” Remove
  the requirement to annotate ordinary metric measurements.
- [ ] Cover kilometers, meters, centimeters, kilograms, grams, liters, square
  meters, and degrees Celsius, including derived quantities such as km/h.
- [ ] Keep metric measurements in the prose. Do not replace the removed notes
  with imperial measurements inserted into the narrative.
- [ ] Retain explanations of unfamiliar traditional units, including their
  useful modern equivalents. A traditional-unit note that mentions meters or
  kilograms is not a conversion-only modern-unit note.
- [ ] Leave the won conversion policy and configured currency rates unchanged.
- [ ] Leave the existing geun weight explanation unchanged; this task does not
  resolve the previously discussed Korean/Chinese weight convention question.

Example: Chapter 4 should no longer need separate conversion notes for ten,
fifteen, twenty, and thirty meters. Its other cultural explanations remain
eligible.

## 2. Explain unfamiliar series vocabulary when first needed

- [ ] Replace the blanket prohibition on defining **Murim**, **qi**,
  **dantian**, **internal energy**, and **mana** with a reader-oriented rule:
  give a brief explanation at the first meaningful appearance when the term
  would otherwise be unclear.
- [ ] Make the first-use rule apply across the book, rather than automatically
  repeating the same definition in each chapter or at every occurrence.
- [ ] Skip the note when the surrounding prose already explains the concept.
  Familiar fantasy vocabulary should not receive an automatic dictionary note
  merely because the old prohibition was removed.
- [ ] Explain variants such as the Upper Dantian or qi deviation only when
  they introduce a distinct concept the reader needs at that point. Avoid
  information revealed later in the story.
- [ ] Keep definitions short, factual, spoiler-free, and consistent with the
  chapter's usage. Preserve the existing restriction on notes describing
  individual story characters, factions, places, or plot events.

Example first-use note, adapted to the available story context:

> A dantian is a center where a martial artist gathers and refines internal
> energy, usually located in the lower abdomen.

## Implementation work

- [ ] Update [FINAL.md](../FINAL.md) and align its wording with the useful,
  infrequent explanations required by [RULES.md](../RULES.md).
- [ ] Update the final packet builder in
  [tools/final_touches.py](../tools/final_touches.py) as needed. It currently
  injects `FINAL.md` into each chapter's final-pass packet.
- [ ] Provide a bounded record of terms already explained, with a defined
  persistence/update mechanism, so book-wide first-use decisions do not rely
  on model memory or require loading the entire novel.
- [ ] Add regression coverage for the two reversed policies, repeated terms,
  context that already explains a term, and mixed traditional-unit notes.
- [ ] Preserve the fixes for thought normalization, superscript references,
  references followed by colons, and final QA rejecting unused definitions.

## Existing chapters and acceptance

- [ ] Plan cleanup/backfill as a separate, explicitly scoped maintenance pass
  through the supported workflow; changing the prompt alone does not update
  already finalized chapters.
- [ ] Remove references and definitions only for notes whose sole purpose is
  converting a modern metric quantity. Preserve mixed cultural explanations.
- [ ] Add useful terminology explanations at their first meaningful locations
  without rewriting otherwise acceptable prose or adding spoilers.
- [ ] Renumber affected notes in order of appearance and verify that references
  and definitions match, with no missing or unused notes.
- [ ] Rebuild both EPUB editions and validate note links and superscript
  rendering, including inside enlarged system windows.
- [ ] Confirm that Chapter 4 retains its metric prose without the four
  conversion-only definitions, that dantian receives an appropriate first-use
  explanation, and that traditional-unit and currency policies still work.
