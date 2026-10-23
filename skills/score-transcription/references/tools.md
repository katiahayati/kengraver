# Tools and explicit score data

Resolve `scripts/scoretool.py` relative to the skill directory. Python 3.12 was used for this package. Building uses the standard library; schema checking uses lxml, and PDF cropping/rendering uses PyMuPDF. These commands operate on explicit transcription data; they do not visually read a score for you.

```sh
python3 /path/to/skill/scripts/scoretool.py crop scan.pdf --page 3 --box 0 204 271.2 348 --dpi 300 --out source.png
python3 /path/to/skill/scripts/scoretool.py build score.json --out score.musicxml
python3 /path/to/skill/scripts/scoretool.py render score.musicxml --out rendered --tools /path/to/.tools
python3 /path/to/skill/scripts/scoretool.py render score.musicxml --out rendered --mxl
python3 /path/to/skill/scripts/scoretool.py validate score.musicxml --roundtrip rendered/score.musicxml --report validation.json
python3 /path/to/skill/scripts/scoretool.py compare reviewed.musicxml candidate.musicxml --report differences.json
python3 /path/to/skill/scripts/scoretool.py omr scan.pdf --out raw-omr --languages eng --tools /path/to/.tools
```

Crop page numbers are one-based. Crop coordinates are **PDF points**, not pixels (72 points = one inch). The crop command saves a neighboring `.source.json` with provenance. Render writes PDF, native MuseScore, exported MusicXML, and PNG pages; `--mxl` adds compressed MusicXML (`.mxl`) from the same import, which `validate --roundtrip` and `compare` read directly. A later export of the saved `.mscz` can differ in layout hints (coordinates, system spacing, tuplet bracket display), so compare musical content rather than bytes. Read the resulting PNGs when proofreading. To create a review, arrange the original crops and corresponding rendered images side by side with links to editable outputs; original pagination is unnecessary.

OMR processing accepts PDF or supported image input. Choose installed OCR languages for the printed input, including secondary languages if needed for recognition. Remove unwanted languages only from the final transcription. The command checks for language initialization failures even when Audiveris exits with code 0. For full scores, preserve book context or explicitly recover inherited meter/clefs when working on isolated pages. Avoid concurrent Audiveris runs using the same state directory.

## JSON format version 1

A minimal complete score with one part, one staff, three quarters per bar, and one flat:

```json
{
  "format_version": 1,
  "title": "Example",
  "composer": "",
  "source": "scan.pdf, page 1, system 1, measure 1",
  "boundary_notes": [],
  "parts": [{
    "id": "P1", "name": "Voice", "staves": 1,
    "clefs": {"1": ["G", 2]}, "key_fifths": -1, "meter": "3/4",
    "measures": [{"number": "1", "voices": {"1": [
      {"pitches": ["F4"], "duration": "1", "staff": 1,
       "lyrics": [{"number": "1", "text": "Lu", "syllabic": "begin", "language": "it"}]},
      {"pitches": ["G4"], "duration": "1", "staff": 1},
      {"pitches": ["A4"], "duration": "1", "staff": 1,
       "lyrics": [{"number": "1", "text": "na", "syllabic": "end", "language": "it"}]}
    ]}}]
  }]
}
```

This lyric deliberately has one syllable spanning two notes. Intervening notes need not repeat the text.

