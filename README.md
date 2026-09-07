# Kengraver

A shareable agent skill for turning scanned sheet music into editable MusicXML:
optical recognition when useful, visual score reading, explicit transcription
data, and rendered proofreading.

This is **not a trained model or a one-click OMR service**. The agent reads and
corrects the music; the bundled tools encode and check it. Results depend on the
model, scan and review effort. Successful import can preserve a wrong reading.

## Install the skill

In Codex, ask:

> Use $skill-installer to install skills/score-transcription from katiahayati/kengraver.

Alternatively, copy the complete `skills/score-transcription` folder into
`~/.agents/skills/score-transcription`. Do not replace an existing installation
without saving its local changes. Start a new session if it is not discovered.
See the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

Then ask, for example:

> Use $score-transcription on this scan. Include all vocal and piano parts and
> the German lyrics. Page layout and expressive markings are optional. First
> transcribe a difficult representative passage, compare the render to the scan,
> and record uncertainties before continuing.

Specify any playback-instrument preference yourself; voice-to-oboe and a
particular lyric language are not universal defaults. Work is remembered through
score state files, lessons and tests, not changes to model weights.

## Tools and a reproducible example

Tested platform: Ubuntu 24.04 / Linux x86_64 / Python 3.12. Other platforms are
not verified. See [setup](skills/score-transcription/references/setup.md) for
checksum-pinned MuseScore/Audiveris installation. Binaries are not included.
OMR is optional; the encoder does not require a cloud account or model API key.

From this repository:

```sh
python3 -m venv .venv
.venv/bin/pip install -r skills/score-transcription/assets/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python skills/score-transcription/scripts/scoretool.py build scores/luonnotar/pilot/01-opening.json --out output/opening.musicxml
.venv/bin/python skills/score-transcription/scripts/scoretool.py compare tests/fixtures/luonnotar/01-opening.musicxml output/opening.musicxml
```

With the toolchain installed:

```sh
.venv/bin/python skills/score-transcription/scripts/scoretool.py render output/opening.musicxml --out output/rendered --tools /path/to/tools
.venv/bin/python skills/score-transcription/scripts/scoretool.py validate output/opening.musicxml --roundtrip output/rendered/opening.musicxml
```

Compare the rendered page to the [opening source crop](skills/score-transcription/assets/cases/opening.png).
The three JSON excerpts total nine measures, **not the full Luonnotar score**.
They are preserved historical pilot data, not the later full-score instrument
assignment. References were reviewed before the current encoder and must not
be regenerated automatically alongside candidates.

## What carries over

- A score-independent encoder/checker, exact rational timing and MusicXML schemas.
- A workflow for inherited clefs/keys, independent voices, lyric attachment,
  slashed graces, partial ties, tuplets and measured tremolos.
- [Lessons](skills/score-transcription/references/lessons.md) from two complete
  voice-and-piano transcriptions, including a separate accidental audit.
- Real source crops, reviewed MusicXML and behavioral regression tests.

Structural checks and target-application comparisons are separate from visual
source review. The development scores received agent/user review, not independent
engraver certification. This release does not establish a general accuracy rate
or equal performance across models. See [supported features and limits](skills/score-transcription/references/tools.md).

## Contributing and rights

Report a problem with a measure location, incoming notation context, source crop
you may share, current/expected reading, and tool versions. Add a regression
when the failure is deterministic. Never commit credentials or private scans.

Original code and instructions: [MIT](LICENSE). Score excerpts and bundled
schemas have separate provenance and terms: [third-party notices](THIRD_PARTY_NOTICES.md).
