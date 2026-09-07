"""Portable gloss behavior; no Apollo material or notation application required."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gloss', ROOT/'skills/score-lyric-gloss/scripts/gloss.py')
gloss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gloss)

SOURCE = '''<score-partwise><part id="Singer">
<measure number="1"><attributes><divisions>4</divisions></attributes>
<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><lyric><syllabic>begin</syllabic><text>hal</text></lyric></note>
<note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice></note></measure>
<measure number="2"><note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><lyric><syllabic>end</syllabic><text>lo</text></lyric></note>
<note><pitch><step>F</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><lyric><text>du</text></lyric></note></measure>
</part></score-partwise>'''


class GlossTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory/'source.musicxml'
        self.source.write_text(SOURCE)
        self.output = self.directory/'learning.musicxml'
        self.mapping = dict(part='Singer', appearance=dict(color='#245B85', font_style='normal'),
                            units=[dict(source='hallo', text='hello'), dict(source='du', text='you')])

    def test_cross_bar_word_and_unlyricized_note(self):
        rows = gloss.words(E.fromstring(SOURCE), 'Singer')
        self.assertEqual([(r['source'], r['measure'], r['onset']) for r in rows], [('hallo','1','0'), ('du','2','1')])

    def test_public_example_is_runnable_and_preserves_original(self):
        example = ROOT/'skills/score-lyric-gloss/examples/hello.musicxml'
        mapping = json.loads((example.parent/'hello-gloss.json').read_text())
        before = example.read_bytes()
        result = gloss.annotate(example, mapping, self.output)
        self.assertEqual(result['gloss_units'], 2)
        self.assertEqual(example.read_bytes(), before)
        self.assertEqual(gloss.text_inventory(self.output), [
            ('P1', '1', '0', '1', 'hello', '#0066CC', 'normal'),
            ('P1', '2', '1', '1', 'you', '#0066CC', 'normal')])
        original, annotated = E.parse(example).getroot(), E.parse(self.output).getroot()
        for m in annotated.findall('.//measure'):
            for d in m.findall('direction'): m.remove(d)
        E.indent(original); E.indent(annotated)
        self.assertEqual(E.tostring(original), E.tostring(annotated))

    def test_grouping_and_input_preservation(self):
        self.mapping['units'] = [dict(source='hallo du', text='hello you')]
        report = gloss.annotate(self.source, self.mapping, self.output)
        self.assertEqual(report['words'], 2)
        self.assertEqual(report['gloss_units'], 1)
        self.assertEqual(self.source.read_text(), SOURCE)
        before = E.fromstring(SOURCE)
        after = E.parse(self.output).getroot()
        for m in after.findall('.//measure'):
            for d in m.findall('direction'): m.remove(d)
        E.indent(before); E.indent(after)
        self.assertEqual(E.tostring(before), E.tostring(after))

    def test_invalid_coverage_and_inplace_refused(self):
        for units in ([], [dict(source='du', text='you')], [dict(source='', text='bad')],
                      [dict(source='hallo', text='')], self.mapping['units']+[dict(source='extra', text='extra')]):
            with self.subTest(units=units), self.assertRaises(ValueError):
                gloss.annotate(self.source, dict(self.mapping, units=units), self.output)
        with self.assertRaises(ValueError): gloss.annotate(self.source, self.mapping, self.source)
        with self.assertRaises(ValueError): gloss.annotate(self.source, dict(self.mapping, verse='2'), self.output)

    def test_wrong_voice_and_broken_word_refused(self):
        r = E.fromstring(SOURCE)
        r.findall('.//voice')[-1].text = '2'
        with self.assertRaises(ValueError): gloss.words(r, 'Singer')
        r = E.fromstring(SOURCE)
        r.find('.//syllabic').text = 'single'
        with self.assertRaises(ValueError): gloss.words(r, 'Singer')

    def test_check_color_style_text_anchor_and_duplicates(self):
        gloss.annotate(self.source, self.mapping, self.output)
        self.assertEqual(gloss.check(self.output, self.output)['status'], 'pass')
        for mutation in ('color', 'font-style', 'text', 'offset', 'duplicate'):
            r = E.parse(self.output).getroot()
            d = r.find('.//direction'); w = d.find('direction-type/words')
            if mutation=='text': w.text='wrong'
            elif mutation=='offset': E.SubElement(d, 'offset').text='1'
            elif mutation=='duplicate': r.find('.//measure').insert(0, copy.deepcopy(d))
            else: w.set(mutation, '#000000' if mutation=='color' else 'italic')
            changed = self.directory/'changed.musicxml'
            E.ElementTree(r).write(changed)
            with self.subTest(mutation=mutation): self.assertEqual(gloss.check(self.output, changed)['status'], 'FAIL')
        with self.assertRaises(ValueError): gloss.check(self.source, self.source)

    def test_uncolored_gloss_and_dropped_import_ids(self):
        self.mapping['appearance'] = dict(placement='above')
        gloss.annotate(self.source, self.mapping, self.output)
        r = E.parse(self.output).getroot()
        for w in r.findall('.//words'): del w.attrib['id']
        changed = self.directory/'imported.musicxml'
        E.ElementTree(r).write(changed)
        self.assertEqual(gloss.check(self.output, changed)['checked_glosses'], 2)
        self.assertEqual(gloss.check(self.output, changed)['status'], 'pass')
        self.assertEqual(r.find('.//words').get('default-y'), '30')


if __name__ == '__main__': unittest.main()
