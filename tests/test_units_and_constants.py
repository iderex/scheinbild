"""The constant table refuses a row with no source, and the conversions invert.

These are the boring tests and they are the ones that catch the expensive
mistakes. A conversion applied in the wrong direction is not a crash and not a
wrong shape; it is a number that is out by a factor of about twenty seven and
looks like a physics result. The effect this board is measuring is a factor of
two, so a factor this code could introduce on its own has to be refused here
rather than argued about later.

The refusal tests build their own rows and hand them to the loader. They do not
break the shipped table, because a test that edited the table would be testing
whichever copy of it ran first.

Two of the tests check the shipped values against each other. The measured rows
of the table are checked against the rows that are exact by SI definition, using
relations that were not used to write either row down. That is a check on the
numbers this repository ships and not a restatement of them, and it is the only
kind of check on a citation a suite can make without a network, which the suite
refuses.
"""

import math
import unittest

from scheinbild_model.constants import CONSTANTS, Constant, ConstantRefused, load
from scheinbild_model.units import (
    atomic_time_to_attoseconds,
    attoseconds_to_atomic_time,
    electronvolts_to_hartree,
    hartree_to_electronvolts,
)

# The relative tolerance the cross checks below are held to. It is looser than
# double precision arithmetic and much tighter than the relative standard
# uncertainty CODATA quotes on the rows being checked, which is about 1.1e-12
# for both of them. So a disagreement this catches is a transcription error in
# this repository rather than a disagreement between adjustments.
_CROSS_CHECK_TOLERANCE = 1e-11

# The values the round trips are run over. A negative delay is in the set
# because delay is signed in this experiment and the sign is the thing under
# measurement; zero is in it because zero is where a divide and a multiply look
# identical.
_ROUND_TRIP_VALUES = (0.0, 1.0, -1.0, 1e-9, 105.2, -20.0, 1e9)

# The round trips are held to a relative tolerance rather than to a number of
# decimal places. A fixed number of places is an absolute bound, so the same
# assertion is vacuous at 1e-9 and unsatisfiable at 1e9, and the values above
# span both. This is a few times the double precision epsilon, which is what
# two floating point operations can cost and no more.
_ROUND_TRIP_TOLERANCE = 1e-14


class TheTableRefusesARowThatBreaksTheRule(unittest.TestCase):
    """Each rule the loader holds, refused one at a time.

    Every test here builds a row that is legal in every respect but one, so a
    failure names the rule that stopped biting rather than saying the loader
    still refuses something.
    """

    def _good_row(self, **overrides: object) -> Constant:
        row: dict[str, object] = {
            "symbol": "a_constant_for_this_test",
            "value": 1.5,
            "unit": "eV",
            "source": "A citation that would let a reader find the number.",
        }
        row.update(overrides)
        # The overrides are values the dataclass does not declare, on
        # purpose: every case below breaks exactly one field, and a value
        # of the wrong type is one of the things the loader refuses. The
        # suppression is on the construction and names one code, so a
        # misspelt field name is still reported here.
        return Constant(**row)  # type: ignore[arg-type]

    def test_a_row_with_a_good_source_loads(self) -> None:
        # The control. Without it, every refusal below would also pass against
        # a loader that refused everything.
        table = load([self._good_row()])
        self.assertEqual(table["a_constant_for_this_test"].value, 1.5)

    def test_an_empty_source_is_refused(self) -> None:
        with self.assertRaises(ConstantRefused) as refusal:
            load([self._good_row(source="")])
        self.assertIn("a_constant_for_this_test", str(refusal.exception))
        self.assertIn("source", str(refusal.exception))

    def test_a_blank_source_is_refused(self) -> None:
        # A space is the shortest way past a check that tests for the empty
        # string, and it is what somebody writes when they mean to come back.
        with self.assertRaises(ConstantRefused):
            load([self._good_row(source="   \n\t ")])

    def test_a_row_with_no_unit_is_refused(self) -> None:
        with self.assertRaises(ConstantRefused) as refusal:
            load([self._good_row(unit="")])
        self.assertIn("unit", str(refusal.exception))

    def test_a_row_with_no_symbol_is_refused(self) -> None:
        with self.assertRaises(ConstantRefused):
            load([self._good_row(symbol="  ")])

    def test_a_non_finite_value_is_refused(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ConstantRefused):
                    load([self._good_row(value=value)])

    def test_a_value_that_is_not_a_float_is_refused(self) -> None:
        # A string that looks like a number is the shape a table read from a
        # file would produce, and it arithmetics without raising in exactly one
        # direction: multiplication repeats it.
        for value in ("1.5", 2, True, None):
            with self.subTest(value=value):
                with self.assertRaises(ConstantRefused):
                    load([self._good_row(value=value)])

    def test_a_symbol_declared_twice_is_refused(self) -> None:
        with self.assertRaises(ConstantRefused) as refusal:
            load([self._good_row(), self._good_row(value=2.5)])
        self.assertIn("twice", str(refusal.exception))


