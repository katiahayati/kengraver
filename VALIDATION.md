# Release validation

## Render `.mxl` export — 2026-10-23

- `scoretool.py render --mxl` (Python: `render(..., mxl=True)`) adds a compressed
  MusicXML export from the same MuseScore import as the PDF, `.mscz` and MusicXML.
  Without the flag the exports, return value and output files are unchanged.
- 40 public tests passed, including two new render tests that stub the MuseScore
  launcher and check the export list with and without `--mxl`. The development
  suite passed 157 tests, and the preserved three-excerpt pilot regression passed.
- With MuseScore 4.7.4, the public CLI rendered the bundled gloss example with
  `--mxl`, and `validate --roundtrip` accepted the `.mxl` directly (schema, timing,
  ties and strict musical comparison).
- In development use, an `.mxl` exported later from the saved `.mscz` differed from
  the import-time `.mxl` only in layout hints (coordinates, system spacing, tuplet
  bracket display); the strict musical comparison passed on both.

## Lyric-gloss addition — 2026-09-07

- 38 public tests passed, including seven portable gloss tests and the unchanged
  transcription/preserved-reference tests. The development suite passed 112 tests.
- The standalone gloss skill passed frontmatter validation. Its helper runs with
  Python's standard library; validation reused a separate local PyYAML install.
- The original two-bar German example was annotated using the published commands,
  rendered in MuseScore 4.7.4 and visually inspected: `hello` starts at `hal-` in
  bar 1, and `you` at `du` in bar 2. Both blue, normal-style glosses survived export
  at their exact musical anchors. Strict musical round-trip comparison passed.
- An initial example omitted a MIDI program; MuseScore supplied one, which the
  strict checker correctly flagged. The final example explicitly declares its
  playback program. No shared musical checks were weakened.
- This addition contains the reusable gloss instructions/helper, human guide,
  synthetic example, MIT license and tests. It does not publish complete working
  scores or their translations, private operations or workstation configuration.
  The existing public transcription implementation and fixtures are unchanged.

Testing reused local Linux tools, with a sequential memory-bounded render; no
cloud instance or translation API was used. The example is a packaging smoke
test, not a multilingual accuracy benchmark. The guide documents the separate
translation, text-preservation, musical-consistency and visual-review checks.

## Initial transcription release — 2026-09-06

The clean export was exercised outside the development workspace on Ubuntu
24.04 / Python 3.12:

- 31 public tests passed: 27 encoder/checker tests (including three preserved
  source-reviewed pilot fixtures) and four synthetic accidental-state tests.
- Skill frontmatter validation passed.
- The two-measure opening rebuilt and passed strict MuseScore 4.7.4 round-trip
  comparison, including all 48 pitched entries and visible rest coverage.
- The opening render was inspected. This is a packaging smoke test, not a new
  full-score visual audit or an independent model transcription trial.
- The separate development suite still passed all 92 tests. Those full-score
  and infrastructure tests are not all included in this public release.

Runtime testing reused installed Python dependencies and MuseScore binaries.
A fresh download/install, other operating systems, and Sol score-reading accuracy
were not tested for this release. Review criteria and known tool limitations
remain in the skill; a green structural check is not proof of fidelity to a scan.
