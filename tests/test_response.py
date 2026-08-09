"""What the response applies, what it conserves, and what a single kernel gets wrong.

Three of these are the reason the module is written the way it is rather than the
obvious way, so each one says what it would catch.

The width test compares the width that comes out of the built column against the
width the derivation predicts, and the factor of two between a time resolution
and an energy resolution is checked against the time of flight relation itself
rather than against the formula the module uses. A test that restated
`2 * r * E` would agree with the module about a factor it also got from the
module.

The comparison against a single kernel is not a guard over the shipped path. It
is the evidence that the expensive implementation earns its cost, so it asserts a
lower bound on the difference and fails if the two ever stop differing.

Every tolerance below is derived beside the assertion it belongs to, with the
size of the mistake it can still see, because a tolerance widened until a test
went green describes the implementation instead of checking it.
"""

import math
import unittest

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest, ParameterValue
from scheinbild_model.response import (
    CONSTANT_WIDTH,
    ENERGY_WIDTH,
    RELATIVE_TIME_RESOLUTION,
    RESPONSE_FORM,
    TIME_OF_FLIGHT,
    ResponseRefused,
    apply_response,
    form_of,
    response_matrix,
    single_kernel_response,
    widths_electronvolt,
)
from scheinbild_model.spectrogram import Spectrogram

# A relative time resolution of one percent, so the energy width is two percent
# of the kinetic energy. Nothing published is being quoted here: the values a
# run uses are frozen in milestone 7, and these are chosen to make the grids
# below small enough to run in a suite.
RELATIVE = 0.01

# The energy window. Wide enough that the width at the top is three times the
# width at the bottom, which is what makes a single kernel visibly wrong.
LOW_ELECTRONVOLT = 50.0
HIGH_ELECTRONVOLT = 150.0

# Ten grid points per standard deviation at the narrowest column, which is five
# times what the module refuses below. The width test needs the sampling error
# to be far under the tolerance it asserts, and the measurement quoted at
# MINIMUM_POINTS_PER_WIDTH says two points is already at the last place of a
# float.
POINTS_PER_NARROWEST_WIDTH = 10.0

DELAYS = 3


def energy_axis() -> NDArray[np.float64]:
    narrowest = 2.0 * RELATIVE * LOW_ELECTRONVOLT
    spacing = narrowest / POINTS_PER_NARROWEST_WIDTH
    points = int(round((HIGH_ELECTRONVOLT - LOW_ELECTRONVOLT) / spacing)) + 1
    return np.linspace(LOW_ELECTRONVOLT, HIGH_ELECTRONVOLT, points)


def a_manifest(overrides: dict[str, ParameterValue] | None = None) -> Manifest:
    parameters: dict[str, ParameterValue] = {
        RESPONSE_FORM: TIME_OF_FLIGHT,
        RELATIVE_TIME_RESOLUTION: RELATIVE,
    }
    parameters.update(overrides or {})
    return Manifest.of(parameters=parameters, seeds={}, code_version="0.0.0")


def a_spectrogram(
    manifest: Manifest | None = None, energy: NDArray[np.float64] | None = None
) -> Spectrogram:
    axis = energy_axis() if energy is None else energy
    return Spectrogram.of(
        counts=np.ones((axis.size, DELAYS)),
        energy_axis_electronvolt=axis,
        delay_axis_attosecond=np.linspace(-200.0, 200.0, DELAYS),
        manifest=a_manifest() if manifest is None else manifest,
    )


def applied_width(
    matrix: NDArray[np.float64], axis: NDArray[np.float64], at: int
) -> float:
    """The standard deviation of one column of a built response, in electronvolts.

    Read off the column rather than off the parameters, so this is what the model
    would actually apply and not what it meant to.
    """
    weights = matrix[:, at]
    offset = axis - axis[at]
    return math.sqrt(float((weights * offset * offset).sum()))


