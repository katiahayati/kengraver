# Score Lyric Gloss — a guide for singers and score editors

Put a word-aligned translation in your score so you can understand what you sing.
Original lyrics stay under their notes. The translation appears as separate,
editable text, in the original language's word order—not as another sung verse.
For example, German `im / Wald` can be glossed `in the / forest`, with each meaning
at its word's first note. A Finnish case ending may likewise need several English
words. Awkward English order is intentional; misleading meanings are not.

You can use this with an AI assistant **or supply the translations yourself**.
The Python helper places and checks text; it does not translate, contact an API,
or certify the musical transcription. It takes plain `.musicxml` (not compressed
`.mxl` or native `.mscz`). Export MusicXML from your notation editor first.

## With an assistant

In Codex, ask:

> Use $skill-installer to install skills/score-lyric-gloss from katiahayati/kengraver.

Or copy this complete folder into `~/.agents/skills/score-lyric-gloss`, preserving
any existing local installation first. Restart if the skill does not appear.
See the [official skill documentation](https://learn.chatgpt.com/docs/build-skills).
Other compatible agents can read [SKILL.md](SKILL.md) directly; installation
locations vary. No particular model is required, but language and review ability
matter. Equal quality across models has not been established.

Then provide an editable score and ask:

> Use $score-lyric-gloss to add English meanings to the German vocal line in this
> MusicXML. Keep German word order and all original lyrics and music. Use blue,
> non-italic text below the lyrics, not singable English. Save a separate learning
> copy, render it in MuseScore, check every word's alignment and readability, and
> give me a word key and notes on uncertain readings.

Specify the desired language, vocal part, verse and appearance. If your starting
point is a PDF, or the lyric underlay is wrong, first transcribe/correct it with
the separate `score-transcription` skill or a human engraver. This skill does not
perform optical recognition. You do not need the transcription skill just to
annotate an already-correct MusicXML file.

## Try it yourself: no agent, account or API key required

Requirements: Python 3 (tested with 3.12) and, for visual inspection, an editor
such as MuseScore. The helper has no third-party Python dependencies. Run these
commands **from this skill folder**; choose a new output path for your own work.

```sh
python3 scripts/gloss.py inventory examples/hello.musicxml --part P1 --verse 1
python3 scripts/gloss.py apply examples/hello.musicxml examples/hello-gloss.json --out output/hello-learning.musicxml
```

Open `output/hello-learning.musicxml` in MuseScore. You should see `hello` at the
first `hal-` note in bar 1 and `you` at `du` in bar 2, in blue. The German word
`hallo` spans a melisma and a barline: it gets **one** gloss, not a translation of
each syllable. This tiny original example is MIT-licensed, not a score excerpt.

Save a native learning copy, then export a fresh MusicXML as
`output/hello-imported.musicxml`. Check preservation of the text:

```sh
python3 scripts/gloss.py check output/hello-learning.musicxml output/hello-imported.musicxml
```

Expected: `status: pass`, `checked_glosses: 2`. This checks the text, color,
normal/italic style, part, staff and musical onset—not translation quality,
musical correctness or collisions. Always inspect the rendered score too.

## Use your own lyrics

1. Export the original score as an uncompressed MusicXML file and keep it unchanged.
2. Find the vocal part ID in the XML's `<score-part id="...">` list; `P1` is only
   the example's ID. Run `inventory` for that part and lyric verse number.
3. Copy [hello-gloss.json](examples/hello-gloss.json) to a new mapping file. Replace
   its units with the inventory's complete words in exactly the same order,
   including punctuation and repetitions. Supply a contextual translation for
   each. The script refuses missing, extra or mismatching words.
4. Use `apply` with a new output filename, then open, save, export and check as above.
   For a musical-content comparison, the companion transcription tool's `compare`
   command checks the original against the annotated file and its editor export.
5. Read every passage at normal zoom, especially word starts, melismas, dense runs
   and system/page breaks. Keep the mapping and notes so you can revise a reading
   later without redoing the alignment.

For a short adjacent-word group, use its complete source words separated by one
space in `source`. Do not regroup a whole sentence merely to make smoother English.
The helper handles one monophonic lyric stream per invocation. Multiple lyric
voices, elisions or lyrics attached to chord members need explicit adaptation;
they are rejected rather than silently interleaved. An already-annotated input is
also rejected. Begin each revision from the original, not from an editor's export
that may have dropped annotation IDs.

## Appearance and practical limits

The mapping supports `color` (hex RGB), `font_size` (points), `font_style`
(`normal` or `italic`), `placement` (`above` or `below`) and `default_y` (MusicXML
tenths, with negative values downward). The example uses `#0066CC`, 9 pt, below.
These are example choices, not universal defaults. Different editors may interpret
placement differently; the native file preserves the layout you actually checked.

MuseScore supports colored text. A very dark blue can look almost black at normal
zoom even when the saved color is correct. Check readability on the intended screen
and in print. If text collides, adjust spacing, text position or short line breaks
(`\n` in JSON); do not move the source lyric or change note durations to make room.

For full verification and translation decisions, see [SKILL.md](SKILL.md). It
distinguishes original spelling from suspected typos, contextual meaning from
dictionary guesses, and successful import from a visually checked learning score.
Only share lyrics, scans and translations you have permission to distribute.

Original code, instructions and the synthetic example are MIT-licensed. The
public distribution includes `LICENSE`; installing this folder does not install
MuseScore or change its license.
