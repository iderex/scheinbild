"""Every state the spectrogram refuses, with the neighbouring state it accepts.

The pairs are the point. A refusal proved only by something absurd says the
constructor can raise; it does not say the constructor raises for the reason it
names. So each near miss below is the version of the same input that is correct,
usually one element or one value away from the case that trips it.

The valid spectrogram every case is built from is small on purpose. A three by
four array has a first dimension and a second dimension that differ, so a
transposed array is caught by a length check rather than passing because both
sides happened to be square.
"""

import unittest

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest
from scheinbild_model.spectrogram import Spectrogram, SpectrogramRefused

ENERGIES = 3
DELAYS = 4


def a_manifest() -> Manifest:
    return Manifest.of(parameters={}, seeds={}, code_version="0.0.0")


def an_energy_axis(points: int = ENERGIES) -> NDArray[np.float64]:
    return np.linspace(90.0, 110.0, points)


def a_delay_axis(points: int = DELAYS) -> NDArray[np.float64]:
    return np.linspace(-200.0, 200.0, points)


def counts(shape: tuple[int, ...] = (ENERGIES, DELAYS)) -> NDArray[np.float64]:
    return np.ones(shape)


def a_spectrogram(**overrides: object) -> Spectrogram:
    arguments: dict[str, object] = {
        "counts": counts(),
        "energy_axis_electronvolt": an_energy_axis(),
        "delay_axis_attosecond": a_delay_axis(),
        "manifest": a_manifest(),
    }
    arguments.update(overrides)
    # Every case below builds a spectrogram that is wrong in exactly one
    # argument, and a value of the wrong type is one of the states the
    # constructor refuses, so the overrides are deliberately not what it
    # declares. One code is named, so a misspelt argument is still reported.
    return Spectrogram.of(**arguments)  # type: ignore[arg-type]


class TheValidCaseIsValid(unittest.TestCase):
    """Everything below is a departure from this, so this one comes first."""

    def test_a_consistent_spectrogram_is_built(self) -> None:
        spectrogram = a_spectrogram()
        self.assertEqual(spectrogram.counts.shape, (ENERGIES, DELAYS))
        self.assertEqual(spectrogram.energy_axis_electronvolt.size, ENERGIES)
        self.assertEqual(spectrogram.delay_axis_attosecond.size, DELAYS)

    def test_the_manifest_travels_with_it(self) -> None:
        manifest = a_manifest()
        self.assertEqual(a_spectrogram(manifest=manifest).manifest, manifest)


class TheShapeMustAgreeWithTheAxes(unittest.TestCase):
    def test_an_array_with_too_few_energy_rows_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(counts=counts((ENERGIES - 1, DELAYS)))
        self.assertIn("first dimension", str(refusal.exception))

    def test_an_array_with_too_few_delay_columns_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(counts=counts((ENERGIES, DELAYS - 1)))
        self.assertIn("second dimension", str(refusal.exception))

    def test_a_transposed_array_is_refused(self) -> None:
        # The mistake the axis order rule exists for. It is caught here because
        # the two dimensions differ; on a square grid this case would pass and
        # the axis names in the constructor are what is left standing against it.
        with self.assertRaises(SpectrogramRefused):
            a_spectrogram(counts=counts((DELAYS, ENERGIES)))

    def test_a_one_dimensional_array_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(counts=np.ones(ENERGIES))
        self.assertIn("two dimensional", str(refusal.exception))

    def test_the_matching_shape_is_accepted(self) -> None:
        # The near miss for all four above: the same construction with the one
        # dimension put back.
        self.assertEqual(a_spectrogram().counts.shape, (ENERGIES, DELAYS))


class AnAxisMustBeSorted(unittest.TestCase):
    def test_a_descending_energy_axis_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(energy_axis_electronvolt=an_energy_axis()[::-1])
        self.assertIn("strictly increasing", str(refusal.exception))

    def test_a_descending_delay_axis_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(delay_axis_attosecond=a_delay_axis()[::-1])
        self.assertIn("strictly increasing", str(refusal.exception))

    def test_two_equal_neighbouring_points_are_refused(self) -> None:
        # The near miss inside the rule. A merely non decreasing axis passes a
        # test written with >= and gives a lookup a wrong answer rather than an
        # error, so the rule is strict and this is the case that says so.
        axis = an_energy_axis()
        axis[1] = axis[0]
        with self.assertRaises(SpectrogramRefused):
            a_spectrogram(energy_axis_electronvolt=axis)

    def test_an_ascending_axis_is_accepted(self) -> None:
        self.assertTrue(np.all(np.diff(a_spectrogram().energy_axis_electronvolt) > 0))


class AnAxisMustBeUniform(unittest.TestCase):
    def test_a_stretched_last_step_is_refused(self) -> None:
        axis = an_energy_axis()
        axis[-1] += 1.0
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(energy_axis_electronvolt=axis)
        self.assertIn("not uniform", str(refusal.exception))

    def test_a_non_uniform_delay_axis_is_refused(self) -> None:
        axis = a_delay_axis()
        axis[1] += 5.0
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(delay_axis_attosecond=axis)
        self.assertIn("not uniform", str(refusal.exception))

    def test_floating_point_roughness_is_accepted(self) -> None:
        # The near miss that decides the tolerance. An axis built by repeated
        # addition rather than by a linear space differs from a perfect grid in
        # the last few bits, and a rule with no tolerance refuses grids nobody
        # would call non uniform.
        step = 400.0 / (DELAYS - 1)
        axis = np.array([-200.0 + step * index for index in range(DELAYS)])
        self.assertEqual(
            a_spectrogram(delay_axis_attosecond=axis).delay_axis_attosecond.size,
            DELAYS,
        )

    def test_a_two_dimensional_axis_is_refused(self) -> None:
        # Found by removing the guard and watching the suite stay green. An axis
        # given as a column rather than as a row has the right number of
        # elements, so every length check below it passes, and the arithmetic
        # further on broadcasts into something with a plausible shape instead of
        # failing.
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(
                energy_axis_electronvolt=an_energy_axis().reshape(ENERGIES, 1)
            )
        self.assertIn("one dimensional", str(refusal.exception))

    def test_the_same_axis_flattened_is_accepted(self) -> None:
        axis = an_energy_axis().reshape(ENERGIES, 1).reshape(-1)
        self.assertEqual(
            a_spectrogram(energy_axis_electronvolt=axis).energy_axis_electronvolt.size,
            ENERGIES,
        )

    def test_an_axis_with_one_point_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(
                counts=counts((1, DELAYS)),
                energy_axis_electronvolt=np.array([100.0]),
            )
        self.assertIn("spacing", str(refusal.exception))


