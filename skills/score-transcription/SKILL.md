---
name: score-transcription
description: "Convert scanned or photographed sheet music into editable MusicXML using optical recognition, visual score reading, and rendered proofreading. Use for score transcription and correction of scan-derived MusicXML, including multi-staff music and lyric underlay."
---

# Score Transcription

Deliver editable notation faithful to the requested musical content. Treat the scan as the source and optical recognition as a proposal. User instructions override these defaults.

## Start or resume

Read the job's state file before transcribing. It should identify the source and its hash, requested parts and lyric languages, checked coverage, inherited notation context, and unresolved decisions. For a new score, establish those facts from the source and the current request; use [the state template](assets/score-state.template.json) as a starting point.

Unless the user specifies otherwise, preserve all musical parts and independent voices, notes/rests, grace-note type, clefs, keys, meters, ties, tuplets, barlines, and requested lyrics. Articulations, dynamics, pedal, expressive text, and original page layout are optional unless requested. Lyric language and instrument assignments are per-score choices; Do not inherit a previous score's lyric language or instrument assignment.

Read [tools and data format](references/tools.md) before using the bundled commands. Read [demonstrated lessons](references/lessons.md) when selecting or correcting recognition output, handling cross-staff music, or checking lyric underlay.

## Transcribe and check

- Work on identifiable measures with enough surrounding context. Retain page/system/crop coordinates and the clef, key, meter, accidental, tie, and lyric state entering a chunk. A missing staff can mean an omitted silent part. Recover context across pages before assigning pitches or durations.
- Choose OMR, direct visual transcription, or a mixture based on observed repair effort. Do not extrapolate a small pilot's recognition counts to other scores or engine versions.
- Keep explicit score data separate from the encoder. Cross-staff notes can be sequential events in one voice; vertically nearby notes are not automatically simultaneous. Encode pitch spelling, onset, duration, staff, and voice independently.
- Distinguish slashed from unslashed grace notes in the source data; generic grace recognition is insufficient. Check the final system for closing barlines and requested fermatas. Apply requested instrument assignments without altering the source pitches or lyric underlay.
- Check lyrics against the printed line, then check their note attachment separately. A syllable may span several notes. Preserve syllabic connections and extensions; do not silently modernize spelling or copy another language's syllable alignment.
- Run structural checks, render in the target notation program, and visually compare every covered passage with the source. Structural validity and a successful round trip are not proof that a pitch was read correctly. Inspect disagreements rather than using musical plausibility to overwrite the scan.
- Keep original inputs, raw OMR, editable transcription data, exports, and evidence distinct. Record unresolved readings by location with candidate interpretations; never promote them to checked through guesswork.
- A partial excerpt must document any deliberately truncated ties or lyric spans. A whole-score deliverable must resolve its internal boundaries. Do not silently discard an unsupported musical feature to make validation pass.

## Carry learning forward

After a substantive correction, update the score data and job state. If the cause generalizes, add a concise evidence-backed lesson, a regression case, or a narrowly scoped tool fix. Include the source crop, former mistake, correction, verification, and applicable tool version. Label hypotheses and unreviewed references explicitly. Re-run relevant existing cases after changes to shared tools.

Keep completion state in files as work progresses, including what remains untranscribed and which checks actually ran. At handoff, link the MusicXML, visual review, validation report, and unresolved decisions. A future session should resume from these artifacts without the conversation.

## Portability

The scripts and MusicXML schemas are bundled here. Use paths relative to this skill's resolved directory, regardless of the working directory. `scoretool.py` can discover the original workspace's `.tools` directory when this skill is symlinked there; otherwise supply `--tools` or `KENGRAVER_TOOLS`. [Tool setup](references/setup.md) contains pinned, reproducible installation instructions. Do not assume the binaries or Python dependencies accompanied a copied skill.

Current encoder and checker limits are documented in the tools reference. Extend and verify those capabilities when the source requires them; the skill does not require one fixed transcription engine or representation.
