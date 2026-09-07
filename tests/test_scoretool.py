"""Behavioral tests independent of Luonnotar's key, meter, and instrumentation."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/score-transcription/scripts'))
import scoretool as tool


def event(pitch='C4', duration='1', **extra):
    return dict(pitches=[pitch] if pitch else [], duration=duration, **extra)


def spec(events=None, meter='3/4', key=-1):
    return dict(format_version=1, title='Independent test', parts=[
        dict(id='Solo', name='Solo', staves=1, clefs={'1': ['G', 2]}, key_fifths=key,
             meter=meter, measures=[dict(number='1', voices={'1': events or [event('F4'), event('G4'), event('A4')]})])])


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, data, name='score'):
        path = tool.build(data, self.directory / (name + '.musicxml'))
        self.assertEqual(tool.validate(path)['status'], 'pass')
        return path

    def test_nonpilot_key_meter_and_accidentals(self):
        path = self.build(spec([event('Bb4'), event('B4'), event('Bb4')]))
        root = tool.read_xml(path)
        self.assertEqual(root.findtext('.//fifths'), '-1')
        self.assertEqual([n.findtext('accidental') for n in root.findall('.//note')], [None, 'natural', 'flat'])
        self.assertEqual(tool.analyze(path)['measures'][0][2:], ('3', '3/4'))

    def test_changes_pickup_and_three_parts(self):
        data = spec()
        measures = data['parts'][0]['measures']
        measures[0].update(number='0', implicit=True, length='1', voices={'1': [event()]})
        measures.append(dict(number='1', meter='3+2/8', key_fifths=2, clefs={'1': ['C', 3]},
                             voices={'1': [event('D4', '3/2'), event('E4')]}))
        measures.append(dict(number='2', voices={'1': [event(None, '5/2', measure_rest=True)]}))
        for name in ['Viola', 'Cello']:
            part = copy.deepcopy(data['parts'][0])
            part.update(id=name, name=name)
            data['parts'].append(part)
        path = self.build(data)
        self.assertEqual(tool.validate(path)['parts'], 3)
        self.assertEqual([m[2] for m in tool.analyze(path)['measures'][:3]], ['1', '5/2', '5/2'])
        self.assertIn((0, 'clef', 1, '1', ('C', '3', '0')), tool.analyze(path)['context'])

    def test_quintuplet_exact_timing(self):
        events = [event(p, '1/5', tuplet=dict(actual=5, normal=4, mark=mark))
                  for p, mark in zip(['C4', 'D4', 'E4', 'F4', 'G4'], ['start', 'continue', 'continue', 'continue', 'stop'])]
        path = self.build(spec(events, meter='1/4'))
        notes = tool.analyze(path)['events']
        self.assertEqual([e[3] for e in notes], ['0', '1/5', '2/5', '3/5', '4/5'])
        self.assertTrue(all(n.findtext('type') == '16th' for n in tool.read_xml(path).findall('.//note')))

    def test_lyric_underlay_and_extender(self):
        data = spec([event('C4', lyrics=[dict(text='Ah', extend='start', language='en')]),
                     event('D4'), event('E4', lyrics=[dict(extend='stop')])])
        path = self.build(data)
        self.assertEqual(tool.validate(path)['lyric_syllables'], 1)
        self.assertEqual([bool(n.find('lyric') is not None) for n in tool.read_xml(path).findall('.//note')], [True, False, True])

    def test_crossstaff_tie_and_independent_voice(self):
        data = spec(meter='2/4')
        part = data['parts'][0]
        part.update(staves=2, clefs={'1': ['G', 2], '2': ['F', 4]})
        part['measures'] = [dict(number='1', voices={
            '7': [event('C4', tie='start', staff=1), event('C4', tie='stop', staff=2)],
            '9': [event('E4', '2', staff=1)]})]
        path = self.build(data)
        self.assertEqual(len(tool.voice_groups(tool.analyze(path))), 2)

    def test_reject_bad_bar_lengths(self):
        for duration in ['2', '4']:
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'expected 3'):
                tool.build(spec([event('C4', duration)]), self.directory / 'bad.musicxml')

    def test_reject_unknown_semantics(self):
        for extra in [dict(tremolo=3), dict(partial_ties=['C4'])]:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Unsupported event'):
                tool.build(spec([event('C4', '3', **extra)]), self.directory / 'bad.musicxml')

    def test_unclosed_tie_fails(self):
        path = tool.build(spec([event('C4', '3', tie='start')]), self.directory / 'bad.musicxml')
        with self.assertRaisesRegex(ValueError, 'Unclosed ties'):
            tool.validate(path)

    def changed_xml(self, path, mutate):
        root = tool.read_xml(path)
        mutate(root)
        target = self.directory / 'changed.musicxml'
        ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)
        return target

    def test_wrong_pitch_detected_even_when_structure_valid(self):
        path = self.build(spec())
        other = self.changed_xml(path, lambda r: setattr(r.find('.//pitch/step'), 'text', 'E'))
        self.assertEqual(tool.validate(other)['status'], 'pass')
        self.assertEqual(tool.compare(path, other)['notes_and_lyrics'], 'FAIL')

    def test_wrong_lyric_and_clef_detected(self):
        path = self.build(spec([event('C4', '3', lyrics=[dict(text='Hei')])]))
        other = self.changed_xml(path, lambda r: setattr(r.find('.//lyric/text'), 'text', 'Hel'))
        self.assertEqual(tool.compare(path, other)['notes_and_lyrics'], 'FAIL')
        other = self.changed_xml(path, lambda r: setattr(r.find('.//clef/sign'), 'text', 'F'))
        self.assertEqual(tool.compare(path, other)['context'], 'FAIL')

    def test_arbitrary_voice_ids_do_not_fail(self):
        path = self.build(spec())
        other = self.changed_xml(path, lambda r: [setattr(v, 'text', '42') for v in r.findall('.//voice')])
        self.assertEqual(tool.compare(path, other)['status'], 'pass')

    def test_split_voice_detected(self):
        path = self.build(spec())
        other = self.changed_xml(path, lambda r: setattr(r.findall('.//voice')[1], 'text', '2'))
        self.assertEqual(tool.compare(path, other)['notes_and_lyrics'], 'pass')
        self.assertEqual(tool.compare(path, other)['voice_continuity'], 'FAIL')

    def test_wrong_duration_rejected(self):
        path = self.build(spec())
        other = self.changed_xml(path, lambda r: setattr(r.find('.//note/duration'), 'text', '2'))
        with self.assertRaisesRegex(ValueError, 'expected 3'):
            tool.analyze(other)

    def test_preserved_pilot_references(self):
        # These snapshots predate this encoder; never regenerate them with candidates.
        for source in sorted((ROOT / 'scores/luonnotar/pilot').glob('*.json')):
            with self.subTest(source=source.name):
                path = self.build(json.loads(source.read_text()), source.stem)
                reference = ROOT / 'tests/fixtures/luonnotar' / path.name
                self.assertEqual(tool.compare(reference, path)['status'], 'pass')

    def test_silent_staff_rest_cannot_disappear(self):
        path = self.build(spec([event(None, '3', measure_rest=True)]))
        def replace_rest(root):
            measure = root.find('.//part/measure')
            note = measure.find('note')
            forward = ET.Element('forward')
            ET.SubElement(forward, 'duration').text = note.findtext('duration')
            measure.remove(note)
            measure.append(forward)
        other = self.changed_xml(path, replace_rest)
        self.assertEqual(tool.compare(path, other)['rest_coverage'], 'FAIL')

    def test_first_measure_clef_override_is_not_dropped(self):
        data = spec()
        data['parts'][0]['measures'][0]['clefs'] = {'1': ['C', 3]}
        path = self.build(data)
        self.assertEqual(tool.read_xml(path).findtext('.//clef/sign'), 'C')

    def test_importer_invisible_padding_is_not_a_new_rest(self):
        path = self.build(spec())
        def add_padding(root):
            measure = root.find('.//part/measure')
            ET.SubElement(ET.SubElement(measure, 'backup'), 'duration').text = '3'
            note = ET.SubElement(measure, 'note', {'print-object': 'no'})
            ET.SubElement(note, 'rest', {'measure': 'yes'})
            ET.SubElement(note, 'duration').text = '3'
            ET.SubElement(note, 'voice').text = '5'
        other = self.changed_xml(path, add_padding)
        self.assertEqual(tool.compare(path, other)['status'], 'pass')

    def test_grace_notes_keep_order_without_consuming_beats(self):
        path = self.build(spec([event('B3', '0', grace=dict(type='eighth', slash=True)), event('C4', '3')]))
        self.assertEqual(tool.validate(path)['grace_pitches'], 1)
        self.assertEqual(tool.analyze(path)['events'][0][3], '0')
        self.assertEqual(tool.analyze(path)['graces'][0][4], ('B', 0, 3))

    def test_partial_chord_ties(self):
        data = spec([dict(pitches=['C4', 'E4'], duration='1', pitch_ties={'C4': 'start'}),
                     dict(pitches=['C4', 'F4'], duration='2', pitch_ties={'C4': 'stop'})])
        path = self.build(data)
        self.assertEqual(sum(bool(e[6]) for e in tool.analyze(path)['events']), 2)

    def test_grace_slash_distinction_and_wrong_slash_detected(self):
        for slash in (True, False):
            with self.subTest(slash=slash):
                path = self.build(spec([event('B3', '0', grace=dict(type='eighth', slash=slash)), event('C4', '3')]))
                self.assertEqual(tool.read_xml(path).find('.//grace').get('slash'), 'yes' if slash else 'no')
                other = self.changed_xml(path, lambda r: r.find('.//grace').set('slash', 'no' if slash else 'yes'))
                result = tool.compare(path, other)
                self.assertEqual(result['notes_and_lyrics'], 'pass')
                self.assertEqual(result['grace_sequence'], 'FAIL')
                self.assertEqual(result['status'], 'FAIL')

    def test_double_and_final_barlines_and_missing_barline_detected(self):
        for style in ('light-light', 'light-heavy'):
            with self.subTest(style=style):
                data = spec()
                data['parts'][0]['measures'][0]['right_barline'] = style
                path = self.build(data)
                self.assertEqual(tool.read_xml(path).findtext('.//bar-style'), style)
                other = self.changed_xml(path, lambda r: r.find('.//part/measure').remove(r.find('.//barline')))
                self.assertEqual(tool.compare(path, other)['barlines'], 'FAIL')

    def test_fermata_on_rest_and_chord_and_missing_fermata_detected(self):
        for pitches in ([], ['C4', 'E4', 'G4']):
            with self.subTest(pitches=pitches):
                note = dict(pitches=pitches, duration='3', fermata='upright')
                if not pitches:
                    note['measure_rest'] = True
                path = self.build(spec([note]))
                self.assertEqual(len(tool.read_xml(path).findall('.//fermata')), 1)
                other = self.changed_xml(path, lambda r: r.find('.//notations').remove(r.find('.//fermata')))
                self.assertEqual(tool.compare(path, other)['fermatas'], 'FAIL')

    def test_instrument_program_change_detected(self):
        data = spec()
        data['parts'][0].update(name='Oboe', midi_program=69)
        path = self.build(data)
        other = self.changed_xml(path, lambda r: setattr(r.find('.//midi-program'), 'text', '54'))
        self.assertEqual(tool.compare(path, other)['midi_programs'], 'FAIL')

    def test_measured_tremolo_both_endpoints_tie_into_chord(self):
        data = spec([event('C4', measured_tremolo=dict(type='start', strokes=2), tie='start'),
                     event('G4', measured_tremolo=dict(type='stop', strokes=2), tie='start'),
                     dict(pitches=['C4', 'G4'], duration='1', tie='stop')])
        path = self.build(data)
        analyzed = tool.analyze(path)
        self.assertEqual([e[3] for e in analyzed['events']], ['0', '0', '2', '2'])
        self.assertEqual([e[5] for e in analyzed['events']], ['2', '2', '1', '1'])
        self.assertEqual(len(analyzed['tremolos']), 1)
        self.assertFalse(analyzed['tuplets'])
        other = self.changed_xml(path, lambda r: [setattr(t, 'text', '3') for t in r.findall('.//tremolo')])
        self.assertEqual(tool.compare(path, other)['measured_tremolos'], 'FAIL')

    def test_reject_broken_tremolo_pair(self):
        data = spec([event('C4', measured_tremolo=dict(type='start', strokes=2)), event('G4', '2')])
        path = tool.build(data, self.directory / 'broken.musicxml')
        with self.assertRaisesRegex(ValueError, 'Unclosed tremolo'):
            tool.validate(path)

    def test_grace_before_measured_tremolo(self):
        data = spec([event('B3', '0', grace=dict(type='eighth', slash=False)),
                     event('C4', measured_tremolo=dict(type='start', strokes=2)),
                     event('G4', measured_tremolo=dict(type='stop', strokes=2)), event('E4')])
        path = self.build(data)
        self.assertEqual(tool.validate(path)['grace_pitches'], 1)
        self.assertEqual(len(tool.analyze(path)['tremolos']), 1)

    def test_tremolo_chord_endpoints_and_mismatched_duration(self):
        data = spec([dict(pitches=['C4','E4'], duration='1', measured_tremolo=dict(type='start', strokes=3)),
                     event('G4', measured_tremolo=dict(type='stop', strokes=3)), event('A4')])
        path = self.build(data)
        self.assertEqual(len(tool.analyze(path)['tremolos'][0][-2]), 2)
        def damage(root):
            notes = root.findall('.//note')
            notes[2].find('duration').text = '2'
            notes[3].find('duration').text = '0'
        other = self.changed_xml(path, damage)
        with self.assertRaises(ValueError):
            tool.analyze(other)


if __name__ == '__main__':
    unittest.main()
