# Kengraver

For transcription/correction, read `skills/score-transcription/SKILL.md` and
the job state before resuming. Keep source-specific facts in score data.
Ask for scope when unclear; do not inherit the examples' language or instruments.

For source-order learning translations, read `skills/score-lyric-gloss/SKILL.md`.
Keep original lyrics/music unchanged, record mappings and uncertainties per score,
and inspect actual text placement and contrast after import. Its README includes
a human-operated workflow; the helper places supplied translations, not generates them.

After shared-tool changes run `python3 -m unittest discover -s tests -v`.
Never regenerate preserved reference fixtures alongside test candidates.
Report structural/import checks separately from visual source review.
Keep private scores, credentials, installed tools and machine configuration out
of commits. Historical pilot excerpts do not represent a complete score.
