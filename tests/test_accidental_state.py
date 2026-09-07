"""Synthetic state regressions; not a visual recognition accuracy benchmark."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/score-transcription/scripts'))
from scoretool import displayed_accidentals


def note(pitch, duration='1', staff=1):
    return dict(pitches=[pitch], duration=duration, staff=staff)


class AccidentalStateTests(unittest.TestCase):
    def test_carry_across_voices_in_onset_order_not_dictionary_order(self):
        measure = {'voices': {
            'later': [dict(pitches=[], duration='1'), note('B#5')],
            'earlier': [note('B#5', '2')]}}
        self.assertEqual(displayed_accidentals(measure, 4), {('earlier', 0, 'B#5'): 'sharp'})

    def test_explicit_natural_cancels_previous_sharp(self):
        measure = {'voices': {'1': [note('B#5'), note('B5'), note('B5')]}}
        self.assertEqual(displayed_accidentals(measure, 4),
                         {('1', 0, 'B#5'): 'sharp', ('1', 1, 'B5'): 'natural'})

    def test_state_is_staff_and_octave_specific(self):
        measure = {'voices': {'1': [note('B#5'), note('B5', staff=2), note('B4')]}}
        self.assertEqual(displayed_accidentals(measure, 4), {('1', 0, 'B#5'): 'sharp'})

    def test_new_measure_returns_to_key_signature(self):
        altered = {'voices': {'1': [note('G3')]}}
        following = {'voices': {'1': [note('G#3'), note('B5')]}}
        self.assertEqual(displayed_accidentals(altered, 4), {('1', 0, 'G3'): 'natural'})
        self.assertEqual(displayed_accidentals(following, 4), {})


if __name__ == '__main__':
    unittest.main()