class TheTwoFormsAreBothAvailableAndNeitherIsADefault(unittest.TestCase):
    def test_the_time_of_flight_form_is_selectable(self) -> None:
        self.assertEqual(form_of(a_manifest()), TIME_OF_FLIGHT)

    def test_the_constant_width_form_is_selectable(self) -> None:
        manifest = a_manifest({RESPONSE_FORM: CONSTANT_WIDTH, ENERGY_WIDTH: 1.5})
        self.assertEqual(form_of(manifest), CONSTANT_WIDTH)

    def test_a_form_nobody_named_is_refused(self) -> None:
        with self.assertRaises(ResponseRefused) as refusal:
            form_of(a_manifest({RESPONSE_FORM: "gaussian"}))
        self.assertIn(TIME_OF_FLIGHT, str(refusal.exception))
        self.assertIn(CONSTANT_WIDTH, str(refusal.exception))

    def test_a_resolution_of_zero_is_refused(self) -> None:
        with self.assertRaises(ResponseRefused):
            widths_electronvolt(
                a_manifest({RELATIVE_TIME_RESOLUTION: 0.0}), energy_axis()
            )

    def test_a_resolution_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(ResponseRefused):
            widths_electronvolt(
                a_manifest({RELATIVE_TIME_RESOLUTION: "narrow"}), energy_axis()
            )

    def test_a_resolution_one_step_above_zero_is_accepted(self) -> None:
        # The neighbour. Without it the refusal above would also pass against a
        # module that refused every resolution there is.
        widths = widths_electronvolt(
            a_manifest({RELATIVE_TIME_RESOLUTION: RELATIVE}), energy_axis()
        )
        self.assertTrue(bool(np.all(widths > 0.0)))


