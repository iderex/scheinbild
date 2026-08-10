"""The atomic data loader refuses what it names, and the shipped file obeys it.

The refusal cases are documents written here rather than edits to the file in the
tree. A case built out of the repository's own data proves the state of the tree
on the day it ran and not the guard, and a test that had to break the shipped
file to prove a rule would be testing whichever copy of it ran first.

The cases against the shipped file are a different kind and are kept apart below.
None of them restates a value: they check the two columns against each other, and
against a third number from the same database that was not used to write either
of them down. A test that asserted the 2s binding energy equals the number in the
file would pass against any transcription error, because it would be comparing
the file with itself.

The column swap is the mistake worth spending a test on. The 2s trace is weaker
than the 2p trace, and that ratio is what decides how badly the satellites can
distort the 2s delay this board is about. Two columns exchanged produce a
spectrogram that looks entirely reasonable and answers the board's question
backwards.
"""

import unittest

from scheinbild_model.atomic_data import (
    CALCULATED,
    LINEAR_IN_THE_LOGARITHMS,
    MEASURED,
    AtomicDataRefused,
    FetchStep,
    load,
    neon_main_lines,
    relative_cross_section,
)

# The energy of the Ne II level 2s.2p6 2S1/2 above the Ne II ground level, out of
# the NIST Atomic Spectra Database. It is the third number of the pair of rows
# the 2s binding energy in the file was built from, so comparing the difference
# of the two shipped binding energies against it is a check on the arithmetic in
# that entry rather than a restatement of its value.
_NE_II_TWO_S_HOLE_ELECTRONVOLT = 26.910472

# Tight enough that a transcription error in any digit fails, and loose enough
# for the one subtraction between two numbers of this size.
_ARITHMETIC_TOLERANCE = 1e-9

# The highest tabulated photon energy at which the 2p cross section is still the
# larger of the two in the shipped tables. Above it the two columns cross, which
# is the source saying so rather than a defect: the 2p cross section falls off
# faster, and at 600 eV it is already below the 2s one. Read off the file with
#
#     python -c "from scheinbild_model.atomic_data import neon_main_lines as n; \
#     t = {k: v.tabulated_cross_section() for k, v in n().items()}; \
#     print([(e, t['2p'].megabarn_at(e) > t['2s'].megabarn_at(e)) \
#     for e in t['2s'].photon_energy_electronvolt])"
_THE_COLUMNS_CROSS_ABOVE_ELECTRONVOLT = 300.0

