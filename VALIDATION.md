# Release validation — 2026-09-06

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
