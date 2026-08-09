"""The potential returns to zero, the field is its derivative, and the sign holds.

Three properties, and each of them is a way this model could be wrong while
looking entirely reasonable.

A potential that does not return to zero after the pulse says the pulse left a
constant momentum behind it. Nothing in a spectrogram would announce that; it
would arrive as a drift along the delay axis, which is the axis the extracted
delay is read off. The test for it is not a check that the envelope is small at
the ends, which is arithmetic about a Gaussian. It is that the field integrates
to zero over the whole pulse, which is what the potential returning to zero MEANS
and is the property the other convention fails.

That near miss is written out here and measured rather than described, and the
measurement says something the module's own argument does not: for a pulse of
many cycles a directly written Gaussian field leaves a residual that is
exponentially small, so the two conventions agree and the choice costs nothing.
It is at a sub-cycle duration that they part, and that is where the case below
puts them, on one pulse, with one convention passing the bound and the other
missing it by orders of magnitude.

A sign error inverts the direction of every extracted delay and leaves a result
that is internally consistent and backwards. The case for it is written in words
first and in numbers second, so that a reader disagreeing with the convention
disagrees with a sentence rather than with a minus.

A peak energy shift that does not match the closed form means the intensity, the
frequency or the conversion between them is wrong by a factor, and a streaking
amplitude wrong by a factor moves every delay this board extracts.
"""

import unittest
from math import cos, exp, log, pi, sqrt

from scheinbild_model.manifest import Manifest
from scheinbild_model.streaking_field import (
    CARRIER_ENVELOPE_PHASE,
    DURATION,
    PEAK_INTENSITY,
    PHOTON_ENERGY,
    StreakingField,
    StreakingFieldRefused,
)
from scheinbild_model.units import (
    atomic_time_to_attoseconds,
    attoseconds_to_atomic_time,
    electronvolts_to_hartree,
    hartree_to_electronvolts,
    peak_intensity_to_atomic_field,
)

# A streaking pulse of the kind this board is about: an infrared carrier of
# 1.55 eV, which is roughly 800 nm, five femtoseconds long, at a peak intensity
# where streaking is done. None of these is a frozen value; they are a case to
# compute against.
_CARRIER_ELECTRONVOLT = 1.55
_DURATION_ATTOSECOND = 5000.0
_PEAK_INTENSITY = 1e12

# A pulse shorter than one cycle of that carrier, which is about 2670 as. Not a
# pulse anybody streaks with. It is the duration at which the two conventions
# stop agreeing, and the near miss below needs a case where they do.
_SUB_CYCLE_DURATION_ATTOSECOND = 800.0

# The kinetic energy the closed form cases are computed at. About what a neon 2p
# electron leaves with at the photon energy this board works at.
_KINETIC_ENERGY_ELECTRONVOLT = 85.0

# How far out a pulse is followed when the field is integrated. The intensity
# envelope of the potential has fallen to this fraction of its peak there, so its
# amplitude envelope has fallen to the square root of it, which is one part in
# ten thousand.
_EDGE_INTENSITY_FRACTION = 1e-8

# Points per optical cycle in that integration. A trapezoid rule has an error
# that falls as the square of the step, so a step this fine is what makes the
# residual a statement about the field rather than about the quadrature.
_POINTS_PER_CYCLE = 64

# What the integral of the field over the whole pulse may be, as a fraction of
# the peak of the potential. The integral IS the potential at one end minus the
# potential at the other, so the largest value the shape allows is twice the
# amplitude envelope at the edge, which the fraction above puts at 1e-4 of the
# peak. This bound is a factor of ten above that.
_RESIDUAL_BOUND = 1e-3

# The relative tolerance the closed form comparisons are held to. The quantities
# compared are equal in exact arithmetic, so this is a few times what double
# precision costs over the handful of operations involved and nothing more.
# Anything looser would be admitting a modelling error rather than a rounding one.
_CLOSED_FORM_TOLERANCE = 1e-12