_GOOD_BINDING = """
[line.binding_energy]
unit = "eV"
method = "measured"
value = 21.5
source = "A citation precise enough to find the number again."
terms = "Public domain, so the value stands here rather than a fetch step."
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


def _document(
    binding: str = _GOOD_BINDING,
    cross: str = _GOOD_CROSS,
    interpolation: str = LINEAR_IN_THE_LOGARITHMS,
    name: str = "a-line-for-this-test",
    second: str = "",
) -> str:
    """One legal document, with whichever part a case wants broken replaced."""
    return (
        f'interpolation = "{interpolation}"\n'
        "\n[[line]]\n"
        f'name = "{name}"\n'
        f"{binding}{cross}{second}"
    )


class TheLoaderRefusesADocumentThatBreaksTheRule(unittest.TestCase):
    """Each rule the loader holds, broken one at a time.

    Every case here is legal in every respect but one, so a failure names the
    rule that stopped biting rather than saying the loader still refuses
    something.
    """

    def test_a_good_document_loads(self) -> None:
        # The control. Without it every case below would also pass against a
        # loader that refused everything it was given.
        lines = load(_document())
        self.assertEqual(sorted(lines), ["a-line-for-this-test"])
        self.assertEqual(
            lines["a-line-for-this-test"].binding_energy.electronvolt, 21.5
        )

    def test_a_binding_energy_with_no_source_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(binding=_GOOD_BINDING.replace('source = "A citation', "#")))
        self.assertIn("source", str(refusal.exception))

    def test_a_blank_source_is_refused(self) -> None:
        # A space is the shortest way past a check that tests for the empty
        # string, and it is what somebody writes when they mean to come back.
        broken = _GOOD_BINDING.replace(
            'source = "A citation precise enough to find the number again."',
            'source = "   "',
        )
        with self.assertRaises(AtomicDataRefused):
            load(_document(binding=broken))

    def test_a_cross_section_with_no_terms_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(cross=_GOOD_CROSS.replace("terms =", "#terms =")))
        self.assertIn("terms", str(refusal.exception))

    def test_a_cross_section_with_neither_a_value_nor_a_fetch_step_is_refused(
        self,
    ) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(cross=_GOOD_CROSS.replace("value = [4.0", "#value = [4.0")))
        self.assertIn("fetch", str(refusal.exception))

    def test_a_cross_section_with_both_a_value_and_a_fetch_step_is_refused(
        self,
    ) -> None:
        both = _GOOD_CROSS + 'fetch = "Download the table and put it here."\n'
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(cross=both))
        self.assertIn("both", str(refusal.exception))

    def test_a_table_whose_columns_differ_in_length_is_refused(self) -> None:
        # The near miss. A row deleted from one column and not the other leaves
        # a table that parses, loads and pairs every energy with the wrong value.
        short = _GOOD_CROSS.replace("value = [4.0, 2.0, 1.0]", "value = [4.0, 2.0]")
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(cross=short))
        self.assertIn("length", str(refusal.exception))

    def test_a_photon_axis_that_does_not_increase_is_refused(self) -> None:
        out_of_order = _GOOD_CROSS.replace(
            "photon_energy_electronvolt = [80.0, 132.3, 200.0]",
            "photon_energy_electronvolt = [80.0, 200.0, 132.3]",
        )
        with self.assertRaises(AtomicDataRefused):
            load(_document(cross=out_of_order))

    def test_a_repeated_photon_energy_is_refused(self) -> None:
        # The near miss for the case above: a table that never decreases but
        # holds one energy twice has two cross sections at one point and a zero
        # width interval between them to divide by.
        repeated = _GOOD_CROSS.replace(
            "photon_energy_electronvolt = [80.0, 132.3, 200.0]",
            "photon_energy_electronvolt = [80.0, 132.3, 132.3]",
        )
        with self.assertRaises(AtomicDataRefused):
            load(_document(cross=repeated))

    def test_a_cross_section_of_zero_is_refused(self) -> None:
        # An empty cell in a source table is not a zero, and it is what a
        # transcription that filled the gaps in would produce.
        zeroed = _GOOD_CROSS.replace(
            "value = [4.0, 2.0, 1.0]", "value = [4.0, 0.0, 1.0]"
        )
        with self.assertRaises(AtomicDataRefused):
            load(_document(cross=zeroed))

    def test_a_document_naming_an_unknown_interpolation_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(interpolation="cubic-spline"))
        self.assertIn("cubic-spline", str(refusal.exception))

    def test_a_document_naming_no_interpolation_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused):
            load(_document().split("\n", maxsplit=1)[1])

    def test_a_document_with_no_line_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused):
            load(f'interpolation = "{LINEAR_IN_THE_LOGARITHMS}"\n')

    def test_a_line_declared_twice_is_refused(self) -> None:
        again = '\n[[line]]\nname = "a-line-for-this-test"\n' + _GOOD_BINDING
        with self.assertRaises(AtomicDataRefused) as refusal:
            load(_document(second=again + _GOOD_CROSS))
        self.assertIn("twice", str(refusal.exception))

    def test_a_document_that_is_not_valid_toml_is_refused(self) -> None:
        with self.assertRaises(AtomicDataRefused):
            load("interpolation = ")


class ANumberThatMayNotBeShippedCarriesItsFetchStep(unittest.TestCase):
    """The other shape an entry may take, and what asking it for a value does."""

    _FETCHED = """
