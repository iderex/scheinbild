"""The trace follows the potential, the delay moves it, and nothing falls off the grid.

Four properties, and each of them is a way this map could be wrong while looking
like a streaking trace.

The centre of energy against delay is what the standard analysis reads. If it
does not follow the vector potential, everything downstream is fitting a curve
this model invented. That case is written twice here: once exactly, against the
intensity weighted mean of the energies the map produced, which is a statement
about the deposition, and once against the closed form shift at the centre of
the ionising pulse, which is a statement about the physics and carries a bound
derived from how long that pulse is.

The intrinsic delay is the quantity this whole board exists to put in and get
back out. A map that took it and moved the trace by something other than that
amount would be a model whose true answer is not the number the operator wrote
down, and every later comparison would be against the wrong value.

A trace that runs off the end of its energy grid is the case with no symptom.
The deposition extrapolates past the end and keeps the total and the centre of
energy right while doing it, so neither of the numbers this model is read
through says anything is wrong. That is why the grid check is asserted directly,
at one bin either side of the span the map itself reports, rather than through a
total that would have looked the same.
"""

import unittest
from math import sqrt

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest
from scheinbild_model.pulse import CENTRAL_ENERGY, CHIRP, TIME_GRID_HALF_WIDTH, Pulse
from scheinbild_model.pulse import DURATION as PULSE_DURATION
from scheinbild_model.streaking_field import (
    CARRIER_ENVELOPE_PHASE,
    PEAK_INTENSITY,
    PHOTON_ENERGY,
    StreakingField,
)
from scheinbild_model.streaking_field import DURATION as FIELD_DURATION
from scheinbild_model.streaking_map import (
    BIRTH_TIME_POINTS,
    INTRINSIC_DELAY,
    Line,
    StreakingMapRefused,
    centre_of_energy_electronvolt,
    energy_span_electronvolt,
    parameter_name,
    trace,
    unstreaked_energy_electronvolt,
)
from scheinbild_model.units import electronvolts_to_hartree, hartree_to_electronvolts

# A case to compute against, not a frozen parameter set. An ionising pulse of
# 90 eV and 150 as, and an infrared streaking pulse of 1.55 eV, five
# femtoseconds and 1e12 W/cm^2, which is where streaking is done.
_PHOTON_ELECTRONVOLT = 90.0
_IONISING_DURATION_ATTOSECOND = 150.0
_IONISING_HALF_WIDTH_ATTOSECOND = 400.0
_CARRIER_ELECTRONVOLT = 1.55
_STREAKING_DURATION_ATTOSECOND = 5000.0
_STREAKING_INTENSITY = 1e12

# The neon 2p binding energy, near enough for a case. The value the model reads
# comes from the data file with its source; this is a number to compute with.
_BINDING_ENERGY_ELECTRONVOLT = 21.56

_LINE = "2p"

# The birth time grid, and the delay scan. Both are chosen so that every time
# the map adds together is a whole number of attoseconds: the half width is 400
# and the step is 4, the scan runs in steps of 60, and the intrinsic delay below
# is 100. Whole numbers of that size are exact in binary, which is what lets the
# delay case assert an exact equality rather than a close one. The property does
# not depend on that; the sharpness of the assertion does.
_BIRTH_TIME_POINTS = 201
_DELAY_FIRST_ATTOSECOND = -1200.0
_DELAY_STEP_ATTOSECOND = 60.0
_DELAY_POINTS = 41
_INTRINSIC_DELAY_ATTOSECOND = 100.0

# Points on the energy axis, over whatever span the case needs. Fine enough that
# the trace at one delay covers many bins, which is what the deposition is worth
# having for.
_ENERGY_POINTS = 601

# An ionising pulse long compared with one cycle of the streaking carrier, which
# is about 2670 as. Not a pulse anybody streaks with. It is the case that makes
# the bound below mean something, because a pulse that samples a large part of a
# cycle averages the potential over it rather than reading it at one moment.
_LONG_IONISING_DURATION_ATTOSECOND = 1500.0
_LONG_IONISING_HALF_WIDTH_ATTOSECOND = 3600.0

