"""The rules the satellite file needs, each one broken on its own, and the file.

Four rules arrive with that file and none of them is provable against it. Every
number in it is either a measured level or a citation, so a case that broke one
would have to break the tree's own data, and a case built out of the repository's
data proves the state of the tree on the day it ran rather than the guard. So the
refusals below are proved against documents written here, and the shipped file is
held to its own arithmetic separately at the end.

The rules: a number says whether it was measured or calculated; a second source
that disagrees is recorded beside the first rather than merged into it; a line's
strength arrives either as a cross section or as a ratio to another line and
never as both; and an intrinsic delay written into a data file is refused
wherever in the row it is put.

The last of those is the one worth spending a near miss on. A delay in a data
file does not fail: it loads, it is read, and it produces a spectrogram whose
timing came from a value no manifest carries and no freeze record covers, which
is the one property this board's results are supposed to have.
"""

import unittest

from scheinbild_model.atomic_data import (
    CALCULATED,
    LINEAR_IN_THE_LOGARITHMS,
    MEASURED,
    AtomicDataRefused,
    FetchStep,
    load,
    neon_2p_shake_up_satellites,
    neon_main_lines,
)

# The ionisation energy of Ne I, out of the same database the shipped satellite
# binding energies were built from. It is the number every entry there was added
# to, so subtracting it back out and comparing against the level the entry names
# is a check on that addition rather than a restatement of its result.
_NEON_IONISATION_ELECTRONVOLT = 21.564541

# Tight enough that a digit transcribed wrongly fails, and loose enough for the
# one subtraction between two numbers of this size.
_ARITHMETIC_TOLERANCE = 1e-9

# The binding energy of the 2s main line, out of the main line file rather than
# written here, is what the satellites are checked to sit above. Above in
# binding energy is below in kinetic energy, which is the whole reason this
# board has to care about them: the streaking field walks them through the
# window the 2s line is fitted in.
_TWO_S = "2s"

_GOOD_BINDING = """
[line.binding_energy]
unit = "eV"
method = "measured"
value = 52.1
source = "A citation precise enough to find the number again."
terms = "Public domain, so the value stands here rather than a fetch step."
"""

_GOOD_STRENGTH = """
[line.relative_strength]
relative_to = "2p"
method = "calculated"
photon_energy_electronvolt = [90.0, 106.0, 150.0]
value = [0.02, 0.015, 0.01]
source = "A citation precise enough to find the table again."
terms = "Redistribution permitted with attribution, which the citation gives."
"""

_FETCHED_STRENGTH = """
[line.relative_strength]
relative_to = "2p"
method = "calculated"
fetch = "Read table 1 of the citation above and divide by its main line row."
source = "A citation precise enough to find the table again."
terms = "The compiled table may not be redistributed, so only the citation is here."
"""

_GOOD_CROSS = """
[line.cross_section]
unit = "Mb"
method = "calculated"
photon_energy_electronvolt = [80.0, 132.3, 200.0]
value = [4.0, 2.0, 1.0]
source = "A citation precise enough to find the table again."
terms = "Redistribution permitted with attribution, which the citation gives."
"""

_DISAGREEMENT = """
[[line.binding_energy.disagreement]]
method = "calculated"
value = 52.4
source = "A second citation, holding a different number for the same state."
terms = "Public domain, so the value stands here rather than a fetch step."
"""


def _document(
    binding: str = _GOOD_BINDING,
    strength: str = _GOOD_STRENGTH,
    name: str = "a-satellite-for-this-test",
) -> str:
    """One legal document, with whichever part a case wants broken replaced."""
    return (
        f'interpolation = "{LINEAR_IN_THE_LOGARITHMS}"\n'
        "\n[[line]]\n"
        f'name = "{name}"\n'
        f"{binding}{strength}"
    )