- Pitches are **written** scientific pitch names (`C4` = middle C). `#`, `b`, `##`, and `bb` are supported. Spell all accidentals explicitly in the pitch data, including those implied by the key signature. Several pitches in one event are a simultaneous chord; separate events are sequential.
- Durations are exact fractions in quarter-note units: `"1/4"` is a sixteenth, `"3/2"` a dotted quarter, `"2/3"` a quarter-note triplet. Prefer strings to floating-point numbers. Divisions are calculated from the actual data.
- Empty `pitches` is a rest. A whole-measure rest has `measure_rest: true` and the actual bar duration (for example `"3"` in 3/4).
- Each voice's event list fills the current bar. Separate voices overlap in time; a voice can alternate `staff` values across staves. Staff count and clefs are per part. Missing silent voices can be omitted, but supply a whole-measure rest when an entire part is silent.
- Optional part fields: `abbreviation`, `midi_program`, `midi_channel`. Initial `meter`, `key_fifths`, and every staff's clef must be supplied explicitly.
- A measure can change `meter`, `key_fifths`, or `clefs`. Those persist to following measures. Additive meters such as `3+2/8` are supported. A pickup needs `implicit: true` and `length` in quarter units; that override applies only to that measure. All parts must have aligned measure labels and lengths.
- An event's `clef: ["F", 4]` changes its staff's clef at that event's onset. Measure-boundary clef changes use `clefs` instead. Supported clefs: G, F, and C on numbered staff lines.
- `tie` is `start`, `stop`, or `continue`; a chord event applies the tie to all its pitches. Alternatively, `pitch_ties: {"C4": "start"}` ties only named pitches; do not combine the two forms. Internal ties must meet an identical pitch in the same musical voice at the exact next onset. Cross-staff ties are allowed.
- An untimed grace event uses `duration: "0"` and `grace: {"type": "eighth", "slash": true}` for a slashed acciaccatura; use `slash: false` for an unslashed appoggiatura. Make this choice explicitly from the source, not from a generic grace default. Its written pitch, staff, type, slash and ordering are preserved, but it does not consume metrical duration. No fixed performance-time stealing is inferred. Tied grace notes, grace tuplets, and other grace timing attributes are not supported. Grace pitches are counted separately in validation reports.
- A measure's optional `right_barline` is `regular`, `light-light` (double), or `light-heavy` (final). Do not infer a double bar at every key change; read the source. Supply it in each aligned part where needed. Repeats, left/middle barlines and other styles are not supported by this writer.
- An event's optional `fermata` is `upright` or `inverted`. It emits one normal-shaped fermata for the note, chord or rest. No fixed playback hold duration is inferred; other fermata shapes and barline-attached fermatas are not yet supported by the writer.
- A measured two-note tremolo is two adjacent events in one voice, each with half the pair's total duration. Use `measured_tremolo: {"type": "start", "strokes": 2}` on the first and `"type": "stop"` on the second. Two strokes specify sixteenth-note alternation; three specify 32nds. Written values are twice each event's duration, with MusicXML's 2:1 time modification. Chords and cross-staff endpoints are supported. Endpoint ties meet the end of the entire pair, so both pitches can tie into a following held chord. The analyzer validates paired timing, written values, strokes and the ratio; its canonical events give both endpoints the pair's onset and full span, while a separate tremolo record preserves alternation order. These are notation events, not a count of performed attacks. Unmeasured, single-note, cross-bar and tuplet tremolos remain unsupported.
- A tuplet event has `tuplet: {"actual": 3, "normal": 2, "mark": "start"}`; use `mark: "continue"` for intervening events and `"stop"` on the last. `normal_type` and `number` are optional. Supply the ratio on every event in the tuplet. Ordinary dotted values are derived automatically.
- `lyrics` is a list. Each lyric can have `number`, `name`, `language`, `text`, `syllabic` (`single/begin/middle/end`), and `extend` (`start/continue/stop`). An extension-only lyric omits text. Use hyphenated syllabic connections for a syllable continuing within a word, and explicit extenders where the source indicates a word extension. Audit the rendered result, especially on tied notes and at boundaries.
- Optional notation fields: `stem` (`up/down`), `beam` (`begin/continue/end`), and `accidentals` (pitch-to-display-name map, such as `{"D5": "natural"}`). These affect the rendering; the pitch data remains authoritative.

## What a pass means

The validator checks MusicXML 4.0 schema, bar duration/alignment, and internal ties. Comparison checks pitches, timing, staff assignments, lyric text/syllabic/extension data, pitched-note voice membership (ignoring arbitrary renumbering), key/clef/meter context, tuplet ratios, grace sequence including slash, measured tremolos, nonregular barline styles, note/rest fermatas by staff and onset, MIDI programs, and rest coverage by staff and time (allowing rest subdivisions to change). It deliberately does not require fonts, spacing, pagination, or other expressive markings to survive. MIDI-program equality does not prove a native application's instrument identity; inspect that separately when instrument assignment is requested.

Review is separate from validation. Reports state that visual review is not established by a command. A round trip preserves what was encoded, including a wrong reading. Exact extender serialization can also differ between equivalent encodings; investigate a reported difference before treating it as a source-reading error.

Rest comparison concerns visible rests. Invisible `print-object="no"` padding rests are included in timing validation but excluded from printed-rest comparison; MuseScore adds these beneath cross-staff streams. Rest subdivision and arbitrary empty voice numbering are not required to match.

Current limits: unmeasured/single-note tremolos, advanced grace timing, octave-shift directions, transposing instruments, unpitched percussion, nested tuplets, polymeter, or mid-measure meter/key changes. A clearly measured two-note tremolo may alternatively be expanded into its alternating notes, with the transformation recorded in source metadata, but use native notation when endpoint ties are required. Do not invent a speed for an unmeasured tremolo. The explicit-data writer rejects unrecognized event/part fields. The checker rejects known unsupported MusicXML timing/transposition constructs rather than returning a misleading pass. Direct MusicXML editing is an option, but extend the appropriate checks and record any unverified semantics. Do not force unsupported notation into ordinary notes to pass the current checker.

Native tremolo representation follows the [MusicXML 4.0 tremolo reference](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/tremolo/). Full-file MuseScore 4.7.4 tests preserved measured pairs, strokes and endpoint ties.