# What the centre of energy may depart from the closed form shift by, as a
# fraction of the peak shift. Derived rather than tried. The centre of energy is
# the intensity weighted mean of the shift over the birth times, so expanding
# the shift about the middle of the pulse leaves a second order term of
# (1/2) w^2 s^2 times the shift, where w is the carrier angular frequency and s
# is the standard deviation of the intensity envelope. A 150 as intensity full
# width at half maximum is s = 150 / 2.3548 = 63.7 as, and a 1.55 eV carrier is
# w = 2 pi / 2670 as = 2.353e-03 per as, so (1/2) w^2 s^2 = 1.12e-02. The bound
# is that with a third of it again for the fourth order term and for the
# streaking envelope moving across the birth window. What the case measures is
# 6.25e-02 eV against a peak shift of 5.5998 eV, which is 1.117e-02 of it, so
# the derivation and the measurement agree to three figures.
_TRACKING_BOUND = 1.5e-2

# What the deposition may move the first moment by. Splitting a weight linearly
# between two grid points conserves the total and the first moment in exact
# arithmetic, so this is what the summation costs over the number of points
# involved and nothing more. In electronvolts, against energies of order 70.
_FIRST_MOMENT_TOLERANCE = 1e-9

# How far the intensity envelope of the potential has to have fallen before the
# streaking field counts as gone. Its square root is what the amplitude has
# fallen to, so at this fraction the shift left is one part in a hundred million
# of the peak shift, which is far below anything this model resolves and far
# above the last place of a float.
_GONE_FRACTION = 1e-16

# What the total counts in one delay column may differ from the line's relative
# strength by, relatively. Same reason: the split conserves the total exactly
# and this is the summation.
_TOTAL_TOLERANCE = 1e-12


def _parameters(**overrides: object) -> dict[str, object]:
    parameters: dict[str, object] = {
        CENTRAL_ENERGY: _PHOTON_ELECTRONVOLT,
        PULSE_DURATION: _IONISING_DURATION_ATTOSECOND,
        CHIRP: 0.0,
        TIME_GRID_HALF_WIDTH: _IONISING_HALF_WIDTH_ATTOSECOND,
        PHOTON_ENERGY: _CARRIER_ELECTRONVOLT,
        FIELD_DURATION: _STREAKING_DURATION_ATTOSECOND,
        CARRIER_ENVELOPE_PHASE: 0.0,
        PEAK_INTENSITY: _STREAKING_INTENSITY,
        BIRTH_TIME_POINTS: _BIRTH_TIME_POINTS,
        parameter_name(_LINE, INTRINSIC_DELAY): 0.0,
    }
    parameters.update(overrides)
    return parameters


def _manifest(**overrides: object) -> Manifest:
    # The overrides are of whatever type the case wants, because a value of the
    # wrong type is one of the things the map refuses. The suppression is on the
    # construction and names one code.
    return Manifest.of(
        parameters=_parameters(**overrides),  # type: ignore[arg-type]
        seeds={},
        code_version="a version for this test",
    )


def _line(
    manifest: Manifest,
    binding_energy: float = _BINDING_ENERGY_ELECTRONVOLT,
    strength: float = 1.0,
) -> Line:
    """The case's line. Its two atomic numbers are arguments, as they are in use.

    In a run they come out of the data file `atomic_data` loads. Here they are
    written down, because what is being proved is the map and not the file.
    """
    return Line.of(manifest, _LINE, binding_energy, strength)


def _delays(first: float = _DELAY_FIRST_ATTOSECOND) -> NDArray[np.float64]:
    return np.array(
        [first + index * _DELAY_STEP_ATTOSECOND for index in range(_DELAY_POINTS)],
        dtype=np.float64,
    )


def _axis_over(
    manifest: Manifest, line: Line, delays: NDArray[np.float64], points: int
) -> NDArray[np.float64]:
    """An energy axis spanning exactly what this line reaches over this scan."""
    lowest, highest = energy_span_electronvolt(manifest, line, delays)
    return np.linspace(lowest, highest, points, dtype=np.float64)


def _peak_shift_electronvolt(manifest: Manifest, line: Line) -> float:
    """The size of the largest shift this field gives this line, in electronvolts.

    At a carrier envelope phase of zero the crest of the carrier sits on the peak
    of the envelope, so the shift at time zero is the largest the field produces.
    """
    field = StreakingField(manifest)
    unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
    return abs(field.energy_shift_electronvolt(unstreaked, 0.0))