class ANumberSaysWhetherItWasMeasuredOrCalculated(unittest.TestCase):
    """The marker, on each of the places a number can be, and what it may say."""

    def test_a_good_document_loads(self) -> None:
        # The control. Without it every case below would also pass against a
        # loader that refused everything it was given.
        line = load(_document())["a-satellite-for-this-test"]
        self.assertEqual(line.binding_energy.method, MEASURED)

    def test_a_binding_energy_with_no_method_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING.replace("method =", "#method =")))
        self.assertIn("method", str(refusal.exception))

    def test_a_strength_with_no_method_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(strength=_GOOD_STRENGTH.replace("method =", "#method =")))
        self.assertIn("method", str(refusal.exception))

    def test_a_method_outside_the_two_is_refused(self) -> None:
        # The near miss. "estimated" is what somebody writes about a number that
        # is neither, and it is the word that would let one through as if the
        # file had decided which of the two it was.
        broken = _GOOD_BINDING.replace('"measured"', '"estimated"')
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=broken))
        self.assertIn("estimated", str(refusal.exception))

    def test_a_fetch_step_carries_a_method_of_its_own(self) -> None:
        # A number that is not here is still a measured or a calculated number,
        # and the entry that stands in its place has to say which.
        line = load(_document(strength=_FETCHED_STRENGTH))["a-satellite-for-this-test"]
        strength = line.relative_strength
        assert isinstance(strength, FetchStep)
        self.assertEqual(strength.method, CALCULATED)


class TwoSourcesThatDisagreeAreBothRecorded(unittest.TestCase):
    """A second source stands beside the first, and neither is merged into it."""

    def test_a_disagreement_is_carried_beside_the_value(self) -> None:
        energy = load(_document(binding=_GOOD_BINDING + _DISAGREEMENT))[
            "a-satellite-for-this-test"
        ].binding_energy
        self.assertEqual(len(energy.disagreements), 1)
        # Both numbers survive, and neither is the average of the two. An
        # average is one number with the spread deleted and nothing on its face
        # admitting the deletion, which is the failure this shape prevents.
        self.assertEqual(energy.electronvolt, 52.1)
        self.assertEqual(energy.disagreements[0].value, 52.4)

    def test_a_disagreement_with_no_source_is_refused(self) -> None:
        broken = _DISAGREEMENT.replace("source =", "#source =")
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING + broken))
        self.assertIn("source", str(refusal.exception))

    def test_a_disagreement_with_no_method_is_refused(self) -> None:
        # The one worth the case. A disagreement between a measurement and a
        # calculation and a disagreement between two measurements say different
        # things about how much the number is worth, and a record that did not
        # separate them would read as the weaker of the two either way.
        broken = _DISAGREEMENT.replace("method =", "#method =")
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING + broken))
        self.assertIn("method", str(refusal.exception))

    def test_a_disagreement_with_neither_a_value_nor_a_fetch_step_is_refused(
        self,
    ) -> None:
        broken = _DISAGREEMENT.replace("value = 52.4", "#value = 52.4")
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING + broken))
        self.assertIn("fetch", str(refusal.exception))

    def test_a_disagreement_with_both_a_value_and_a_fetch_step_is_refused(self) -> None:
        broken = _DISAGREEMENT + 'fetch = "Retrieve it from the citation above."\n'
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING + broken))
        self.assertIn("both", str(refusal.exception))

    def test_more_than_one_disagreement_is_carried(self) -> None:
        # A third source is not a replacement for the second. The shape that
        # held only the last would drop the rest of the spread without saying so.
        second = _DISAGREEMENT.replace("52.4", "52.6")
        energy = load(_document(binding=_GOOD_BINDING + _DISAGREEMENT + second))[
            "a-satellite-for-this-test"
        ].binding_energy
        self.assertEqual([each.value for each in energy.disagreements], [52.4, 52.6])