[line.cross_section]
unit = "Mb"
method = "calculated"
fetch = "Retrieve table 3 from the citation above and write the rows here."
source = "A citation precise enough to find the table again."
terms = "The compiled table may not be redistributed, so only the citation is here."
"""

    def test_an_entry_with_a_fetch_step_loads(self) -> None:
        line = load(_document(cross=self._FETCHED))["a-line-for-this-test"]
        self.assertIsInstance(line.cross_section, FetchStep)

    def test_asking_it_for_a_table_refuses_and_names_the_step(self) -> None:
        line = load(_document(cross=self._FETCHED))["a-line-for-this-test"]
        with self.assertRaises(AtomicDataRefused) as refusal:
            line.tabulated_cross_section()
        self.assertIn("Retrieve table 3", str(refusal.exception))


class TheInterpolationReadsTheTableItWasGiven(unittest.TestCase):
    """What the method does at a tabulated point, between two, and past the ends."""

    # A table whose upper row does not survive a round trip through two
    # logarithms and an exponential. It is the near miss for the case below and
    # the reason the exact hit is written as a read of the table rather than
    # left to the arithmetic: computing this row from itself gives
    # 1.7094999999999998 rather than 1.7095. Found by sweeping tables of this
    # shape, and the command is in the pull request that landed this file.
    _INEXACT = """