def _envelope_weights(
    manifest: Manifest,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """The birth times and the normalised intensity weight at each of them.

    Built here the way the map builds them, because the exact case below is a
    statement about what the deposition did with these weights rather than about
    where they came from.
    """
    pulse = Pulse(manifest)
    half_width = pulse.time_grid_half_width_attosecond
    births = np.linspace(-half_width, half_width, _BIRTH_TIME_POINTS, dtype=np.float64)
    envelope = np.array(
        [pulse.intensity_envelope(birth) for birth in births.tolist()],
        dtype=np.float64,
    )
    return births, envelope / envelope.sum()


class TheLineIsRefusedWhereItCouldNotBeALine(unittest.TestCase):
    def test_a_good_manifest_gives_a_line(self) -> None:
        # The control, without which every refusal below would also pass against
        # a constructor that refused everything.
        line = _line(_manifest())
        self.assertEqual(line.binding_energy_electronvolt, _BINDING_ENERGY_ELECTRONVOLT)

    def test_a_negative_binding_energy_is_refused(self) -> None:
        with self.assertRaises(StreakingMapRefused):
            _line(_manifest(), binding_energy=-1.0)

    def test_a_strength_of_zero_is_refused(self) -> None:
        with self.assertRaises(StreakingMapRefused):
            _line(_manifest(), strength=0.0)

    def test_a_negative_strength_is_refused(self) -> None:
        with self.assertRaises(StreakingMapRefused):
            _line(_manifest(), strength=-0.5)

    def test_a_delay_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(StreakingMapRefused):
            _line(_manifest(**{parameter_name(_LINE, INTRINSIC_DELAY): "0.0"}))

    def test_a_negative_intrinsic_delay_is_not_refused(self) -> None:
        # Deliberate. A line emitting before the one it is measured against is
        # the case this board exists to be able to represent.
        line = _line(_manifest(**{parameter_name(_LINE, INTRINSIC_DELAY): -50.0}))
        self.assertEqual(line.intrinsic_delay_attosecond, -50.0)

    def test_a_line_the_photon_cannot_ionise_is_refused(self) -> None:
        manifest = _manifest()
        with self.assertRaises(StreakingMapRefused):
            unstreaked_energy_electronvolt(
                Pulse(manifest),
                _line(manifest, binding_energy=_PHOTON_ELECTRONVOLT + 1.0),
            )

    def test_too_few_birth_times_are_refused(self) -> None:
        manifest = _manifest(**{BIRTH_TIME_POINTS: 1})
        with self.assertRaises(StreakingMapRefused):
            trace(
                manifest,
                _line(manifest),
                _axis_over(_manifest(), _line(_manifest()), _delays(), 11),
                _delays(),
            )

    def test_a_birth_time_count_that_is_not_a_whole_number_is_refused(self) -> None:
        manifest = _manifest(**{BIRTH_TIME_POINTS: 201.0})
        with self.assertRaises(StreakingMapRefused):
            trace(
                manifest,
                _line(manifest),
                _axis_over(_manifest(), _line(_manifest()), _delays(), 11),
                _delays(),
            )


class TheTraceSitsWhereTheLineIs(unittest.TestCase):
    def test_far_outside_the_streaking_pulse_the_line_is_unstreaked(self) -> None:
        # With the potential gone, the trace sits at the photon energy less the
        # binding energy. This is the case that catches a binding energy applied
        # with the wrong sign, which every streaking property below would pass.
        #
        # "Gone" is a fraction of the peak and not a word. The scan starts far
        # enough out that the intensity envelope of the potential has fallen to
        # the fraction below at the earliest birth time of the first delay step,
        # so the amplitude has fallen to its square root and the shift left is
        # at most that fraction of the peak shift.
        manifest = _manifest()
        line = _line(manifest)
        field = StreakingField(manifest)
        unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
        far = (
            field.time_the_envelope_has_fallen_to_attosecond(_GONE_FRACTION)
            + _IONISING_HALF_WIDTH_ATTOSECOND
        )
        bound = (
            _peak_shift_electronvolt(manifest, line) * sqrt(_GONE_FRACTION)
            + _FIRST_MOMENT_TOLERANCE
        )
        delays = np.array(
            [far + index * _DELAY_STEP_ATTOSECOND for index in range(3)],
            dtype=np.float64,
        )
        axis = _axis_over(_manifest(), line, _delays(), _ENERGY_POINTS)
        centre = centre_of_energy_electronvolt(trace(manifest, line, axis, delays))
        for value in centre.tolist():
            self.assertAlmostEqual(value, unstreaked, delta=bound)


class TheCentreOfEnergyIsWhatTheMapPutThere(unittest.TestCase):
    """The deposition, exactly, before anything is said about the physics."""

    def test_the_centre_is_the_intensity_weighted_mean_of_the_mapped_energies(
        self,
    ) -> None:
        manifest = _manifest()
        line = _line(manifest)
        field = StreakingField(manifest)
        unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)

        births, weights = _envelope_weights(manifest)
        centre = centre_of_energy_electronvolt(trace(manifest, line, axis, delays))

        for index, delay in enumerate(delays.tolist()):
            with self.subTest(delay=delay):
                expected = unstreaked + sum(
                    weight * field.energy_shift_electronvolt(unstreaked, delay + birth)
                    for birth, weight in zip(births.tolist(), weights.tolist())
                )
                self.assertAlmostEqual(
                    float(centre[index]), expected, delta=_FIRST_MOMENT_TOLERANCE
                )