class ALineIsAsStrongAsOneSourceSaysAndNotAsTwo(unittest.TestCase):
    """A cross section or a ratio, exactly one, and what reading the other does."""

    def test_a_strength_table_is_read_between_its_rows(self) -> None:
        strength = load(_document())[
            "a-satellite-for-this-test"
        ].tabulated_relative_strength()
        self.assertEqual(strength.strength_at(106.0), 0.015)
        self.assertLess(strength.strength_at(120.0), 0.015)
        self.assertGreater(strength.strength_at(120.0), 0.01)

    def test_a_photon_energy_outside_the_strength_table_is_refused(self) -> None:
        # The same rule the cross section tables are held to, for the same
        # reason: a satellite strength outside the range its source reported is
        # a number nobody measured or calculated.
        strength = load(_document())[
            "a-satellite-for-this-test"
        ].tabulated_relative_strength()
        with self.assertRaises(AtomicDataRefused) as refusal:
            strength.strength_at(160.0)
        self.assertIn("150.0", str(refusal.exception))

    def test_a_line_with_both_a_cross_section_and_a_strength_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(strength=_GOOD_STRENGTH + _GOOD_CROSS))
        self.assertIn("both", str(refusal.exception))

    def test_a_line_with_neither_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(strength=""))
        self.assertIn("neither", str(refusal.exception))

    def test_a_strength_that_does_not_say_what_it_is_relative_to_is_refused(
        self,
    ) -> None:
        # A ratio with no denominator named is a number that means whatever the
        # reader assumes, and the assumption a reader makes here decides how
        # strong the contamination in the spectrogram is.
        broken = _GOOD_STRENGTH.replace("relative_to =", "#relative_to =")
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(strength=broken))
        self.assertIn("relative_to", str(refusal.exception))

    def test_asking_a_ratio_line_for_a_cross_section_refuses_and_says_why(self) -> None:
        line = load(_document())["a-satellite-for-this-test"]
        with self.assertRaises(AtomicDataRefused) as refusal:
            line.tabulated_cross_section()
        self.assertIn("relative", str(refusal.exception))

    def test_asking_a_cross_section_line_for_a_ratio_refuses_and_says_why(self) -> None:
        line = load(_document(strength=_GOOD_CROSS))["a-satellite-for-this-test"]
        with self.assertRaises(AtomicDataRefused) as refusal:
            line.tabulated_relative_strength()
        self.assertIn("cross section", str(refusal.exception))

    def test_asking_a_fetched_ratio_for_its_table_names_the_step(self) -> None:
        line = load(_document(strength=_FETCHED_STRENGTH))["a-satellite-for-this-test"]
        with self.assertRaises(AtomicDataRefused) as refusal:
            line.tabulated_relative_strength()
        self.assertIn("Read table 1", str(refusal.exception))


class AnIntrinsicDelayIsRefusedWhereverItIsWritten(unittest.TestCase):
    """The delay is a run parameter, and a data file may not hold one anywhere."""

    def test_a_delay_at_the_top_of_a_row_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(
                _document()
                .replace("[line.binding_energy]", "")
                .replace(
                    'name = "a-satellite-for-this-test"',
                    'name = "a-satellite-for-this-test"\nintrinsic_delay_attosecond = 12.0'
                    "\n[line.binding_energy]",
                )
            )
        self.assertIn("intrinsic_delay_attosecond", str(refusal.exception))

    def test_a_delay_inside_a_nested_table_is_refused(self) -> None:
        # The near miss, and the one somebody actually writes: the delay put
        # beside the binding energy it belongs to rather than at the top of the
        # row, where a check that read only the top level would walk past it.
        broken = _GOOD_BINDING + "delay_attosecond = 12.0\n"
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=broken))
        self.assertIn("delay_attosecond", str(refusal.exception))

    def test_a_field_merely_holding_the_word_is_refused_too(self) -> None:
        # Deliberately blunt. A field named for the delay under any spelling is
        # refused, because the failure this prevents is a timing number reaching
        # the model from outside the manifest and the spelling does not change
        # that.
        broken = _GOOD_BINDING + 'emission_delay = "later"\n'
        with self.assertRaises(AtomicDataRefused):
            load(_document(binding=broken))

    def test_no_packaged_data_file_carries_one(self) -> None:
        # The other half. The rule above refuses a document offered to the
        # loader; this says the files the package actually ships are documents
        # that rule lets through, which is what a reader wants to know.
        self.assertNotEqual(len(neon_main_lines()), 0)
        self.assertNotEqual(len(neon_2p_shake_up_satellites()), 0)