# What the numerical derivative below may differ from the closed form one by, as
# a fraction of the peak field. A central difference has a truncation error of
# about the step squared over six times the third derivative, and against a peak
# field of A times the frequency that is the step squared times the frequency
# squared over six. With the step at one part in 4096 of a cycle that is about
# 4e-07, so this bound sits a factor of twenty above it and is derived rather
# than tried.
_DERIVATIVE_TOLERANCE = 1e-5


def _manifest(**overrides: object) -> Manifest:
    parameters: dict[str, object] = {
        PHOTON_ENERGY: _CARRIER_ELECTRONVOLT,
        DURATION: _DURATION_ATTOSECOND,
        CARRIER_ENVELOPE_PHASE: 0.0,
        PEAK_INTENSITY: _PEAK_INTENSITY,
    }
    parameters.update(overrides)
    # The overrides are of whatever type the case wants, because a value of the
    # wrong type is one of the things the field refuses. The suppression is on
    # the construction and names one code.
    return Manifest.of(
        parameters=parameters,  # type: ignore[arg-type]
        seeds={},
        code_version="a version for this test",
    )


def _cycle_attosecond(field: StreakingField) -> float:
    """One optical cycle of the carrier, in attoseconds."""
    frequency = electronvolts_to_hartree(field.photon_energy_electronvolt)
    return atomic_time_to_attoseconds(2.0 * pi / frequency)


def _grid(field: StreakingField) -> list[float]:
    """A time grid holding the whole of one pulse, fine enough for a trapezoid."""
    edge = field.time_the_envelope_has_fallen_to_attosecond(_EDGE_INTENSITY_FRACTION)
    step = _cycle_attosecond(field) / _POINTS_PER_CYCLE
    count = int(2.0 * edge / step)
    return [-edge + index * step for index in range(count + 1)]


def _integral(values: list[float], step: float) -> float:
    """The trapezoid rule, over values on an evenly spaced grid."""
    return step * (sum(values[1:-1]) + 0.5 * (values[0] + values[-1]))


def _residual_in_atomic_units(values: list[float], grid: list[float]) -> float:
    """The integral of a field sampled in attoseconds, in atomic units.

    The values are a field in atomic units and the grid is in attoseconds, so
    the product carries one attosecond and the conversion turns it into one
    atomic unit of time. That leaves a quantity in the same units as a vector
    potential, which is what it is compared against.
    """
    return attoseconds_to_atomic_time(_integral(values, grid[1] - grid[0]))


class TheFieldIsRefusedWhereItWouldNotBeAField(unittest.TestCase):
    def test_a_good_manifest_builds(self) -> None:
        # The control, without which every refusal below would also pass against
        # a class that refused everything.
        self.assertGreater(StreakingField(_manifest()).peak_vector_potential, 0.0)

    def test_a_photon_energy_of_zero_is_refused(self) -> None:
        with self.assertRaises(StreakingFieldRefused):
            StreakingField(_manifest(**{PHOTON_ENERGY: 0.0}))

    def test_a_negative_duration_is_refused(self) -> None:
        with self.assertRaises(StreakingFieldRefused):
            StreakingField(_manifest(**{DURATION: -1.0}))

    def test_an_intensity_of_zero_is_refused(self) -> None:
        with self.assertRaises(StreakingFieldRefused):
            StreakingField(_manifest(**{PEAK_INTENSITY: 0.0}))

    def test_a_parameter_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(StreakingFieldRefused):
            StreakingField(_manifest(**{PEAK_INTENSITY: "1e12"}))

    def test_a_negative_kinetic_energy_is_refused(self) -> None:
        with self.assertRaises(StreakingFieldRefused):
            StreakingField(_manifest()).energy_shift_electronvolt(-1.0, 0.0)

    def test_an_envelope_fraction_outside_zero_to_one_is_refused(self) -> None:
        field = StreakingField(_manifest())
        for fraction in (0.0, 1.0, -0.5, 2.0):
            with self.subTest(fraction=fraction):
                with self.assertRaises(StreakingFieldRefused):
                    field.time_the_envelope_has_fallen_to_attosecond(fraction)