class TheCentreOfEnergyFollowsThePotential(unittest.TestCase):
    """The physics, with the bound the ionising pulse's own length imposes."""

    def _departure(self, manifest: Manifest) -> float:
        line = _line(manifest)
        field = StreakingField(manifest)
        unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        centre = centre_of_energy_electronvolt(trace(manifest, line, axis, delays))
        closed = np.array(
            [
                unstreaked + field.energy_shift_electronvolt(unstreaked, delay)
                for delay in delays.tolist()
            ],
            dtype=np.float64,
        )
        return float(np.max(np.abs(centre - closed)))

    def test_the_centre_traces_the_shift_the_field_gives_at_that_delay(self) -> None:
        manifest = _manifest()
        peak = _peak_shift_electronvolt(manifest, _line(manifest))
        self.assertLess(
            self._departure(manifest),
            _TRACKING_BOUND * peak,
            "The centre of energy does not follow the vector potential.",
        )

    def test_an_ionising_pulse_of_a_cycle_misses_that_bound(self) -> None:
        # The near miss, and it is the one somebody would actually produce: a
        # longer ionising pulse averages the potential over a large part of a
        # cycle instead of reading it at one moment, and the trace it leaves is
        # a washed out version of the curve rather than the curve.
        manifest = _manifest(
            **{
                PULSE_DURATION: _LONG_IONISING_DURATION_ATTOSECOND,
                TIME_GRID_HALF_WIDTH: _LONG_IONISING_HALF_WIDTH_ATTOSECOND,
            }
        )
        peak = _peak_shift_electronvolt(manifest, _line(manifest))
        self.assertGreater(
            self._departure(manifest),
            _TRACKING_BOUND * peak,
            "The near miss no longer misses, so the case above proves nothing.",
        )

    def test_the_excursion_is_the_size_the_closed_form_gives(self) -> None:
        # A streaking amplitude wrong by a factor moves every delay this board
        # extracts, and a trace of the right shape and the wrong size would pass
        # the tracking case above at a looser bound. The peak shift is the
        # momentum times the potential plus the potential squared over two, and
        # the model's own field is asked for the potential rather than this test
        # rebuilding it.
        manifest = _manifest()
        line = _line(manifest)
        field = StreakingField(manifest)
        unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
        momentum = sqrt(2.0 * electronvolts_to_hartree(unstreaked))
        potential = field.peak_vector_potential
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        centre = centre_of_energy_electronvolt(trace(manifest, line, axis, delays))
        excursion = unstreaked - float(np.min(centre))
        closed = hartree_to_electronvolts(
            momentum * potential - potential * potential / 2.0
        )
        self.assertAlmostEqual(excursion / closed, 1.0, delta=_TRACKING_BOUND)


class TheIntrinsicDelayMovesTheTrace(unittest.TestCase):
    """The quantity the operator puts in, and the amount the trace moves by."""

    def _trace(self, delay: float, first: float) -> NDArray[np.float64]:
        manifest = _manifest(**{parameter_name(_LINE, INTRINSIC_DELAY): delay})
        line = _line(manifest)
        delays = _delays(first)
        axis = _axis_over(_manifest(), _line(_manifest()), _delays(), 601)
        return trace(manifest, line, axis, delays).counts

    def test_a_delayed_line_gives_the_same_trace_at_an_earlier_delay(self) -> None:
        # An electron of a line with intrinsic delay d, born at t, samples the
        # field at delay + t + d. So the trace of a delayed line at a delay is
        # the trace of the undelayed one at that delay plus d, and the equality
        # is exact rather than close because every time added here is a whole
        # number of attoseconds of a size that is exact in binary.
        undelayed = self._trace(0.0, _DELAY_FIRST_ATTOSECOND)
        delayed = self._trace(
            _INTRINSIC_DELAY_ATTOSECOND,
            _DELAY_FIRST_ATTOSECOND - _INTRINSIC_DELAY_ATTOSECOND,
        )
        self.assertTrue(
            np.array_equal(delayed, undelayed),
            "The intrinsic delay moved the trace by something other than itself.",
        )

    def test_a_delay_of_nothing_moves_nothing(self) -> None:
        # Without this the case above would also pass against a map that ignored
        # the intrinsic delay entirely, because both sides would be the same
        # trace on two axes that are compared position by position.
        undelayed = self._trace(0.0, _DELAY_FIRST_ATTOSECOND)
        moved = self._trace(0.0, _DELAY_FIRST_ATTOSECOND - _INTRINSIC_DELAY_ATTOSECOND)
        self.assertFalse(
            np.array_equal(moved, undelayed),
            "Two different delay scans gave the same trace, so the comparison "
            "above is not sensitive to the axis it is read on.",
        )


