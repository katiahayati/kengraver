# Lessons from reviewed transcriptions

These lessons arose from Luonnotar and Frühlingsfeier voice-and-piano work with
Audiveris 5.11.0 and MuseScore 4.7.4. Review was by agents and the user, not an
independent engraver accuracy study. The bundled Luonnotar excerpts are historical
pilot references. Full-score Frühlingsfeier evidence is not bundled in this release.

## Read staff, clef and time independently

In the [opening crop](../assets/cases/opening.png), alternating staff events
form one sequential stream, not simultaneous chords. Both piano staves are in
treble clef. Compare [reviewed MusicXML](../assets/cases/01-opening.musicxml).

At the [vocal entry](../assets/cases/vocal-entry.png), OMR missed a bass-clef
change and advanced piano attacks by an eighth. The [lead-in](../assets/cases/vocal-lead-in.png)
supplies context; [reviewed notation](../assets/cases/02-vocal-entry.musicxml)
documents truncated excerpt-boundary ties. A [dense passage](../assets/cases/dense-piano.png)
also lost a clef change and chord notes; [reference](../assets/cases/03-dense-piano.musicxml).
An isolated page may inherit a different meter from earlier pages. Do not infer
pitch from which hand plays, or durations from horizontal spacing alone.

## Lyrics require text and attachment checks

OCR confuses letters and syllabic properties independently. In the
[lyric-span example](../assets/cases/lyric-span.png), Finnish `vuot-ta` spans
three notes; the middle note has no repeated syllable. Its German translation
has different alignment. [Reference](../assets/cases/04-lyric-span.musicxml).
Within-word melismas and word extenders are not interchangeable. MuseScore may
normalize extender serialization; investigate differences without suppressing
lyric checks. Read the requested language, not the most convenient printed line.

## A valid bar can still be wrong

In [this piano source](../assets/cases/late-rhythm-source.png), two dotted quarters
and a whole note overfill 3/2. Removing the first two dots seems plausible, but
[orchestral corroboration](../assets/cases/late-rhythm-corroboration.png) supports
shortening the last note to a dotted half instead. A related source can help;
an arrangement is not obliged to match orchestration everywhere. Record editorial
choices and unresolved readings explicitly.

## Grace slashes and closing notation need source checks

User review caught acciaccaturas encoded as appoggiaturas despite a faithful
round trip. A generic grace token had hard-coded `slash: false`.
[Source slash](../assets/cases/grace-slash-source.png). Encode slash choice
explicitly, test both forms, and reject ambiguous adapter tokens. Do not turn
one score's all-slashed inventory into a universal default.

Check the ending for final bars and fermatas, and each internal double bar
against the print. Key changes do not automatically imply double bars. Do not
add a fermata to every staff because one staff has one.

## Separate accidental review from rhythmic review

The later Frühlingsfeier audit caught wrong pitches after successful strict
import checks. Review key signatures, printed glyph ownership, carry and resets
as a separate pass, particularly after decoding dense beaming or sustains.

- An unmarked pitch can inherit a key-signature sharp.
- A same-staff, same-octave accidental can carry across independent voices.
- An explicit natural cancels the prior alteration; a nearly repeated figure
  in the next bar may deliberately differ.
- Carry is octave- and staff-specific; bar boundaries reset ordinary accidental
  state to the key signature. Handle continuing ties with their own context.
- Assign each printed accidental to the correct chord member by vertical staff
  position; a nearby sharp or natural does not apply to the whole chord.

The source-data correction, not a change to the shared encoder, fixed these
errors. Synthetic tests demonstrate state handling but cannot prove that a scan
was read correctly. Add source-derived expected pitches when correcting a job.

## Tuplets, ties and complete assemblies

A tiny septuplet label explained an apparently overfull run. Count tuplet rests
as well as pitches, and inspect each chord member's tie independently. For
staggered arpeggio attacks tied to a held chord, overlapping voices may be needed
to sustain every attack continuously to its destination. Document this notation
normalization; do not automatically extend untied arpeggios.

Measured tremolo endpoints can both tie into a following chord. Ordinary
sequential short notes do not preserve both ties. Native measured tremolos use
a 2:1 time modification that is not a normal tuplet; check pair timing, strokes
and both endpoint ties.

MuseScore 4.7.4 moved grace notes or added visible rests in earlier bars after
later cross-staff voices were added. Test the assembled score after extending
it, not only isolated excerpts. Keep musical voice identities distinct where
appropriate without hard-coding a particular numeric voice ID globally.

## Tool behavior and honest reports

Audiveris 5.11.0 could return zero after OCR language initialization failure:
inspect logs. Separate books/output directories avoid observed filename
collisions. MuseScore's Qt offscreen argument order in the launcher is deliberate
and version-specific. Voice renumbering is harmless when membership is preserved.
Invisible padding rests still count for timing, but not visible-rest comparison.
Visible moved/hidden rests must remain reported, not silently waived.

When learning from a correction, retain source location/crop, the old and new
reading, verification scope, tool version and uncertainty in the job record.
Generalize only what the evidence supports and preserve regression references.
