#!/usr/bin/env python3
"""Build, render, and check explicit score transcriptions; no optical reading is implied."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
import json
from math import lcm
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
TYPES = {"breve": F(8), "whole": F(4), "half": F(2), "quarter": F(1),
         "eighth": F(1, 2), "16th": F(1, 4), "32nd": F(1, 8),
         "64th": F(1, 16), "128th": F(1, 32)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sub(parent, tag, text=None, **attrs):
    node = ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})
    if text is not None:
        node.text = str(text)
    return node


def meter_length(meter):
    beats, unit = meter.split("/")
    require(int(unit) > 0, "Meter denominator must be positive")
    require(all(int(n) > 0 for n in beats.split("+")), "Meter beats must be positive")
    return F(sum(int(n) for n in beats.split("+")) * 4, int(unit))


def pitch_components(pitch):
    match = re.fullmatch(r"([A-G])(bb|##|b|#)?([0-9])", pitch)
    require(match is not None, f"Unsupported pitch {pitch!r}; use scientific spelling such as C#4")
    step, accidental, octave = match.groups()
    return step, {None: 0, "#": 1, "##": 2, "b": -1, "bb": -2}[accidental], int(octave)


def key_alter(fifths, step):
    require(-7 <= fifths <= 7, "Only standard key signatures (-7..7 fifths) are supported")
    return (1 if step in "FCGDAEB"[:fifths] else 0) if fifths >= 0 else (-1 if step in "BEADGCF"[:-fifths] else 0)


def duration_shape(event):
    if event.get('grace'):
        return event['grace'].get('type', 'eighth'), 0
    if event.get("measure_rest"):
        return "whole", 0
    duration = F(str(event["duration"]))
    if event.get('measured_tremolo'):
        duration *= 2
    tuplet = event.get("tuplet")
    if tuplet:
        require(isinstance(tuplet, dict), "Tuplets need actual, normal, and optional mark fields")
        require(int(tuplet["actual"]) > 0 and int(tuplet["normal"]) > 0, "Tuplet ratio must be positive")
        duration *= F(tuplet["actual"], tuplet["normal"])
    for name, base in TYPES.items():
        for dots in range(4):
            if duration == base * sum((F(1, 2 ** n) for n in range(dots + 1)), F()):
                return name, dots
    raise ValueError(f"Duration {event['duration']} has no supported written value; supply a tuplet ratio if needed")


def checked_spec(spec):
    require(spec.get("format_version") == 1, "Expected format_version: 1")
    require(set(spec) <= {"format_version", "title", "composer", "source", "boundary_notes", "parts"}, "Unsupported score fields")
    require(bool(spec.get("title")) and bool(spec.get("parts")), "A score needs a title and parts")
    require(len({p["id"] for p in spec["parts"]}) == len(spec["parts"]), "Part IDs must be unique")
    signatures = []
    denominators = [1]
    for part in spec["parts"]:
        require(set(part) <= {"id", "name", "abbreviation", "staves", "clefs", "key_fifths", "meter", "midi_program", "midi_channel", "measures"}, f"Unsupported part fields in {part['id']}")
        staves = part["staves"]
        require(staves >= 1 and set(map(int, part["clefs"])) == set(range(1, staves + 1)), "Supply a clef for every staff")
        key = int(part["key_fifths"])
        key_alter(key, "C")
        meter = part["meter"]
        signature = []
        require(bool(part["measures"]), "A part needs measures")
        for measure in part["measures"]:
            require(set(measure) <= {"number", "meter", "key_fifths", "clefs", "length", "implicit", "voices", "source", "right_barline"}, "Unsupported measure fields")
            require(measure.get('right_barline') in (None, 'regular', 'light-light', 'light-heavy'), 'Unsupported right barline style')
            meter = measure.get("meter", meter)
            length = F(str(measure.get("length", meter_length(meter))))
            require(length > 0, "Measure length must be positive")
            require(length == meter_length(meter) or measure.get("implicit"), "Nonstandard measure length requires implicit: true (e.g. a pickup)")
            key = int(measure.get("key_fifths", key))
            key_alter(key, "C")
            signature.append((str(measure["number"]), length, meter))
            denominators.append(length.denominator)
            require(bool(measure["voices"]), "Supply at least one complete voice per measure")
            for voice, events in measure["voices"].items():
                total = F()
                for event in events:
                    require(set(event) <= {"pitches", "duration", "staff", "measure_rest", "tie", "pitch_ties", "grace", "tuplet", "lyrics", "clef", "stem", "beam", "accidentals", "measured_tremolo", "fermata"}, "Unsupported event fields; extend the encoder explicitly instead of dropping notation")
                    require(event.get('fermata') in (None, 'upright', 'inverted'), 'Unsupported fermata orientation')
                    duration = F(str(event["duration"]))
                    require(duration > 0 or (duration == 0 and event.get('grace')), "Nonpositive duration without a grace note")
                    if event.get('grace'):
                        require(isinstance(event['grace'], dict) and set(event['grace']) <= {'type', 'slash'}, 'Grace requires a type and optional slash')
                        require(duration == 0 and event.get('pitches') and not event.get('tie') and not event.get('pitch_ties') and not event.get('tuplet'), 'Grace notes must be untied pitched zero-duration events')
                        require(event['grace'].get('type', 'eighth') in TYPES, 'Unsupported grace type')
                    if event.get('pitch_ties'):
                        require(not event.get('tie') and set(event['pitch_ties']) <= set(event.get('pitches', [])), 'Per-pitch ties must name event pitches and not conflict with a whole-chord tie')
                        require(all(t in ('start', 'stop', 'continue') for t in event['pitch_ties'].values()), 'Invalid per-pitch tie')
                    if event.get('measured_tremolo'):
                        trem = event['measured_tremolo']
                        require(isinstance(trem, dict) and set(trem) == {'type', 'strokes'}, 'Measured tremolo requires type and strokes')
                        require(trem['type'] in ('start', 'stop') and trem['strokes'] in (1, 2, 3, 4, 5), 'Unsupported tremolo type or strokes')
                        require(event.get('pitches') and not any(event.get(k) for k in ('grace', 'tuplet', 'beam', 'lyrics')), 'Measured tremolos must be pitched, without grace, tuplet, beam, or lyrics')
                    require(1 <= event.get("staff", 1) <= staves, "Event refers to an absent staff")
                    require(not event.get("measure_rest") or (not event.get("pitches") and duration == length), "Whole-measure rest must fill its measure")
                    require(event.get("tie") in (None, "start", "stop", "continue"), "Invalid tie type")
                    require(not event.get("tie") or event.get("pitches"), "A rest cannot be tied")
                    require(not event.get("lyrics") or event.get("pitches"), "Lyrics must attach to pitched events")
                    if event.get("tuplet"):
                        require(isinstance(event['tuplet'], dict) and set(event['tuplet']) <= {'actual', 'normal', 'mark', 'normal_type', 'number'}, 'Unsupported tuplet fields')
                        require(event['tuplet'].get('mark') in (None, 'start', 'continue', 'stop'), 'Invalid tuplet mark')
                    for pitch in event.get("pitches", []):
                        pitch_components(pitch)
                    for lyric in event.get("lyrics", []):
                        require(set(lyric) <= {"number", "name", "language", "text", "syllabic", "extend"}, "Unsupported lyric fields")
                        require(lyric.get("syllabic", "single") in ("single", "begin", "middle", "end"), "Invalid syllabic value")
                        require(lyric.get("extend") in (None, "start", "continue", "stop"), "Invalid lyric extension")
                        require(bool(lyric.get("text")) or bool(lyric.get("extend")), "A lyric needs text or an extension")
                    duration_shape(event)
                    total += duration
                    denominators.append(duration.denominator)
                require(total == length, f"Part {part['id']} measure {measure['number']} voice {voice}: {total} quarters, expected {length}")
        signatures.append(signature)
    require(all(s == signatures[0] for s in signatures), "Parts must have aligned measure numbers and lengths; polymeter is not supported")
    return lcm(*denominators)


def put_clef(parent, staff, clef):
    require(clef[0] in ("G", "F", "C"), "Supported clefs are G, F, and C")
    require(1 <= int(clef[1]) <= 5, "Clef line must be 1..5")
    node = sub(parent, "clef", number=staff)
    sub(node, "sign", clef[0])
    sub(node, "line", clef[1])


def displayed_accidentals(measure, fifths):
    """Resolve the printed accidental state in musical time, across all voices."""
    timed = defaultdict(list)
    for voice, events in measure["voices"].items():
        offset = F()
        for index, event in enumerate(events):
            for pitch in event.get("pitches", []):
                timed[offset].append((voice, index, event, pitch))
            offset += F(str(event["duration"]))
    state, result = {}, {}
    names = {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}
    for offset, rows in sorted(timed.items()):
        simultaneous = defaultdict(set)
        for voice, index, event, pitch in rows:
            step, alter, octave = pitch_components(pitch)
            simultaneous[(event.get("staff", 1), step, octave)].add(alter)
        for voice, index, event, pitch in rows:
            step, alter, octave = pitch_components(pitch)
            key = event.get("staff", 1), step, octave
            explicit = event.get("accidentals", {}).get(pitch)
            ambiguous = len(simultaneous[key]) > 1
            tie = event.get('pitch_ties', {}).get(pitch, event.get('tie'))
            if explicit or ((alter != state.get(key, key_alter(fifths, step)) or ambiguous) and tie not in ("stop", "continue")):
                result[(voice, index, pitch)] = explicit or names[alter]
        for key, values in simultaneous.items():
            state[key] = next(iter(values)) if len(values) == 1 else None
    return result


def put_event(parent, event, voice, staves, divisions, accidentals, index):
    staff = event.get("staff", 1)
    if "clef" in event:
        put_clef(sub(parent, "attributes"), staff, event["clef"])
    duration = F(str(event["duration"]))
    note_type, dots = duration_shape(event)
    for ci, pitch in enumerate(event.get("pitches") or [None]):
        tie = event.get('pitch_ties', {}).get(pitch, event.get('tie'))
        ties = ['stop', 'start'] if tie == 'continue' else [tie] if tie else []
        note = sub(parent, "note")
        if event.get('grace'):
            sub(note, 'grace', slash='yes' if event['grace'].get('slash', True) else 'no')
        if ci:
            sub(note, "chord")
        if pitch is None:
            sub(note, "rest", **({"measure": "yes"} if event.get("measure_rest") else {}))
        else:
            step, alter, octave = pitch_components(pitch)
            pn = sub(note, "pitch")
            sub(pn, "step", step)
            if alter:
                sub(pn, "alter", alter)
            sub(pn, "octave", octave)
        if not event.get('grace'):
            sub(note, "duration", int(duration * divisions))
        for tie in ties:
            sub(note, "tie", type=tie)
        sub(note, "voice", voice)
        if not event.get("measure_rest"):
            sub(note, "type", note_type)
            for _ in range(dots):
                sub(note, "dot")
        if (voice, index, pitch) in accidentals:
            sub(note, "accidental", accidentals[(voice, index, pitch)])
        tuplet = event.get("tuplet")
        tremolo = event.get('measured_tremolo')
        if tuplet:
            node = sub(note, "time-modification")
            sub(node, "actual-notes", tuplet["actual"])
            sub(node, "normal-notes", tuplet["normal"])
            sub(node, "normal-type", tuplet.get("normal_type", note_type))
        elif tremolo:
            node = sub(note, 'time-modification')
            sub(node, 'actual-notes', 2)
            sub(node, 'normal-notes', 1)
        if pitch and note_type not in ("whole", "breve") and event.get("stem"):
            sub(note, "stem", event["stem"])
        if staves > 1:
            sub(note, "staff", staff)
        if event.get("beam") and ci == 0:
            levels = {"eighth": 1, "16th": 2, "32nd": 3, "64th": 4, "128th": 5}
            require(note_type in levels, "Only short notes can be beamed")
            for level in range(1, levels[note_type] + 1):
                sub(note, "beam", event["beam"], number=level)
        if ties or (tuplet and tuplet.get("mark") in ("start", "stop")) or (tremolo and ci == 0) or (event.get('fermata') and ci == 0):
            node = sub(note, "notations")
            for tie in ties:
                sub(node, "tied", type=tie)
            if tuplet and tuplet.get("mark") in ("start", "stop"):
                sub(node, "tuplet", type=tuplet["mark"], number=tuplet.get("number", 1), bracket="yes")
            if tremolo and ci == 0:
                sub(sub(node, 'ornaments'), 'tremolo', tremolo['strokes'], type=tremolo['type'])
            if event.get('fermata') and ci == 0:
                sub(node, 'fermata', 'normal', type=event['fermata'])
        if ci == 0:
            for lyric in event.get("lyrics", []):
                node = sub(note, "lyric", number=lyric.get("number", 1), **({"name": lyric["name"]} if "name" in lyric else {}))
                if lyric.get("text"):
                    sub(node, "syllabic", lyric.get("syllabic", "single"))
                    text = sub(node, "text", lyric["text"])
                    if lyric.get("language"):
                        text.set("{http://www.w3.org/XML/1998/namespace}lang", lyric["language"])
                if lyric.get("extend"):
                    sub(node, "extend", type=lyric["extend"])


def build(spec, output):
    divisions = checked_spec(spec)
    score = ET.Element("score-partwise", version="4.0")
    sub(sub(score, "work"), "work-title", spec["title"])
    identification = sub(score, "identification")
    if spec.get("composer"):
        sub(identification, "creator", spec["composer"], type="composer")
    enc = sub(identification, "encoding")
    sub(enc, "software", "Kengraver score-transcription")
    sub(enc, "encoding-description", " ".join(spec.get("boundary_notes", [])))
    if spec.get("source"):
        sub(identification, "source", spec["source"])
    listing = sub(score, "part-list")
    for pi, part in enumerate(spec["parts"]):
        node = sub(listing, "score-part", id=part["id"])
        sub(node, "part-name", part["name"])
        if part.get("abbreviation"):
            sub(node, "part-abbreviation", part["abbreviation"])
        instrument = sub(node, "score-instrument", id=part["id"] + "-I1")
        sub(instrument, "instrument-name", part["name"])
        if part.get("midi_program"):
            midi = sub(node, "midi-instrument", id=part["id"] + "-I1")
            sub(midi, "midi-channel", part.get("midi_channel", pi + 1))
            sub(midi, "midi-program", part["midi_program"])
    for part in spec["parts"]:
        node = sub(score, "part", id=part["id"])
        meter, fifths = part["meter"], part["key_fifths"]
        for mi, measure in enumerate(part["measures"]):
            meter = measure.get("meter", meter)
            fifths = measure.get("key_fifths", fifths)
            length = F(str(measure.get("length", meter_length(meter))))
            m = sub(node, "measure", number=measure["number"], **({"implicit": "yes"} if measure.get("implicit") else {}))
            if mi == 0 or any(k in measure for k in ("meter", "key_fifths", "clefs")):
                attrs = sub(m, "attributes")
                if mi == 0:
                    sub(attrs, "divisions", divisions)
                if mi == 0 or "key_fifths" in measure:
                    sub(sub(attrs, "key"), "fifths", fifths)
                if mi == 0 or "meter" in measure:
                    time = sub(attrs, "time")
                    beats, unit = meter.split("/")
                    sub(time, "beats", beats)
                    sub(time, "beat-type", unit)
                if mi == 0 and part["staves"] > 1:
                    sub(attrs, "staves", part["staves"])
                    sub(attrs, "part-symbol", "brace")
                clefs = dict(part["clefs"]) if mi == 0 else {}
                clefs.update(measure.get("clefs", {}))
                for staff, clef in clefs.items():
                    put_clef(attrs, staff, clef)
            accidentals = displayed_accidentals(measure, fifths)
            for vi, (voice, events) in enumerate(measure["voices"].items()):
                if vi:
                    sub(sub(m, "backup"), "duration", int(length * divisions))
                for index, event in enumerate(events):
                    put_event(m, event, voice, part["staves"], divisions, accidentals, index)
            if measure.get('right_barline'):
                sub(sub(m, 'barline', location='right'), 'bar-style', measure['right_barline'])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(score, space="  ")
    ET.ElementTree(score).write(output, encoding="utf-8", xml_declaration=True)
    return output


def read_xml(path):
    path = Path(path)
    if path.suffix == ".mxl":
        with zipfile.ZipFile(path) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            filename = next(n.attrib["full-path"] for n in container.iter() if n.tag.endswith("rootfile"))
            return ET.fromstring(archive.read(filename))
    return ET.parse(path).getroot()


def analyze(path, strict=True):
    root = read_xml(path)
    require(root.tag == "score-partwise", "Only score-partwise MusicXML is supported")
    require(not strict or not root.findall(".//transpose"), "Transposing instruments need a sounding-pitch comparison extension")
    require(not strict or not root.findall(".//octave-shift"), "Octave-shift directions need a context comparison extension")
    require(not strict or not root.findall(".//unpitched"), "Unpitched percussion is not yet validated")
    events, rests, measures, changes, tuplets, graces, tremolos = [], [], [], [], [], [], []
    barlines, fermatas = [], []
    midi_programs = [tuple(m.findtext('midi-program') for m in p.findall('midi-instrument')) for p in root.findall('./part-list/score-part')]
    for pi, part in enumerate(root.findall("part")):
        divisions, meter, staves, absolute = 1, None, 1, F()
        for mi, measure in enumerate(part.findall("measure")):
            cursor, chord_start, high_water = F(), F(), F()
            trem_marks, note_shapes, tuplet_candidates = [], {}, []
            for child in measure:
                if child.tag == "attributes":
                    divisions = int(child.findtext("divisions", str(divisions)))
                    staves = int(child.findtext("staves", str(staves)))
                    require(divisions > 0, "divisions must be positive")
                    for time in child.findall("time"):
                        meter = time.findtext("beats") + "/" + time.findtext("beat-type")
                        changes.append((pi, "meter", 0, str(absolute + cursor), meter))
                    for key in child.findall("key"):
                        for staff in [int(key.attrib["number"])] if "number" in key.attrib else range(1, staves + 1):
                            changes.append((pi, "key", staff, str(absolute + cursor), key.findtext("fifths", "0")))
                    for clef in child.findall("clef"):
                        changes.append((pi, "clef", int(clef.attrib.get("number", "1")), str(absolute + cursor), (clef.findtext("sign"), clef.findtext("line"), clef.findtext("clef-octave-change", "0"))))
                elif child.tag in ("backup", "forward"):
                    duration = F(child.findtext("duration")) / divisions
                    require(duration > 0, "backup/forward durations must be positive")
                    cursor += duration * (-1 if child.tag == "backup" else 1)
                    if strict:
                        require(cursor >= 0, f"{path}: backup before measure start")
                    high_water = max(high_water, cursor)
                elif child.tag == "note":
                    duration = F(child.findtext("duration", "0")) / divisions
                    if child.find("chord") is None:
                        chord_start = cursor
                        cursor += duration
                    high_water = max(high_water, cursor)
                    staff = int(child.findtext("staff", "1"))
                    voice = child.findtext("voice", "1")
                    for fermata in child.findall('./notations/fermata'):
                        fermatas.append((pi, mi, staff, str(chord_start), fermata.get('type', 'upright'), (fermata.text or 'normal').strip() or 'normal'))
                    trem = child.find('./notations/ornaments/tremolo')
                    if trem is not None:
                        require(trem.get('type') in ('start', 'stop') and trem.text in ('1', '2', '3', '4', '5'), 'Only measured two-note tremolos are supported')
                        trem_marks.append((voice, chord_start, duration, trem.get('type'), int(trem.text)))
                    if strict:
                        require(duration > 0 or (duration == 0 and child.find('grace') is not None), "Nonpositive note duration without grace")
                        require(1 <= staff <= staves, "Note on nonexistent staff")
                    pitch = child.find("pitch")
                    if pitch is None:
                        # MuseScore adds invisible whole-bar padding voices beneath
                        # cross-staff streams. Keep their timing, not their ink.
                        if child.attrib.get('print-object') != 'no':
                            rests.append((pi, mi, staff, str(chord_start), str(duration), voice))
                    else:
                        spelled = (pitch.findtext("step"), int(pitch.findtext("alter", "0")), int(pitch.findtext("octave")))
                        lyrics = tuple((ly.attrib.get("number", "1"), ly.findtext("syllabic", "single"), "".join(t.text or "" for t in ly.findall("text")), ly.find("extend").attrib.get("type", "start") if ly.find("extend") is not None else "") for ly in child.findall("lyric"))
                        ties = tuple(sorted(t.attrib["type"] for t in child.findall("tie")))
                        if child.find('grace') is not None:
                            graces.append((pi, mi, staff, str(chord_start), spelled, child.findtext('type'), child.find('grace').get('slash', 'no'), child.find('chord') is not None))
                        else:
                            events.append((pi, mi, staff, str(chord_start), spelled, str(duration), ties, lyrics, voice))
                    tm = child.find("time-modification")
                    if child.find('grace') is None:
                        note_shapes.setdefault((voice, chord_start), []).append((duration, child.findtext('type'), len(child.findall('dot')), tm.findtext('actual-notes') if tm is not None else None, tm.findtext('normal-notes') if tm is not None else None))
                    if tm is not None:
                        tuplet_candidates.append((voice, (pi, mi, staff, str(chord_start), str(duration), tm.findtext("actual-notes"), tm.findtext("normal-notes"), child.findtext("type"))))
                elif child.tag == 'barline':
                    style = child.findtext('bar-style', 'regular')
                    if style != 'regular':
                        barlines.append((pi, mi, child.get('location', 'right'), style))
            pending_trem, trem_positions = {}, set()
            for voice, onset, duration, mark, strokes in trem_marks:
                if mark == 'start':
                    require(voice not in pending_trem, 'Overlapping tremolo starts')
                    pending_trem[voice] = (onset, duration, strokes)
                    continue
                require(voice in pending_trem, 'Tremolo stop without start')
                start, half_span, start_strokes = pending_trem.pop(voice)
                require(onset == start + half_span and duration == half_span and strokes == start_strokes, 'Tremolo pair timing or strokes disagree')
                pair = []
                for position in (start, onset):
                    for actual, kind, dots, numerator, denominator in note_shapes[voice, position]:
                        require(kind in TYPES and actual * 2 == TYPES[kind] * sum((F(1, 2 ** n) for n in range(dots + 1)), F()) and (numerator, denominator) == ('2', '1'), 'Tremolo needs half its written duration and a 2:1 time modification')
                    indices = [i for i, e in enumerate(events) if e[0:2] == (pi, mi) and e[-1] == voice and F(e[3]) == position]
                    require(indices, 'Tremolo endpoint has no pitched notes')
                    pair.append(tuple(sorted((events[i][2], events[i][4]) for i in indices)))
                    for i in indices:
                        e = events[i]
                        events[i] = (*e[:3], str(start), e[4], str(2 * half_span), *e[6:])
                    trem_positions.add((voice, str(position)))
                tremolos.append((pi, mi, str(start), str(2 * half_span), strokes, *pair))
            require(not pending_trem, 'Unclosed tremolo; cross-measure pairs are unsupported')
            # The 2:1 time modification describes the tremolo, not a tuplet.
            tuplets.extend(t for v, t in tuplet_candidates if (v, t[3]) not in trem_positions)
            if strict:
                require(meter is not None, f"{path}: no initial meter; recover inherited context first")
                expected = high_water if measure.attrib.get("implicit") == "yes" else meter_length(meter)
                require(high_water == expected and cursor == expected, f"{path}: part {pi + 1}, measure {measure.attrib.get('number')}: duration {high_water}, final cursor {cursor}, expected {expected}")
            else:
                expected = high_water
            measures.append((pi, mi, str(expected), meter))
            absolute += expected
    context = []
    previous = {}
    for row in sorted(changes, key=lambda x: (x[0], x[1], x[2], F(x[3]))):
        key = row[:3]
        if previous.get(key) != row[4]:
            context.append(row)
            previous[key] = row[4]
    if strict:
        lengths = defaultdict(list)
        for pi, mi, length, meter in measures:
            lengths[pi].append(length)
        require(all(v == next(iter(lengths.values())) for v in lengths.values()), "Parts have different measure counts or lengths")
    return dict(events=events, rests=rests, measures=measures, context=context, tuplets=tuplets, graces=graces, tremolos=tremolos, barlines=barlines, fermatas=fermatas, midi_programs=midi_programs)


def schema_check(path):
    from lxml import etree
    directory = PACKAGE / "assets/musicxml-schema"
    class LocalSchemas(etree.Resolver):
        def resolve(self, url, public_id, context):
            candidate = directory / url.rsplit("/", 1)[-1]
            if candidate.exists():
                return self.resolve_filename(str(candidate), context)
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(LocalSchemas())
    schema = etree.XMLSchema(etree.parse(str(directory / "musicxml.xsd"), parser))
    schema.assertValid(etree.fromstring(ET.tostring(read_xml(path)), parser))


def check_ties(data):
    starts, lengths = {}, {}
    for pi, mi, length, meter in data["measures"]:
        starts[pi, mi] = sum((F(l) for (p, m), l in lengths.items() if p == pi and m < mi), F())
        lengths[pi, mi] = length
    pending = {}
    for e in sorted(data["events"], key=lambda e: (e[0], e[1], F(e[3]))):
        pi, mi, staff, offset, pitch, duration, ties, lyrics, voice = e
        key = pi, voice, pitch
        position = starts[pi, mi] + F(offset)
        if "stop" in ties:
            require(pending.pop(key, None) == position, f"Broken tie at part {pi + 1}, measure index {mi}, {pitch}")
        if "start" in ties:
            require(key not in pending, f"Overlapping tie {key}")
            pending[key] = position + F(duration)
    require(not pending, f"Unclosed ties: {pending}; record excerpt boundaries explicitly")


def voice_groups(data):
    groups = defaultdict(list)
    for e in data["events"]:
        groups[e[0], e[-1]].append(e[:-1])
    return Counter(tuple(sorted(events)) for events in groups.values())


def compare(before, after):
    a, b = analyze(before), analyze(after)
    expected, actual = Counter(e[:-1] for e in a["events"]), Counter(e[:-1] for e in b["events"])
    missing, extra = list((expected - actual).elements()), list((actual - expected).elements())
    result = dict(notes_and_lyrics="pass" if not missing and not extra else "FAIL",
                  voice_continuity="pass" if voice_groups(a) == voice_groups(b) else "FAIL",
                  context="pass" if a["context"] == b["context"] else "FAIL",
                  measure_lengths="pass" if a["measures"] == b["measures"] else "FAIL",
                  tuplet_ratios="pass" if Counter(a["tuplets"]) == Counter(b["tuplets"]) else "FAIL",
                  rest_coverage="pass" if rest_coverage(a) == rest_coverage(b) else "FAIL",
                  grace_sequence='pass' if a['graces'] == b['graces'] else 'FAIL',
                  measured_tremolos='pass' if Counter(a['tremolos']) == Counter(b['tremolos']) else 'FAIL',
                  barlines='pass' if Counter(a['barlines']) == Counter(b['barlines']) else 'FAIL',
                  fermatas='pass' if Counter(a['fermatas']) == Counter(b['fermatas']) else 'FAIL',
                  midi_programs='pass' if a['midi_programs'] == b['midi_programs'] else 'FAIL',
                  missing=missing, extra=extra)
    result["status"] = "pass" if all(result[k] == "pass" for k in ("notes_and_lyrics", "voice_continuity", "context", "measure_lengths", "tuplet_ratios", "rest_coverage", "grace_sequence", "measured_tremolos", "barlines", "fermatas", "midi_programs")) else "FAIL"
    return result


def rest_coverage(data):
    """Normalize rest subdivisions, preserving staff and time, not engraving choices."""
    groups = defaultdict(list)
    for pi, mi, staff, onset, duration, voice in data['rests']:
        groups[pi, mi, staff].append((F(onset), F(onset) + F(duration)))
    result = {}
    for key, intervals in groups.items():
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        result[key] = tuple(merged)
    return result


def validate(path, roundtrip=None):
    schema_check(path)
    data = analyze(path)
    check_ties(data)
    report = dict(file=str(path), schema="pass", timing="pass", internal_ties="pass",
                  pitched_notes=len(data["events"]), lyric_syllables=sum(bool(l[2]) for e in data["events"] for l in e[7]),
                  grace_pitches=len(data['graces']),
                  parts=len({m[0] for m in data["measures"]}), status="pass",
                  visual_review="not established by this command")
    if roundtrip:
        schema_check(roundtrip)
        check_ties(analyze(roundtrip))
        report["roundtrip"] = compare(path, roundtrip)
        report["status"] = report["roundtrip"]["status"]
    return report


def tools_root(explicit=None):
    if explicit or os.environ.get("KENGRAVER_TOOLS"):
        return Path(explicit or os.environ["KENGRAVER_TOOLS"]).resolve()
    for ancestor in PACKAGE.parents:
        if (ancestor / ".tools/musescore/squashfs-root/AppRun").exists():
            return ancestor / ".tools"
    return Path.cwd() / ".tools"


def environment(state):
    env = os.environ.copy()
    state = Path(state).resolve()
    for var, name in [("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"), ("XDG_RUNTIME_DIR", "runtime")]:
        folder = state / name
        folder.mkdir(parents=True, exist_ok=True)
        env[var] = str(folder)
    (state / "runtime").chmod(0o700)
    return env


def render(path, output, tools=None, mxl=False):
    import pymupdf
    path, output = Path(path).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = tools_root(tools) / "musescore/squashfs-root/AppRun"
    require(app.exists(), "MuseScore missing; run bootstrap.py or specify --tools")
    env = environment(output / ".tool-state")
    env.update(QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="generic", QT_STYLE_OVERRIDE="Fusion", XDG_CURRENT_DESKTOP="NONE", DESKTOP_SESSION="NONE")
    log = []
    for extension in ("pdf", "mscz", "musicxml") + (("mxl",) if mxl else ()):
        destination = output / (path.stem + "." + extension)
        require(destination != path, "Render output must not overwrite source MusicXML")
        # Verified workaround for MuseScore 4.7.4's Qt environment and CLI parsing.
        command = [str(app), str(path), "-platform", "offscreen", "-platformtheme", "generic", "-o", str(destination)]
        run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        log.append(f"{extension}: exit {run.returncode}\n{run.stdout}{run.stderr}")
        require(run.returncode == 0 and destination.exists(), log[-1])
    (output / (path.stem + ".log")).write_text("\n".join(log))
    with pymupdf.open(output / (path.stem + ".pdf")) as doc:
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=180).save(output / f"{path.stem}-{i + 1}.png")
    return output / (path.stem + ".musicxml")


def crop(pdf, page, box, output, dpi=300):
    import pymupdf
    with pymupdf.open(pdf) as doc:
        require(1 <= page <= len(doc), "PDF page out of range (pages are one-based)")
        rect = pymupdf.Rect(box) if box else doc[page - 1].rect
        require(not rect.is_empty and doc[page - 1].rect.contains(rect), "Crop must lie within the page; coordinates are PDF points")
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        doc[page - 1].get_pixmap(dpi=dpi, clip=rect).save(output)
    dump(output.with_suffix(".source.json"), dict(pdf=str(Path(pdf).resolve()), page=page, box_points=list(rect), dpi=dpi))


def omr(pdf, output, languages, tools=None):
    directory = tools_root(tools)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    state = directory / "state"
    env = environment(state)
    for language in languages.split("+"):
        require((state / "config/AudiverisLtd/audiveris/tessdata" / (language + ".traineddata")).exists(), f"Missing OCR language pack: {language}")
    env["JAVA_TOOL_OPTIONS"] = f"-Djava.awt.headless=true -Djava.util.prefs.userRoot={state}/java-prefs -Duser.home={state}"
    command = [str(directory / "audiveris/opt/audiveris/bin/Audiveris"), "-batch", "-export", "-constant", "org.audiveris.omr.text.Language.defaultSpecification=" + languages, "-output", str(output), "--", str(Path(pdf).resolve())]
    with (output / "console.log").open("w") as log:
        run = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    require(run.returncode == 0, "Audiveris failed; inspect console.log")
    text = (output / "console.log").read_text()
    require(not any(s in text for s in ("couldn't load any languages", "Could not initialize TessBaseAPI", "No installed OCR languages")), "OCR language initialization failed despite process exit 0; inspect console.log")
    return sorted(str(p) for p in output.glob("*.mxl"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    p = commands.add_parser("build"); p.add_argument("spec", type=Path); p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("validate"); p.add_argument("score", type=Path); p.add_argument("--roundtrip", type=Path); p.add_argument("--report", type=Path)
    p = commands.add_parser("compare"); p.add_argument("before", type=Path); p.add_argument("after", type=Path); p.add_argument("--report", type=Path)
    p = commands.add_parser("render"); p.add_argument("score", type=Path); p.add_argument("--out", type=Path, required=True); p.add_argument("--tools", type=Path); p.add_argument("--mxl", action="store_true", help="also export compressed MusicXML (.mxl)")
    p = commands.add_parser("crop"); p.add_argument("pdf", type=Path); p.add_argument("--page", type=int, required=True); p.add_argument("--box", nargs=4, type=float); p.add_argument("--dpi", type=int, default=300); p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("omr"); p.add_argument("pdf", type=Path); p.add_argument("--out", type=Path, required=True); p.add_argument("--languages", required=True); p.add_argument("--tools", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        result = {"built": str(build(json.loads(args.spec.read_text()), args.out))}
    elif args.action == "validate":
        result = validate(args.score, args.roundtrip)
    elif args.action == "compare":
        result = compare(args.before, args.after)
    elif args.action == "render":
        result = {"roundtrip": str(render(args.score, args.out, args.tools, args.mxl))}
        if args.mxl:
            result["mxl"] = str(Path(result["roundtrip"]).with_suffix(".mxl"))
    elif args.action == "crop":
        crop(args.pdf, args.page, args.box, args.out, args.dpi)
        result = {"crop": str(args.out)}
    else:
        result = {"raw_omr": omr(args.pdf, args.out, args.languages, args.tools)}
    if getattr(args, "report", None):
        dump(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