[line.cross_section]
unit = "Mb"
method = "calculated"
photon_energy_electronvolt = [799.7, 1961.9]
value = [7.1334, 1.7095]
source = "A citation precise enough to find the table again."
terms = "Redistribution permitted with attribution, which the citation gives."
"""

    def test_a_tabulated_photon_energy_returns_the_tabulated_value(self) -> None:
        table = load(_document())["a-line-for-this-test"].tabulated_cross_section()
        for energy, value in zip(table.photon_energy_electronvolt, table.megabarn):
            with self.subTest(energy=energy):
                # Exactly, not nearly. A photon energy that is in the table is
                # answered by reading the table, so the arithmetic that could
                # move the last place never runs.
                self.assertEqual(table.megabarn_at(energy), value)

    def test_a_row_the_arithmetic_would_not_reproduce_is_returned_exactly(self) -> None:
        line = load(_document(cross=self._INEXACT))["a-line-for-this-test"]
        table = line.tabulated_cross_section()
        self.assertEqual(table.megabarn_at(1961.9), 1.7095)

    def test_a_value_between_two_rows_lies_between_them(self) -> None:
        table = load(_document())["a-line-for-this-test"].tabulated_cross_section()
        self.assertLess(table.megabarn_at(100.0), 4.0)
        self.assertGreater(table.megabarn_at(100.0), 2.0)

    def test_a_photon_energy_below_the_table_is_refused(self) -> None:
        table = load(_document())["a-line-for-this-test"].tabulated_cross_section()
        with self.assertRaises(AtomicDataRefused) as refusal:
            table.megabarn_at(79.9)
        self.assertIn("80.0", str(refusal.exception))

    def test_a_photon_energy_above_the_table_is_refused(self) -> None:
        table = load(_document())["a-line-for-this-test"].tabulated_cross_section()
        with self.assertRaises(AtomicDataRefused):
            table.megabarn_at(200.1)


class TheShippedFileObeysItsOwnRule(unittest.TestCase):
    """The file in the tree, held to what the loader refuses and to itself."""

    def test_every_line_carries_a_source_and_terms_for_every_number(self) -> None:
        lines = neon_main_lines()
        self.assertNotEqual(len(lines), 0)
        for name, line in lines.items():
            with self.subTest(name=name):
                self.assertTrue(line.binding_energy.source.strip())
                self.assertTrue(line.binding_energy.terms.strip())
                cross = line.cross_section
                assert cross is not None  # every main line entry tabulates one
                self.assertTrue(cross.source.strip())
                self.assertTrue(cross.terms.strip())

    def test_the_binding_energies_are_measured_and_the_cross_sections_calculated(
        self,
    ) -> None:
        # Not decoration. The ratio between the two lines is what decides how
        # badly one can distort the other, and it rests on a central potential
        # rather than on an instrument. A file that let a reader weigh it as a
        # measurement would be overstating what this board's input is worth.
        for name, line in neon_main_lines().items():
            cross = line.cross_section
            assert cross is not None
            with self.subTest(name=name):
                self.assertEqual(line.binding_energy.method, MEASURED)
                self.assertEqual(cross.method, CALCULATED)

    def test_the_lines_this_board_needs_are_there(self) -> None:
        self.assertEqual(sorted(neon_main_lines()), ["2p", "2s"])

    def test_the_two_binding_energies_differ_by_the_tabulated_hole_energy(self) -> None:
        # The 2s entry was built by adding two rows of the same database. This
        # subtracts them again against the third number, so a digit transcribed
        # wrongly into either entry fails here rather than passing as a value
        # compared with itself.
        lines = neon_main_lines()
        difference = (
            lines["2s"].binding_energy.electronvolt
            - lines["2p"].binding_energy.electronvolt
        )
        self.assertAlmostEqual(
            difference, _NE_II_TWO_S_HOLE_ELECTRONVOLT, delta=_ARITHMETIC_TOLERANCE
        )

    def test_the_two_p_line_is_the_stronger_one_at_the_energies_this_board_uses(
        self,
    ) -> None:
        # The column swap, which is the transcription error that would answer
        # this board's question backwards while looking entirely reasonable.
        #
        # Bounded rather than asserted everywhere, because the ordering really
        # does reverse: the 2p cross section falls off faster with photon
        # energy, and somewhere between 300 eV and 600 eV the source's two
        # columns cross. A test asserting the ordering over the whole table
        # would be asserting something the source does not say. The bound is
        # above the photon energies this board works at, which are around a
        # hundred electronvolts.
        lines = neon_main_lines()
        weak = lines["2s"].tabulated_cross_section()
        strong = lines["2p"].tabulated_cross_section()
        for energy in weak.photon_energy_electronvolt:
            if energy > _THE_COLUMNS_CROSS_ABOVE_ELECTRONVOLT:
                continue
            with self.subTest(energy=energy):
                self.assertGreater(strong.megabarn_at(energy), weak.megabarn_at(energy))

    def test_the_relative_cross_section_is_the_ratio_of_the_two_tables(self) -> None:
        lines = neon_main_lines()
        at = 132.3
        self.assertAlmostEqual(
            relative_cross_section(lines["2s"], lines["2p"], at),
            lines["2s"].tabulated_cross_section().megabarn_at(at)
            / lines["2p"].tabulated_cross_section().megabarn_at(at),
        )

    def test_the_shipped_tables_never_overshoot_their_neighbours(self) -> None:
        # The property the interpolation was chosen for, over the whole shipped
        # range rather than at one point. A method that overshoots produces a
        # cross section outside the pair of rows it sits between, and a spline
        # through points this sparse does exactly that.
        for name, line in neon_main_lines().items():
            table = line.tabulated_cross_section()
            grid = table.photon_energy_electronvolt
            for index in range(len(grid) - 1):
                low, high = grid[index], grid[index + 1]
                here, there = table.megabarn[index], table.megabarn[index + 1]
                for step in range(1, 8):
                    energy = low + (high - low) * step / 8
                    with self.subTest(name=name, energy=energy):
                        self.assertLessEqual(
                            table.megabarn_at(energy), max(here, there)
                        )
                        self.assertGreaterEqual(
                            table.megabarn_at(energy), min(here, there)
                        )


if __name__ == "__main__":
    unittest.main()