class TheShippedSatelliteFileObeysItsOwnRule(unittest.TestCase):
    """The file in the tree, held to what the loader refuses and to itself."""

    def test_every_entry_carries_a_source_terms_and_a_method(self) -> None:
        satellites = neon_2p_shake_up_satellites()
        self.assertNotEqual(len(satellites), 0)
        for name, line in satellites.items():
            strength = line.relative_strength
            assert strength is not None  # refused at load if it were absent
            with self.subTest(name=name):
                self.assertTrue(line.binding_energy.source.strip())
                self.assertTrue(line.binding_energy.terms.strip())
                self.assertEqual(line.binding_energy.method, MEASURED)
                self.assertTrue(strength.source.strip())
                self.assertTrue(strength.terms.strip())
                self.assertEqual(strength.method, CALCULATED)

    def test_every_binding_energy_is_its_own_level_plus_the_ionisation_energy(
        self,
    ) -> None:
        # Each entry was built by adding two rows of one database and its source
        # writes the sum out. This subtracts the ionisation energy back off and
        # compares against the level the source names, so a digit transcribed
        # wrongly into either fails here rather than passing as a value compared
        # with itself.
        for name, line in neon_2p_shake_up_satellites().items():
            quoted = line.binding_energy.source.split("lies ")[1].split(" eV")[0]
            with self.subTest(name=name):
                self.assertAlmostEqual(
                    line.binding_energy.electronvolt - _NEON_IONISATION_ELECTRONVOLT,
                    float(quoted),
                    delta=_ARITHMETIC_TOLERANCE,
                )

    def test_every_satellite_sits_above_the_inner_main_line(self) -> None:
        # The ordering the board rests on, checked against the other file rather
        # than against a number written here. A satellite below the 2s line in
        # binding energy is above it in kinetic energy, on the far side of the
        # window the 2s line is fitted in, and it would contaminate nothing.
        inner = neon_main_lines()[_TWO_S].binding_energy.electronvolt
        for name, line in neon_2p_shake_up_satellites().items():
            with self.subTest(name=name):
                self.assertGreater(line.binding_energy.electronvolt, inner)

    def test_every_entry_records_the_calculated_source_as_a_disagreement(self) -> None:
        for name, line in neon_2p_shake_up_satellites().items():
            with self.subTest(name=name):
                recorded = line.binding_energy.disagreements
                self.assertEqual(len(recorded), 1)
                self.assertEqual(recorded[0].method, CALCULATED)
                self.assertIsNone(recorded[0].value)
                self.assertIsNotNone(recorded[0].fetch)

    def test_every_strength_is_a_citation_and_not_a_number(self) -> None:
        # The negative one. This file ships no strength, because the only source
        # found for them may not be reproduced here, and a run that needs one
        # follows the step in the entry. The day a strength lands as a value
        # this case fails, which is the right moment to read the file again.
        for name, line in neon_2p_shake_up_satellites().items():
            with self.subTest(name=name):
                self.assertIsInstance(line.relative_strength, FetchStep)
                self.assertEqual(line.strength_relative_to, "2p")

    def test_no_satellite_shares_a_binding_energy_with_another(self) -> None:
        energies = [
            line.binding_energy.electronvolt
            for line in neon_2p_shake_up_satellites().values()
        ]
        self.assertEqual(len(set(energies)), len(energies))


if __name__ == "__main__":
    unittest.main()