class TheCountsSurviveTheScan(unittest.TestCase):
    def test_every_delay_step_carries_the_line_s_whole_strength(self) -> None:
        # The trace is the same electrons at every delay step, moved in energy,
        # so a column that carries fewer counts than another is a column that
        # lost some in the moving. It is a property of the deposition rather
        # than of the grid check: an axis too narrow keeps these totals right,
        # which is what the cases below are asserted directly for.
        strength = 0.37
        manifest = _manifest()
        line = _line(manifest, strength=strength)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        produced = trace(manifest, line, axis, delays)
        for index, total in enumerate(produced.counts.sum(axis=0).tolist()):
            with self.subTest(delay=float(delays[index])):
                self.assertAlmostEqual(total / strength, 1.0, delta=_TOTAL_TOLERANCE)


class AGridThatClipsIsRefused(unittest.TestCase):
    def test_an_axis_spanning_exactly_what_the_line_reaches_is_accepted(self) -> None:
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        self.assertGreater(trace(manifest, line, axis, delays).total_counts(), 0.0)

    def test_an_axis_one_bin_short_at_the_bottom_is_refused(self) -> None:
        # The tightest miss this grid admits. The axis above holds the trace
        # with nothing to spare, so moving its lower end up by one bin is the
        # smallest change that loses a count.
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        lowest, highest = energy_span_electronvolt(manifest, line, delays)
        spacing = (highest - lowest) / (_ENERGY_POINTS - 1)
        short = np.linspace(
            lowest + spacing, highest, _ENERGY_POINTS - 1, dtype=np.float64
        )
        with self.assertRaises(StreakingMapRefused):
            trace(manifest, line, short, delays)

    def test_an_axis_one_bin_short_at_the_top_is_refused(self) -> None:
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        lowest, highest = energy_span_electronvolt(manifest, line, delays)
        spacing = (highest - lowest) / (_ENERGY_POINTS - 1)
        short = np.linspace(
            lowest, highest - spacing, _ENERGY_POINTS - 1, dtype=np.float64
        )
        with self.assertRaises(StreakingMapRefused):
            trace(manifest, line, short, delays)

    def test_the_grid_that_held_one_intensity_is_refused_at_four_times_it(self) -> None:
        # The mistake somebody makes: the streaking intensity goes up and the
        # energy grid stays where it was. Four times the intensity is twice the
        # field, so twice the excursion, and the axis that held the first one
        # holds half of the second.
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        brighter = _manifest(**{PEAK_INTENSITY: 4.0 * _STREAKING_INTENSITY})
        with self.assertRaises(StreakingMapRefused):
            trace(brighter, _line(brighter), axis, delays)

    def test_the_refusal_names_the_span_that_would_hold_the_line(self) -> None:
        # A refusal that said only that the grid was wrong would leave the
        # reader to find the right one by trying. The two numbers it names are
        # the ones `energy_span_electronvolt` answers with, so the message and
        # the function cannot drift apart.
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        brighter = _manifest(**{PEAK_INTENSITY: 4.0 * _STREAKING_INTENSITY})
        brighter_line = _line(brighter)
        lowest, highest = energy_span_electronvolt(brighter, brighter_line, delays)
        with self.assertRaises(StreakingMapRefused) as refused:
            trace(brighter, brighter_line, axis, delays)
        self.assertIn(str(lowest), str(refused.exception))
        self.assertIn(str(highest), str(refused.exception))


class ACentreOfEnergyNeedsCounts(unittest.TestCase):
    def test_a_delay_step_with_nothing_in_it_is_refused(self) -> None:
        manifest = _manifest()
        line = _line(manifest)
        delays = _delays()
        axis = _axis_over(manifest, line, delays, _ENERGY_POINTS)
        produced = trace(manifest, line, axis, delays)
        produced.counts[:, 0] = 0.0
        with self.assertRaises(StreakingMapRefused):
            centre_of_energy_electronvolt(produced)


if __name__ == "__main__":
    unittest.main()