class TheAppliedWidthIsTheWidthTheDerivationPredicts(unittest.TestCase):
    # The column is built from a Gaussian sampled on the grid and normalised, so
    # the width read back off it differs from the width it was built from for
    # two reasons: the sampling, and the truncation at the ends of the axis.
    #
    # Sampling: measured at ten points per standard deviation, where a unit
    # Gaussian returns its own width to the last place of a float. That is the
    # measurement quoted at MINIMUM_POINTS_PER_WIDTH in the module.
    #
    # Truncation: the columns compared below sit at least eight standard
    # deviations inside both ends of the axis. The second moment a normal
    # distribution carries beyond eight standard deviations is under 1e-13 of
    # its total, so the width comes back short by under 1e-13 of itself.
    #
    # A tolerance of 1e-9 is four orders above both and still sees a factor of
    # two, a full width mistaken for a half width, or a percent of drift.
    TOLERANCE = 1e-9

    # How far inside the axis a column has to sit for the truncation above to
    # hold. The widest column is at the top of the axis.
    CLEARANCE_WIDTHS = 8.0

    def interior_indices(self, axis: NDArray[np.float64]) -> list[int]:
        widths = widths_electronvolt(a_manifest(), axis)
        room = self.CLEARANCE_WIDTHS * float(widths[-1])
        return [
            index
            for index, energy in enumerate(axis)
            if axis[0] + room <= energy <= axis[-1] - room
        ]

    def test_the_applied_width_matches_the_prediction_at_several_energies(self) -> None:
        axis = energy_axis()
        matrix = response_matrix(a_manifest(), axis)
        predicted = widths_electronvolt(a_manifest(), axis)
        interior = self.interior_indices(axis)
        self.assertGreater(len(interior), 0, "no column sits clear of both ends")
        for index in interior[:: max(1, len(interior) // 5)]:
            with self.subTest(energy=float(axis[index])):
                self.assertAlmostEqual(
                    applied_width(matrix, axis, index) / float(predicted[index]),
                    1.0,
                    delta=self.TOLERANCE,
                )

    def test_the_factor_of_two_is_the_one_the_flight_time_relation_gives(self) -> None:
        # The check the module's own docstring says is where a factor goes
        # missing, and it is made against the time of flight relation rather
        # than against the formula the module applies.
        #
        # Arrival time goes as E to the minus one half, so energy goes as t to
        # the minus two. Perturbing the arrival time by a relative epsilon and
        # reading the relative change in energy gives the coefficient the module
        # should be using, without that coefficient being written here.
        epsilon = 1e-8
        # Enough figures that the second order term, of order epsilon, is far
        # under the comparison, and enough room above the last place of a float
        # that the difference is not noise.
        tolerance = 1e-6

        def energy_from_arrival_time(time: float) -> float:
            return float(time ** (-2.0))

        at_rest = energy_from_arrival_time(1.0)
        perturbed = energy_from_arrival_time(1.0 + epsilon)
        coefficient = abs(perturbed - at_rest) / at_rest / epsilon

        axis = energy_axis()
        widths = widths_electronvolt(a_manifest(), axis)
        applied_coefficient = float(widths[0]) / float(axis[0]) / RELATIVE
        self.assertAlmostEqual(applied_coefficient, coefficient, delta=tolerance)

    def test_the_width_grows_with_kinetic_energy(self) -> None:
        # The property that makes a convolution wrong, stated on its own so a
        # failure says which of the two forms was applied.
        axis = energy_axis()
        widths = widths_electronvolt(a_manifest(), axis)
        self.assertTrue(bool(np.all(np.diff(widths) > 0.0)))

    def test_the_constant_width_form_does_not_grow(self) -> None:
        axis = energy_axis()
        manifest = a_manifest({RESPONSE_FORM: CONSTANT_WIDTH, ENERGY_WIDTH: 2.0})
        widths = widths_electronvolt(manifest, axis)
        self.assertEqual(len(set(widths.tolist())), 1)


class TheCountsAreConserved(unittest.TestCase):
    # Every column sums to one, so the total is a reordering of the same
    # products and the difference is float64 summation over the grid. The
    # relative error of a pairwise sum over n terms is bounded by about
    # log2(n) times the machine epsilon, which is under 1e-14 for the grids
    # here. A tolerance of 1e-12 sits above that and still sees a column that
    # was not normalised, which loses a percent or more.
    TOLERANCE = 1e-12

    def test_the_time_of_flight_form_conserves_them(self) -> None:
        before = a_spectrogram()
        after = apply_response(before)
        self.assertAlmostEqual(
            after.total_counts() / before.total_counts(), 1.0, delta=self.TOLERANCE
        )

    def test_the_constant_width_form_conserves_them(self) -> None:
        manifest = a_manifest({RESPONSE_FORM: CONSTANT_WIDTH, ENERGY_WIDTH: 1.0})
        before = a_spectrogram(manifest=manifest)
        after = apply_response(before)
        self.assertAlmostEqual(
            after.total_counts() / before.total_counts(), 1.0, delta=self.TOLERANCE
        )

    def test_a_line_is_conserved_as_well_as_a_flat_field(self) -> None:
        # A flat field is the case a mistake in the normalisation is most likely
        # to survive, because every column contributes the same total. A single
        # line puts all the counts in one column.
        axis = energy_axis()
        counts = np.zeros((axis.size, DELAYS))
        counts[axis.size // 2, :] = 1000.0
        before = Spectrogram.of(
            counts=counts,
            energy_axis_electronvolt=axis,
            delay_axis_attosecond=np.linspace(-200.0, 200.0, DELAYS),
            manifest=a_manifest(),
        )
        after = apply_response(before)
        self.assertAlmostEqual(
            after.total_counts() / before.total_counts(), 1.0, delta=self.TOLERANCE
        )

    def test_the_response_returns_a_spectrogram_on_the_same_grid(self) -> None:
        before = a_spectrogram()
        after = apply_response(before)
        self.assertIsInstance(after, Spectrogram)
        np.testing.assert_array_equal(
            after.energy_axis_electronvolt, before.energy_axis_electronvolt
        )
        np.testing.assert_array_equal(
            after.delay_axis_attosecond, before.delay_axis_attosecond
        )
        self.assertIs(after.manifest, before.manifest)


class ASingleKernelIsNotTheSameThing(unittest.TestCase):
    """The reason the expensive implementation exists, recorded rather than remembered."""

    def test_the_two_differ_by_more_than_a_rounding(self) -> None:
        # The width at the top of the axis is HIGH/LOW times the width at the
        # bottom, so a kernel built at the bottom under-blurs the top by that
        # factor. A line placed at the top therefore comes out of the two
        # implementations at visibly different widths, and the assertion is a
        # lower bound so that the test fails if they ever stop differing.
        #
        # The bound is derived rather than read off a run. Two normalised
        # Gaussians of widths s and 3s, sampled on the same grid, differ at
        # their peak by 1 - 1/3 of the taller one's peak height. A tenth of the
        # peak is far under that and far above any rounding.
        axis = energy_axis()
        counts = np.zeros((axis.size, DELAYS))
        line = int(axis.size * 0.9)
        counts[line, :] = 1000.0
        before = Spectrogram.of(
            counts=counts,
            energy_axis_electronvolt=axis,
            delay_axis_attosecond=np.linspace(-200.0, 200.0, DELAYS),
            manifest=a_manifest(),
        )

        correct = apply_response(before)
        cheap = single_kernel_response(before, LOW_ELECTRONVOLT)

        peak = float(correct.counts.max())
        difference = float(np.abs(correct.counts - cheap.counts).max())
        self.assertGreater(difference, 0.1 * peak)

    def test_they_agree_where_the_kernel_was_built(self) -> None:
        # The other half of the same statement. A single kernel is not wrong
        # everywhere, it is right at one energy, which is why it survives being
        # looked at.
        axis = energy_axis()
        matrix = response_matrix(a_manifest(), axis)
        reference = int(axis.size // 2)
        cheap_width = float(widths_electronvolt(a_manifest(), axis)[reference])
        self.assertAlmostEqual(
            applied_width(matrix, axis, reference) / cheap_width, 1.0, delta=1e-9
        )

    def test_the_cheap_one_under_blurs_the_top_of_the_range(self) -> None:
        # Which direction the mistake goes, because it is the direction that
        # matters to this board: less blurring is less overlap between the 2s
        # line and the satellites, and less overlap is a smaller contamination
        # than the instrument would actually produce.
        axis = energy_axis()
        counts = np.zeros((axis.size, DELAYS))
        line = int(axis.size * 0.9)
        counts[line, :] = 1000.0
        before = Spectrogram.of(
            counts=counts,
            energy_axis_electronvolt=axis,
            delay_axis_attosecond=np.linspace(-200.0, 200.0, DELAYS),
            manifest=a_manifest(),
        )
        correct = apply_response(before)
        cheap = single_kernel_response(before, LOW_ELECTRONVOLT)
        self.assertGreater(float(cheap.counts.max()), float(correct.counts.max()))


class AGridTooCoarseForTheResponseIsRefused(unittest.TestCase):
    def coarse_axis(self, points_per_width: float) -> NDArray[np.float64]:
        narrowest = 2.0 * RELATIVE * LOW_ELECTRONVOLT
        spacing = narrowest / points_per_width
        count = int(round((HIGH_ELECTRONVOLT - LOW_ELECTRONVOLT) / spacing)) + 1
        return np.linspace(LOW_ELECTRONVOLT, HIGH_ELECTRONVOLT, count)

    def test_a_grid_below_the_threshold_is_refused(self) -> None:
        with self.assertRaises(ResponseRefused) as refusal:
            response_matrix(a_manifest(), self.coarse_axis(1.0))
        self.assertIn("points per width", str(refusal.exception))

    def test_a_grid_above_the_threshold_is_accepted(self) -> None:
        # The neighbour, one step the other side of the same threshold.
        matrix = response_matrix(a_manifest(), self.coarse_axis(2.5))
        self.assertEqual(matrix.shape[0], matrix.shape[1])

    def test_the_refusal_says_what_spacing_would_work(self) -> None:
        with self.assertRaises(ResponseRefused) as refusal:
            response_matrix(a_manifest(), self.coarse_axis(1.0))
        # The message says what to do and not only what is wrong, which is the
        # shape the refusal in pulse.py already uses.
        self.assertIn("finer carries this response", str(refusal.exception))
        self.assertIn("0.5 eV", str(refusal.exception))


if __name__ == "__main__":
    unittest.main()