class TheEnergyAxisIsInElectronvolts(unittest.TestCase):
    def test_a_negative_energy_is_refused(self) -> None:
        axis = an_energy_axis()
        axis -= axis[-1] + 1.0
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(energy_axis_electronvolt=axis)
        self.assertIn("not negative", str(refusal.exception))

    def test_an_axis_starting_at_zero_is_accepted(self) -> None:
        # The near miss. Zero kinetic energy is a real edge of a real axis, and
        # a rule written with > rather than >= would refuse it.
        axis = np.linspace(0.0, 20.0, ENERGIES)
        self.assertEqual(
            a_spectrogram(energy_axis_electronvolt=axis).energy_axis_electronvolt[0],
            0.0,
        )

    def test_an_axis_in_another_unit_is_not_caught(self) -> None:
        # Stated as a test rather than as a sentence in a docstring, because
        # "this is not caught" is the kind of claim that quietly stops being
        # true and then nobody notices the guard was widened.
        in_hartree = an_energy_axis() / 27.211386245988
        self.assertEqual(
            a_spectrogram(
                energy_axis_electronvolt=in_hartree
            ).energy_axis_electronvolt.size,
            ENERGIES,
        )


class TheValuesMustBeCountsThatCanExist(unittest.TestCase):
    def test_a_negative_expected_count_is_refused(self) -> None:
        array = counts()
        array[1, 2] = -1.0
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(counts=array)
        self.assertIn("negative", str(refusal.exception))

    def test_a_zero_count_is_accepted(self) -> None:
        # The near miss. An empty bin is the commonest value in a real trace and
        # a rule written with <= rather than < would refuse every one of them.
        array = counts()
        array[1, 2] = 0.0
        self.assertEqual(
            a_spectrogram(counts=array).total_counts(), ENERGIES * DELAYS - 1
        )

    def test_a_value_that_is_not_a_number_is_refused(self) -> None:
        array = counts()
        array[0, 0] = np.nan
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(counts=array)
        self.assertIn("finite", str(refusal.exception))

    def test_an_axis_value_that_is_not_a_number_is_refused(self) -> None:
        axis = a_delay_axis()
        axis[0] = np.inf
        with self.assertRaises(SpectrogramRefused) as refusal:
            a_spectrogram(delay_axis_attosecond=axis)
        self.assertIn("finite", str(refusal.exception))


class TheOperationsEverythingDownstreamNeeds(unittest.TestCase):
    def setUp(self) -> None:
        self.spectrogram = a_spectrogram(
            counts=counts((5, DELAYS)),
            energy_axis_electronvolt=np.linspace(100.0, 108.0, 5),
        )

    def test_an_energy_lands_on_its_own_bin(self) -> None:
        self.assertEqual(self.spectrogram.energy_index(104.0), 2)

    def test_an_energy_between_bins_takes_the_nearer_one(self) -> None:
        self.assertEqual(self.spectrogram.energy_index(104.9), 2)
        self.assertEqual(self.spectrogram.energy_index(105.1), 3)

    def test_an_energy_off_the_axis_is_refused_rather_than_clamped(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            self.spectrogram.energy_index(200.0)
        self.assertIn("outside the energy axis", str(refusal.exception))

    def test_the_ends_of_the_axis_are_inside_it(self) -> None:
        self.assertEqual(self.spectrogram.energy_index(100.0), 0)
        self.assertEqual(self.spectrogram.energy_index(108.0), 4)

    def test_a_window_includes_both_ends(self) -> None:
        window = self.spectrogram.energy_window(102.0, 106.0)
        self.assertEqual(window, slice(1, 4))
        self.assertEqual(
            list(self.spectrogram.energy_axis_electronvolt[window]),
            [102.0, 104.0, 106.0],
        )

    def test_a_window_of_one_bin_is_one_bin(self) -> None:
        # The near miss for the inclusive end. A slice built as
        # slice(first, last) would return nothing here.
        window = self.spectrogram.energy_window(104.0, 104.0)
        self.assertEqual(self.spectrogram.energy_axis_electronvolt[window].size, 1)

    def test_a_backwards_window_is_refused(self) -> None:
        with self.assertRaises(SpectrogramRefused) as refusal:
            self.spectrogram.energy_window(106.0, 102.0)
        self.assertIn("backwards", str(refusal.exception))

    def test_the_window_applies_to_the_counts_and_the_axis_alike(self) -> None:
        window = self.spectrogram.energy_window(102.0, 106.0)
        self.assertEqual(
            self.spectrogram.counts[window].shape[0],
            self.spectrogram.energy_axis_electronvolt[window].size,
        )

    def test_the_total_is_every_expected_count(self) -> None:
        self.assertEqual(self.spectrogram.total_counts(), 5 * DELAYS)


if __name__ == "__main__":
    unittest.main()