class TheShippedTableObeysItsOwnRule(unittest.TestCase):
    """The table in the tree, not a fixture, held to what the loader refuses."""

    def test_every_row_carries_a_source_and_a_unit(self) -> None:
        self.assertNotEqual(len(CONSTANTS), 0)
        for symbol, constant in CONSTANTS.items():
            with self.subTest(symbol=symbol):
                self.assertTrue(constant.source.strip())
                self.assertTrue(constant.unit.strip())

    def test_the_table_cannot_be_written_to(self) -> None:
        # A model that could edit its own constants at run time would make the
        # manifest an incomplete description of the run.
        with self.assertRaises(TypeError):
            # Refused twice over, and the suppression is what lets the
            # second refusal be seen. The table is exposed as a Mapping, so
            # the checker refuses the write before it is made; the table is
            # also a MappingProxyType, so the write raises when it is made.
            # This asserts the second, which is the one a run meets.
            CONSTANTS["hartree_energy_in_electronvolt"] = None  # type: ignore[index]


class TheShippedValuesAgreeWithEachOther(unittest.TestCase):
    """The measured rows, checked against the rows that are exact by definition.

    Neither relation below was used to write either row down, so these compare
    two independent entries of the same adjustment rather than a number with
    itself.
    """

    def test_the_hartree_in_electronvolts_follows_from_joules_and_the_charge(
        self,
    ) -> None:
        # An energy in electronvolts is that energy in joules divided by the
        # elementary charge, and the elementary charge is exact in the SI.
        derived = (
            CONSTANTS["hartree_energy_in_joule"].value
            / CONSTANTS["elementary_charge"].value
        )
        self.assertAlmostEqual(
            derived / CONSTANTS["hartree_energy_in_electronvolt"].value,
            1.0,
            delta=_CROSS_CHECK_TOLERANCE,
        )

    def test_the_atomic_unit_of_time_follows_from_hbar_and_the_hartree(self) -> None:
        # The atomic unit of time is hbar divided by the Hartree energy, and
        # the Planck constant it comes from is exact in the SI.
        hbar = CONSTANTS["planck_constant"].value / (2.0 * math.pi)
        derived = hbar / CONSTANTS["hartree_energy_in_joule"].value
        self.assertAlmostEqual(
            derived / CONSTANTS["atomic_unit_of_time_in_second"].value,
            1.0,
            delta=_CROSS_CHECK_TOLERANCE,
        )


class TheConversionsInvert(unittest.TestCase):
    """A round trip through both directions returns what went in."""

    def assertRoundTrips(self, produced: float, value: float) -> None:
        self.assertTrue(
            math.isclose(produced, value, rel_tol=_ROUND_TRIP_TOLERANCE, abs_tol=0.0),
            f"A round trip returned {produced!r} for an input of {value!r}.",
        )

    def test_an_energy_survives_electronvolts_to_hartree_and_back(self) -> None:
        for value in _ROUND_TRIP_VALUES:
            with self.subTest(value=value):
                self.assertRoundTrips(
                    hartree_to_electronvolts(electronvolts_to_hartree(value)),
                    value,
                )

    def test_an_energy_survives_hartree_to_electronvolts_and_back(self) -> None:
        for value in _ROUND_TRIP_VALUES:
            with self.subTest(value=value):
                self.assertRoundTrips(
                    electronvolts_to_hartree(hartree_to_electronvolts(value)),
                    value,
                )

    def test_a_time_survives_attoseconds_to_atomic_units_and_back(self) -> None:
        for value in _ROUND_TRIP_VALUES:
            with self.subTest(value=value):
                self.assertRoundTrips(
                    atomic_time_to_attoseconds(attoseconds_to_atomic_time(value)),
                    value,
                )

    def test_a_time_survives_atomic_units_to_attoseconds_and_back(self) -> None:
        for value in _ROUND_TRIP_VALUES:
            with self.subTest(value=value):
                self.assertRoundTrips(
                    attoseconds_to_atomic_time(atomic_time_to_attoseconds(value)),
                    value,
                )


class TheConversionsGoTheRightWay(unittest.TestCase):
    """A round trip passes with both directions inverted, so this is separate.

    Swap the multiply and the divide in units.py and every test in the class
    above still passes, because the two errors cancel. These are the tests that
    do not.
    """

    def test_one_hartree_is_the_tabulated_number_of_electronvolts(self) -> None:
        self.assertEqual(
            hartree_to_electronvolts(1.0),
            CONSTANTS["hartree_energy_in_electronvolt"].value,
        )

    def test_the_tabulated_number_of_electronvolts_is_one_hartree(self) -> None:
        self.assertAlmostEqual(
            electronvolts_to_hartree(CONSTANTS["hartree_energy_in_electronvolt"].value),
            1.0,
            places=12,
        )

    def test_an_atomic_unit_of_time_is_about_twenty_four_attoseconds(self) -> None:
        # Not a tolerance on a physical value. The assertion is that an atomic
        # unit of time is tens of attoseconds and not hundredths of one, which
        # is what an inverted factor gives, and it is written as a band so that
        # it is not a second copy of the table row.
        self.assertGreater(atomic_time_to_attoseconds(1.0), 20.0)
        self.assertLess(atomic_time_to_attoseconds(1.0), 30.0)

    def test_a_photon_energy_in_electronvolts_is_a_few_hartree(self) -> None:
        # 105.2 eV is the photon energy the measurement this board is about was
        # made at, and it is about four hartree. An inverted conversion makes
        # it about three thousand.
        self.assertGreater(electronvolts_to_hartree(105.2), 3.0)
        self.assertLess(electronvolts_to_hartree(105.2), 5.0)


if __name__ == "__main__":
    unittest.main()