def _written_down_directly(field: StreakingField, time_attosecond: float) -> float:
    """The other convention: the same shape, written as the field itself.

    A Gaussian envelope times a carrier, at the same peak field amplitude, the
    same duration and the same carrier as the pulse it is compared against. It
    is a perfectly reasonable looking field, and the potential it implies is
    whatever its integral turns out to be rather than something that was chosen.
    """
    duration = attoseconds_to_atomic_time(field.duration_attosecond)
    rate = 2.0 * log(2.0) / (duration * duration)
    frequency = electronvolts_to_hartree(field.photon_energy_electronvolt)
    time = attoseconds_to_atomic_time(time_attosecond)
    return field.peak_field_strength * exp(-rate * time * time) * cos(frequency * time)


class ThePotentialReturnsToZero(unittest.TestCase):
    """The property the whole convention exists for, and what it is worth."""

    def test_the_potential_has_gone_at_the_edge_of_the_pulse(self) -> None:
        field = StreakingField(_manifest())
        edge = field.time_the_envelope_has_fallen_to_attosecond(
            _EDGE_INTENSITY_FRACTION
        )
        # The amplitude envelope is the square root of the intensity envelope,
        # so this is the bound the fraction above buys and not a looser one.
        bound = field.peak_vector_potential * sqrt(_EDGE_INTENSITY_FRACTION)
        for time in (-edge, edge):
            with self.subTest(time=time):
                self.assertLessEqual(abs(field.vector_potential(time)), bound)

    def test_the_field_integrates_to_zero_over_the_whole_pulse(self) -> None:
        # This is what the potential returning to zero means. The integral of
        # the field over all time is the potential at one end minus the
        # potential at the other, so a field whose integral is not zero is a
        # pulse that left a constant momentum behind it.
        for duration in (_DURATION_ATTOSECOND, _SUB_CYCLE_DURATION_ATTOSECOND):
            with self.subTest(duration=duration):
                field = StreakingField(_manifest(**{DURATION: duration}))
                grid = _grid(field)
                residual = _residual_in_atomic_units(
                    [field.electric_field(t) for t in grid], grid
                )
                self.assertLess(
                    abs(residual),
                    _RESIDUAL_BOUND * field.peak_vector_potential,
                    "The streaking field does not integrate to zero over its "
                    "own pulse.",
                )

    def test_a_field_written_down_directly_misses_that_bound_below_a_cycle(
        self,
    ) -> None:
        # The near miss, on the same pulse the case above passes. Below one
        # cycle the two conventions are different pulses, and the one written as
        # a field leaves a potential that does not return to where it started.
        field = StreakingField(_manifest(**{DURATION: _SUB_CYCLE_DURATION_ATTOSECOND}))
        grid = _grid(field)
        residual = _residual_in_atomic_units(
            [_written_down_directly(field, t) for t in grid], grid
        )
        self.assertGreater(
            abs(residual),
            _RESIDUAL_BOUND * field.peak_vector_potential,
            "The near miss no longer misses, so the case above proves nothing.",
        )

    def test_the_same_field_at_many_cycles_would_have_passed(self) -> None:
        # The other half of the disclosure, and it is a limit on what the choice
        # buys rather than an argument for it. At the duration this board works
        # at, a directly written field leaves a residual far inside the bound,
        # so the two conventions agree there and the choice is insurance rather
        # than a repair.
        field = StreakingField(_manifest())
        grid = _grid(field)
        residual = _residual_in_atomic_units(
            [_written_down_directly(field, t) for t in grid], grid
        )
        self.assertLess(abs(residual), _RESIDUAL_BOUND * field.peak_vector_potential)


class TheFieldIsTheDerivativeOfThePotential(unittest.TestCase):
    """The closed form derivative, against a numerical one.

    A wrong derivative is the mistake that leaves the potential right and the
    field wrong, which every case above would pass.
    """

    def test_minus_the_slope_of_the_potential_is_the_field(self) -> None:
        field = StreakingField(_manifest())
        cycle = _cycle_attosecond(field)
        step = cycle / 4096.0
        for at in (-cycle, -0.25 * cycle, 0.0, 0.3 * cycle, 2.0 * cycle):
            with self.subTest(at=at):
                rise = field.vector_potential(at + step) - field.vector_potential(
                    at - step
                )
                slope = rise / (2.0 * attoseconds_to_atomic_time(step))
                self.assertAlmostEqual(
                    -slope / field.peak_field_strength,
                    field.electric_field(at) / field.peak_field_strength,
                    delta=_DERIVATIVE_TOLERANCE,
                )


class TheSignIsTheOneTheConventionStates(unittest.TestCase):
    def test_a_positive_potential_takes_momentum_away(self) -> None:
        # The sentence in the module docstring, as an assertion. An electron
        # born while the potential is positive comes out slower.
        field = StreakingField(_manifest())
        self.assertGreater(field.vector_potential(0.0), 0.0)
        self.assertLess(field.momentum_shift(0.0), 0.0)
        self.assertLess(
            field.energy_shift_electronvolt(_KINETIC_ENERGY_ELECTRONVOLT, 0.0), 0.0
        )

    def test_half_a_cycle_later_it_gives_momentum(self) -> None:
        field = StreakingField(_manifest())
        half = 0.5 * _cycle_attosecond(field)
        self.assertLess(field.vector_potential(half), 0.0)
        self.assertGreater(field.momentum_shift(half), 0.0)
        self.assertGreater(
            field.energy_shift_electronvolt(_KINETIC_ENERGY_ELECTRONVOLT, half), 0.0
        )


class ThePeakEnergyShiftMatchesTheClosedForm(unittest.TestCase):
    """The excursion a stated intensity produces, against the analytic value."""

    def test_the_peak_of_the_potential_is_the_field_over_the_frequency(self) -> None:
        field = StreakingField(_manifest())
        closed = peak_intensity_to_atomic_field(_PEAK_INTENSITY) / (
            electronvolts_to_hartree(_CARRIER_ELECTRONVOLT)
        )
        self.assertAlmostEqual(
            field.peak_vector_potential / closed, 1.0, delta=_CLOSED_FORM_TOLERANCE
        )

    def test_nothing_in_time_exceeds_that_peak(self) -> None:
        # Without this the case below would be a statement about one point
        # rather than about the peak. The sampling is at an awkward fraction of
        # a cycle so that it does not land on the crests and stay there.
        field = StreakingField(_manifest())
        cycle = _cycle_attosecond(field)
        largest = max(
            abs(field.vector_potential(index * cycle / 97.0))
            for index in range(-2000, 2001)
        )
        self.assertLessEqual(
            largest, field.peak_vector_potential * (1.0 + _CLOSED_FORM_TOLERANCE)
        )

    def test_the_shift_at_the_peak_is_the_closed_form(self) -> None:
        # At a carrier envelope phase of zero the crest of the carrier sits on
        # the peak of the envelope, so the potential there is exactly its own
        # peak and the closed form is exact rather than a many cycle limit.
        field = StreakingField(_manifest())
        momentum = sqrt(2.0 * electronvolts_to_hartree(_KINETIC_ENERGY_ELECTRONVOLT))
        potential = field.peak_vector_potential
        closed = hartree_to_electronvolts(
            -momentum * potential + potential * potential / 2.0
        )
        produced = field.energy_shift_electronvolt(_KINETIC_ENERGY_ELECTRONVOLT, 0.0)
        self.assertAlmostEqual(produced / closed, 1.0, delta=_CLOSED_FORM_TOLERANCE)

    def test_the_shift_scales_as_the_square_root_of_the_intensity(self) -> None:
        # The relation that catches a conversion applied as a factor rather than
        # as a square root. Four times the intensity is twice the field, so twice
        # the potential and, to the term that is linear in it, twice the shift.
        one = StreakingField(_manifest())
        four = StreakingField(_manifest(**{PEAK_INTENSITY: 4.0 * _PEAK_INTENSITY}))
        self.assertAlmostEqual(
            four.peak_vector_potential / one.peak_vector_potential,
            2.0,
            delta=_CLOSED_FORM_TOLERANCE,
        )


if __name__ == "__main__":
    unittest.main()
