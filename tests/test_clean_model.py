"""The clean model against the analytic streaking relation.

Before any contamination is added, the model is checked where the answer is
known in closed form. This is the last cheap moment to find a sign error, a
factor in the vector potential or a slip between units: once satellites, an
instrument response and counting statistics are in the picture, a discrepancy
has several places to have come from and no closed form to be compared against.

Three comparisons, over the two line spectrogram the model already assembles.

The centre of energy of a line against delay follows the vector potential scaled
by that line's central momentum. Both curves are computed over the same delay
axis and compared point by point.

The peak to peak energy excursion matches the closed form for the peak intensity
and the carrier this run chose. A trace of the right shape and the wrong size
would pass the first comparison at a looser bound, and an amplitude wrong by a
factor moves every delay this board later extracts.

The relative delay of the two lines, read off the phases of their oscillations,
is the difference that was injected. It is done here with a direct phase read
rather than through the standard analysis, and not only because that module does
not exist yet: a failure here is a failure of the model, a failure in the
analysis is a failure of the analysis, and keeping the two separable is worth
the small duplication.

## The tolerances, and where each of them comes from

The analytic relation is not what the model computes, and the difference is not
an error in either of them. The relation keeps the term that is linear in the
vector potential and evaluates it at one instant; the model carries the term
that goes as the square of the potential as well, and averages the whole shift
over the birth times inside the ionising pulse. So each tolerance below is the
size of what the relation drops, written as an expression rather than as a
number, and it moves when the case moves. Every one of them is derived first and
measured afterwards, and both are quoted where they are used.

## What is compared and what is only read

The lines are read out of the assembled spectrogram through an energy window,
because the whole clean model is what is under test rather than one trace of it.
The windows come from the map's own answer for how far each line reaches, and a
case below asserts that they hold every count there is, so a window that
truncated a line and biased its centre of energy would be caught here rather
than absorbed into a tolerance.
"""

import unittest
from math import atan2, cos, log, pi, sqrt

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.assembly import (
    DELAY_FIRST,
    DELAY_POINTS,
    DELAY_STEP,
    ENERGY_FIRST,
    ENERGY_POINTS,
    ENERGY_STEP,
    MINIMUM_CYCLES,
    NEON_MAIN_LINE_NAMES,
    delay_axis_attosecond,
    lines_of,
    neon_main_lines_spectrogram,
    streaking_period_attosecond,
)
from scheinbild_model.atomic_data import neon_main_lines
from scheinbild_model.manifest import Manifest
from scheinbild_model.pulse import CENTRAL_ENERGY, CHIRP, TIME_GRID_HALF_WIDTH, Pulse
from scheinbild_model.pulse import DURATION as PULSE_DURATION
from scheinbild_model.spectrogram import Spectrogram
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
    centre_of_energy_electronvolt,
    energy_span_electronvolt,
    parameter_name,
    unstreaked_energy_electronvolt,
)
from scheinbild_model.units import (
    electronvolts_to_hartree,
    hartree_to_electronvolts,
    peak_intensity_to_atomic_field,
)

# A case to compute against, not a frozen parameter set. An ionising pulse of
# 90 eV and 150 as, which is above the 80 eV first row of the shipped 2s cross
# section table, and an infrared streaking pulse of 1.55 eV at 1e12 W/cm^2.
_PHOTON_ELECTRONVOLT = 90.0
_IONISING_DURATION_ATTOSECOND = 150.0
_IONISING_HALF_WIDTH_ATTOSECOND = 400.0
_CARRIER_ELECTRONVOLT = 1.55
_STREAKING_INTENSITY = 1e12
_BIRTH_TIME_POINTS = 201

# A streaking pulse of twenty femtoseconds, which is longer than the five the
# other cases on this board use. The closed form for the peak to peak excursion
# is written for a field whose envelope does not move within one cycle, and the
# envelope of a five femtosecond pulse falls to 0.906 of its peak between a
# crest of the carrier and the trough beside it. That is not a small term
# standing beside the ones below; it is larger than all of them together, and it
# would be a property of the envelope being compared against a closed form that
# has no envelope in it.
_STREAKING_DURATION_ATTOSECOND = 20000.0

# The delay scan, in cycles of the carrier and samples per cycle rather than in
# attoseconds, because the phase read below wants the two to be exact.
#
# The delays run from minus one period to one period less one step, at a
# forty-eighth of a period each. That is a whole number of cycles of sample
# positions, so a sinusoid at the carrier and a sinusoid at twice the carrier
# are exactly orthogonal over this set. The term the analytic relation drops
# oscillates at twice the carrier, and this is what keeps it out of the phase.
_SCAN_CYCLES = 2
_SAMPLES_PER_CYCLE = 48
_MINIMUM_CYCLES = 1.9

# The energy grid, wide enough to hold both lines with their excursions. The 2s
# line sits near 41.5 eV and the 2p line near 68.4 eV at this photon energy, and
# each swings something under six electronvolts either way.
_ENERGY_FIRST_ELECTRONVOLT = 35.0
_ENERGY_STEP_ELECTRONVOLT = 0.02
_ENERGY_POINTS = 2051

# The intrinsic delays this run puts in. The 2p line is the reference and the 2s
# line is emitted 21 as after it, which is the difference the third comparison
# has to get back out.
_DELAY_2P_ATTOSECOND = 0.0
_DELAY_2S_ATTOSECOND = 21.0
_INJECTED_DIFFERENCE_ATTOSECOND = _DELAY_2S_ATTOSECOND - _DELAY_2P_ATTOSECOND

# A second injected difference, of the other sign, for the case that shows the
# phase read follows what was put in rather than answering with a constant.
_OTHER_DIFFERENCE_ATTOSECOND = -37.0

# What every derived bound below is multiplied by. Each derivation keeps the
# leading term of a departure and drops the next, so a fifth again stands in for
# what was not kept. It is written once here rather than folded into three
# numbers, so that a reader can see how much of each tolerance is derivation and
# how much is margin.
_BOUND_MARGIN = 1.2

# What the recovered relative delay may differ from the injected one by, in
# attoseconds. Derived, and the derivation is the one place a bound here is
# loose rather than tight.
#
# The phase read is exact for a sinusoid at the carrier sampled over a whole
# number of its cycles, which the scan above is. What is left is the term that
# goes as the square of the potential: it oscillates at twice the carrier, where
# the sampling makes it exactly orthogonal to the two the phase is read from, so
# it reaches the phase only through the field envelope varying across the scan.
# That envelope falls to 0.9756 of its peak at either end of this scan, the
# second order term is at most A/(4p) = 1.34e-02 of the linear one for the
# weaker momentum of the two lines, and one radian of carrier phase is
# T/(2 pi) = 424.7 as, so the bound is 2.44e-02 * 1.34e-02 * 424.7 = 0.139 as.
#
# What the case measures is 2.1e-05 as, four decades below the bound, because
# the leak also needs the scan's symmetry about the crest to be broken and 21 as
# out of a 2668 as period breaks it only slightly. The bound is the one that can
# be written down without assuming the injected delay is small.
_PHASE_TOLERANCE_ATTOSECOND = 0.15

# What the two windows may leave outside them, relatively. The deposition
# conserves each line's whole strength, so this is the summation over the grid
# and nothing else.
_WINDOW_TOLERANCE = 1e-12

# Radians in one turn. Geometry rather than a measurement.
_RADIANS_PER_TURN = 2.0 * pi

# What turns an intensity full width at half maximum into the standard deviation
# of the same Gaussian. Algebra of the chosen shape.
_FWHM_IN_STANDARD_DEVIATIONS = 2.0 * sqrt(2.0 * log(2.0))


def _parameters(period_attosecond: float, **overrides: object) -> dict[str, object]:
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
        DELAY_FIRST: -0.5 * _SCAN_CYCLES * period_attosecond,
        DELAY_STEP: period_attosecond / _SAMPLES_PER_CYCLE,
        DELAY_POINTS: _SCAN_CYCLES * _SAMPLES_PER_CYCLE,
        ENERGY_FIRST: _ENERGY_FIRST_ELECTRONVOLT,
        ENERGY_STEP: _ENERGY_STEP_ELECTRONVOLT,
        ENERGY_POINTS: _ENERGY_POINTS,
        MINIMUM_CYCLES: _MINIMUM_CYCLES,
        parameter_name("2p", INTRINSIC_DELAY): _DELAY_2P_ATTOSECOND,
        parameter_name("2s", INTRINSIC_DELAY): _DELAY_2S_ATTOSECOND,
    }
    parameters.update(overrides)
    return parameters


def _period_attosecond() -> float:
    """One cycle of this run's carrier, from the model's own answer.

    The scan is described in cycles, so the period has to be known before the
    delay parameters can be written down. The streaking field reads only its own
    four parameters, so a manifest whose delay axis is a placeholder is enough to
    ask, and asking is what keeps this file from working out a second period.
    """
    # The declared parameter type is narrower than the dictionary above, which
    # is built wide because a case overriding a value with one of the wrong type
    # is one of the things the model refuses. The suppression names one code.
    placeholder = Manifest.of(
        parameters=_parameters(1.0),  # type: ignore[arg-type]
        seeds={},
        code_version="a version for this test",
    )
    return streaking_period_attosecond(StreakingField(placeholder))


_PERIOD_ATTOSECOND = _period_attosecond()


def _manifest(**overrides: object) -> Manifest:
    # The overrides are of whatever type the case wants. The suppression is on
    # the construction and names one code.
    return Manifest.of(
        parameters=_parameters(_PERIOD_ATTOSECOND, **overrides),  # type: ignore[arg-type]
        seeds={},
        code_version="a version for this test",
    )


def _lines(manifest: Manifest) -> dict[str, Line]:
    """This run's lines, by name, as the assembler builds them."""
    built = lines_of(manifest, neon_main_lines(), NEON_MAIN_LINE_NAMES)
    return {line.name: line for line in built}


def _momentum_atomic(manifest: Manifest, line: Line) -> float:
    """The line's central momentum, in atomic units.

    The momentum an electron of this line carries before the streaking field
    touches it, which is what the analytic relation scales the vector potential
    by. A kinetic energy of K in atomic units belongs to a momentum of sqrt(2 K),
    which is the definition of kinetic energy rather than a measurement.
    """
    unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
    return sqrt(2.0 * electronvolts_to_hartree(unstreaked))


def _linear_amplitude_electronvolt(manifest: Manifest, line: Line) -> float:
    """The peak of the analytic relation for this line, in electronvolts.

    The momentum times the peak of the model's own vector potential. This is the
    scale the first comparison's tolerance is stated in, and it is deliberately
    the model's own number: that comparison is about the SHAPE the centre of
    energy traces, and a tolerance in units of the amplitude that produced it is
    what makes the two terms it accounts for come out as pure fractions.

    Nothing about the size of the field is checked here. That is the second
    comparison, and it uses the closed form below rather than this.
    """
    field = StreakingField(manifest)
    return hartree_to_electronvolts(
        _momentum_atomic(manifest, line) * field.peak_vector_potential
    )


def _closed_form_amplitude_electronvolt(
    manifest: Manifest,
    line: Line,
    peak_intensity: float = _STREAKING_INTENSITY,
) -> float:
    """The same peak, built from the chosen intensity and carrier instead.

    The momentum times the peak intensity's field amplitude over the carrier's
    angular frequency, which in atomic units is the photon energy in hartree.
    Nothing here asks the streaking field what its potential is, and that is the
    whole point: an amplitude read back out of the model agrees with itself
    however wrong it is, so a case built on one is green against a model whose
    potential is half what this intensity gives.

    The two conversions are the module that owns them, `units`, so this is not a
    second place where an intensity becomes a field. What is written out here is
    the relation between that field and the potential it integrates to, which is
    the thing under test.

    The intensity is an argument so that the near miss can build the same closed
    form from a different one.
    """
    amplitude = peak_intensity_to_atomic_field(
        peak_intensity
    ) / electronvolts_to_hartree(_CARRIER_ELECTRONVOLT)
    return hartree_to_electronvolts(_momentum_atomic(manifest, line) * amplitude)


def _line_window(manifest: Manifest, spectrogram: Spectrogram, line: Line) -> slice:
    """Every energy bin this line reaches, and one either side of it.

    The span is the map's own answer for where this line goes over this scan,
    rather than an estimate of it built here. One bin of slack at each end
    covers the outermost deposit, which is split between the bin below an energy
    and the bin above it, so a window ending exactly at the span could hold half
    of one.
    """
    lowest, highest = energy_span_electronvolt(
        manifest, line, spectrogram.delay_axis_attosecond
    )
    return spectrogram.energy_window(
        lowest - _ENERGY_STEP_ELECTRONVOLT, highest + _ENERGY_STEP_ELECTRONVOLT
    )


def _centre_of_energy(
    manifest: Manifest, spectrogram: Spectrogram, line: Line
) -> NDArray[np.float64]:
    """One line's centre of energy at each delay, read out of the assembly.

    The window is made into a spectrogram of its own so that the model's own
    reading is what answers, rather than a weighted mean written out again here.
    """
    window = _line_window(manifest, spectrogram, line)
    return centre_of_energy_electronvolt(
        Spectrogram.of(
            counts=spectrogram.counts[window, :],
            energy_axis_electronvolt=spectrogram.energy_axis_electronvolt[window],
            delay_axis_attosecond=spectrogram.delay_axis_attosecond,
            manifest=manifest,
        )
    )


def _analytic_electronvolt(
    manifest: Manifest, line: Line, at_the_line_s_own_delay: bool = True
) -> NDArray[np.float64]:
    """The analytic streaking relation for this line, over the delay scan.

    The unstreaked energy less the momentum times the vector potential. The
    minus is the model's own convention and the reason for it is in
    `streaking_field`: the electron's charge is negative, so the final momentum
    is the initial momentum less the potential at the moment of birth.

    The potential is read at the delay plus the line's own intrinsic delay,
    because that is the moment of the field this line's electrons see. A caller
    can ask for it without, which is what the near miss below does.
    """
    field = StreakingField(manifest)
    unstreaked = unstreaked_energy_electronvolt(Pulse(manifest), line)
    momentum = _momentum_atomic(manifest, line)
    shift = line.intrinsic_delay_attosecond if at_the_line_s_own_delay else 0.0
    return np.array(
        [
            unstreaked
            - hartree_to_electronvolts(momentum * field.vector_potential(delay + shift))
            for delay in delay_axis_attosecond(manifest).tolist()
        ],
        dtype=np.float64,
    )


def _averaging_term() -> float:
    """How much the ionising pulse's own length shrinks the oscillation.

    The centre of energy is the intensity weighted mean of the shift over the
    birth times, so the oscillation it carries is the potential averaged over a
    Gaussian of standard deviation s rather than read at one instant. Expanding
    about the middle of the pulse leaves (1/2) w^2 s^2 of the linear term, where
    w is the carrier's angular frequency.

    For a 150 as intensity full width at half maximum, s = 63.70 as, and one
    cycle of a 1.55 eV carrier is 2668.17 as, so this is 1.125e-02.
    """
    standard_deviation = _IONISING_DURATION_ATTOSECOND / _FWHM_IN_STANDARD_DEVIATIONS
    return 0.5 * (_RADIANS_PER_TURN * standard_deviation / _PERIOD_ATTOSECOND) ** 2


def _quadratic_term(manifest: Manifest, line: Line) -> float:
    """The term the analytic relation drops, as a fraction of the one it keeps.

    The full classical shift is the momentum times the potential plus the
    potential squared over two. The second is A/(2p) of the first at the peak of
    the field, which is 2.089e-02 for the 2p line and 2.682e-02 for the 2s line
    in this run, the difference being the momentum.
    """
    field = StreakingField(manifest)
    return field.peak_vector_potential / (2.0 * _momentum_atomic(manifest, line))


def _envelope_at_half_a_period(manifest: Manifest) -> float:
    """What the potential's own envelope has fallen to half a cycle from its peak.

    Read off the model's field rather than rebuilt: at a carrier envelope phase
    of zero the carrier is at plus one at time zero and at minus one half a
    period later, so the potential there is minus the peak times the envelope.
    It is 0.99385 for the twenty femtosecond pulse this case uses.
    """
    field = StreakingField(manifest)
    return (
        -field.vector_potential(0.5 * _PERIOD_ATTOSECOND) / field.peak_vector_potential
    )


def _tracking_bound(manifest: Manifest, line: Line) -> float:
    """What the centre of energy may depart from the analytic relation by, in eV.

    Two terms, both of them things the relation drops rather than errors. The
    term that goes as the square of the potential, which is A/(2p) of the linear
    one, and the averaging over the ionising pulse, which is (1/2) w^2 s^2 of it.

    Derived: 2.089e-02 + 1.125e-02 = 3.214e-02 for 2p, and 2.682e-02 +
    1.125e-02 = 3.807e-02 for 2s, times the margin. Measured: 0.18091 eV against
    a linear amplitude of 5.71914 eV, which is 3.163e-02, for 2p; and 0.16641 eV
    against 4.45497 eV, which is 3.735e-02, for 2s. Derivation and measurement
    agree to two figures on both lines.
    """
    return (
        _BOUND_MARGIN
        * (_quadratic_term(manifest, line) + _averaging_term())
        * _linear_amplitude_electronvolt(manifest, line)
    )


def _excursion_bound(manifest: Manifest, line: Line) -> float:
    """What the peak to peak excursion may fall short of twice the linear one by.

    The closed form is 2 p A, and four things stand between it and what a scan
    of this model produces. Each is written as an expression rather than as a
    number, so the bound follows the case.

    The averaging over the ionising pulse, (1/2) w^2 s^2 = 1.125e-02, which
    shrinks both extremes.

    The field's envelope, which is not at its peak half a cycle from the crest.
    The trough is smaller by (1 - e), and it is one of the two extremes, so the
    excursion is short by (1 - e)/2 = 3.075e-03.

    The term that goes as the square of the potential, which adds to both
    extremes and therefore cancels out of their difference except where the
    envelope makes the two unequal: A/(4p) times (1 - e^2), 1.28e-04 for 2p and
    1.64e-04 for 2s.

    The delay grid, because an extremum of the curve in general falls between two
    sampled delays. The worst case is half a step, where the cosine has already
    come down by 1 - cos(pi * step / T) = 2.142e-03, and it is a real term here:
    the 2s line's extrema sit 21 as off the grid because that is its intrinsic
    delay.

    Derived: 1.659e-02 for 2p and 1.663e-02 for 2s, times the margin. Measured:
    11.27395 eV against a closed form of 11.43828 eV, short by 1.437e-02, for
    2p; and 8.77175 eV against 8.90994 eV, short by 1.551e-02, for 2s.
    """
    envelope = _envelope_at_half_a_period(manifest)
    step = _PERIOD_ATTOSECOND / _SAMPLES_PER_CYCLE
    fraction = (
        _averaging_term()
        + 0.5 * (1.0 - envelope)
        + 0.5 * _quadratic_term(manifest, line) * (1.0 - envelope * envelope)
        + (1.0 - cos(pi * step / _PERIOD_ATTOSECOND))
    )
    return (
        _BOUND_MARGIN
        * fraction
        * 2.0
        * _closed_form_amplitude_electronvolt(manifest, line)
    )


def _phase_delay_attosecond(
    manifest: Manifest, centre_electronvolt: NDArray[np.float64]
) -> float:
    """The delay this oscillation is shifted by, read off its phase.

    A direct read and not the standard analysis, which does not exist yet. The
    curve is projected onto a cosine and a sine at the carrier frequency; over a
    whole number of cycles sampled uniformly those two are orthogonal to each
    other and to every other harmonic, so the projection is the least squares fit
    and no matrix has to be solved to say so.

    The model's centre of energy goes as minus the potential, so a curve of
    C - a cos(w d + f) projects to -a cos f on the cosine and +a sin f on the
    sine, and f is recovered from those two with the signs in that order. A line
    whose electrons are born f/w later than the reference reaches the same moment
    of the field at a delay that much earlier, which is why the phase divided by
    the angular frequency is the delay itself and not its negative.
    """
    delays = delay_axis_attosecond(manifest)
    phase = _RADIANS_PER_TURN * delays / _PERIOD_ATTOSECOND
    against_cosine = float(np.sum(centre_electronvolt * np.cos(phase)))
    against_sine = float(np.sum(centre_electronvolt * np.sin(phase)))
    return atan2(against_sine, -against_cosine) * _PERIOD_ATTOSECOND / _RADIANS_PER_TURN


class TheWindowsHoldWholeLines(unittest.TestCase):
    """Read first, compared afterwards. A truncated line has a biased centre."""

    def test_the_two_windows_carry_every_count_in_the_spectrogram(self) -> None:
        manifest = _manifest()
        assembled = neon_main_lines_spectrogram(manifest)
        lines = _lines(manifest)
        inside = 0.0
        for name in NEON_MAIN_LINE_NAMES:
            window = _line_window(manifest, assembled, lines[name])
            inside += float(assembled.counts[window, :].sum())
        self.assertAlmostEqual(
            inside / assembled.total_counts(), 1.0, delta=_WINDOW_TOLERANCE
        )

    def test_the_scan_is_a_whole_number_of_cycles_of_samples(self) -> None:
        # The phase read leans on this, so it is asserted rather than assumed.
        # The delays run from minus one period to one period less one step, so
        # the span is one step short of the whole and the sample positions are
        # the whole.
        manifest = _manifest()
        delays = delay_axis_attosecond(manifest)
        step = float(delays[1]) - float(delays[0])
        self.assertEqual(delays.size, _SCAN_CYCLES * _SAMPLES_PER_CYCLE)
        self.assertAlmostEqual(
            delays.size * step / _PERIOD_ATTOSECOND, float(_SCAN_CYCLES), delta=1e-12
        )


class TheCentreOfEnergyFollowsTheAnalyticRelation(unittest.TestCase):
    """The first comparison. Both curves, point by point, over the same axis."""

    def test_each_line_follows_the_potential_scaled_by_its_own_momentum(self) -> None:
        manifest = _manifest()
        assembled = neon_main_lines_spectrogram(manifest)
        lines = _lines(manifest)
        for name in NEON_MAIN_LINE_NAMES:
            with self.subTest(line=name):
                line = lines[name]
                departure = float(
                    np.max(
                        np.abs(
                            _centre_of_energy(manifest, assembled, line)
                            - _analytic_electronvolt(manifest, line)
                        )
                    )
                )
                self.assertLess(
                    departure,
                    _tracking_bound(manifest, line),
                    f"The centre of energy of the {name} line does not follow "
                    "the vector potential scaled by its central momentum.",
                )

    def test_the_relation_read_at_the_wrong_moment_of_the_field_misses(self) -> None:
        # The near miss, and it is the mistake the map's own docstring warns
        # about: an electron of a line with an intrinsic delay samples the field
        # at the delay plus that delay, and a comparison that read the potential
        # at the delay alone would be comparing two curves that are 21 as apart.
        # It is available only on the line that has an intrinsic delay.
        manifest = _manifest()
        assembled = neon_main_lines_spectrogram(manifest)
        line = _lines(manifest)["2s"]
        self.assertNotEqual(line.intrinsic_delay_attosecond, 0.0)
        departure = float(
            np.max(
                np.abs(
                    _centre_of_energy(manifest, assembled, line)
                    - _analytic_electronvolt(
                        manifest, line, at_the_line_s_own_delay=False
                    )
                )
            )
        )
        self.assertGreater(
            departure,
            _tracking_bound(manifest, line),
            "The near miss no longer misses, so the case above proves nothing.",
        )


class TheExcursionIsTheSizeTheClosedFormGives(unittest.TestCase):
    """The second comparison. The size of the trace and not only its shape."""

    def _peak_to_peak(self, manifest: Manifest, line: Line) -> float:
        centre = _centre_of_energy(
            manifest, neon_main_lines_spectrogram(manifest), line
        )
        return float(centre.max() - centre.min())

    def test_each_line_swings_twice_its_momentum_times_the_potential(self) -> None:
        manifest = _manifest()
        for name in NEON_MAIN_LINE_NAMES:
            with self.subTest(line=name):
                line = _lines(manifest)[name]
                closed = 2.0 * _closed_form_amplitude_electronvolt(manifest, line)
                self.assertAlmostEqual(
                    self._peak_to_peak(manifest, line),
                    closed,
                    delta=_excursion_bound(manifest, line),
                    msg=f"The {name} line's excursion is not the size the closed "
                    "form gives for this intensity and this carrier.",
                )

    def test_a_closed_form_built_from_the_wrong_intensity_misses(self) -> None:
        # The near miss. A peak intensity ten parts in a hundred out is a field
        # amplitude, and therefore an excursion, out by five, which is more than
        # three times what the terms above account for. This is the case that
        # says the comparison would catch a streaking amplitude wrong by a
        # factor rather than only a trace of the wrong shape.
        manifest = _manifest()
        for name in NEON_MAIN_LINE_NAMES:
            with self.subTest(line=name):
                line = _lines(manifest)[name]
                closed = 2.0 * _closed_form_amplitude_electronvolt(
                    manifest, line, peak_intensity=1.1 * _STREAKING_INTENSITY
                )
                self.assertGreater(
                    abs(self._peak_to_peak(manifest, line) - closed),
                    _excursion_bound(manifest, line),
                    "The near miss no longer misses, so the case above proves nothing.",
                )


class TheRelativeDelayIsWhatWasInjected(unittest.TestCase):
    """The third comparison. Read off the two phases, not through the analysis."""

    def _difference(self, manifest: Manifest) -> float:
        assembled = neon_main_lines_spectrogram(manifest)
        lines = _lines(manifest)
        read = {
            name: _phase_delay_attosecond(
                manifest, _centre_of_energy(manifest, assembled, lines[name])
            )
            for name in NEON_MAIN_LINE_NAMES
        }
        return read["2s"] - read["2p"]

    def test_the_phases_give_back_the_difference_that_was_put_in(self) -> None:
        self.assertAlmostEqual(
            self._difference(_manifest()),
            _INJECTED_DIFFERENCE_ATTOSECOND,
            delta=_PHASE_TOLERANCE_ATTOSECOND,
            msg="The relative delay read off the two oscillation phases is not "
            "the difference the manifest injected.",
        )

    def test_a_difference_of_the_other_sign_comes_back_with_its_sign(self) -> None:
        # Without this the case above would also pass against a read that
        # answered with a constant, and against one that had lost the sign. A
        # line emitting before the one it is measured against is the case this
        # board exists to be able to represent.
        manifest = _manifest(
            **{
                parameter_name("2s", INTRINSIC_DELAY): (
                    _DELAY_2P_ATTOSECOND + _OTHER_DIFFERENCE_ATTOSECOND
                )
            }
        )
        self.assertAlmostEqual(
            self._difference(manifest),
            _OTHER_DIFFERENCE_ATTOSECOND,
            delta=_PHASE_TOLERANCE_ATTOSECOND,
        )

    def test_moving_both_lines_together_moves_no_difference(self) -> None:
        # The relative delay is what the analysis will later extract, and it may
        # not depend on where the pair sits as a whole. A read that answered
        # with one line's phase rather than with the difference would fail here.
        manifest = _manifest(
            **{
                parameter_name("2p", INTRINSIC_DELAY): 120.0,
                parameter_name("2s", INTRINSIC_DELAY): (
                    120.0 + _INJECTED_DIFFERENCE_ATTOSECOND
                ),
            }
        )
        self.assertAlmostEqual(
            self._difference(manifest),
            _INJECTED_DIFFERENCE_ATTOSECOND,
            delta=_PHASE_TOLERANCE_ATTOSECOND,
        )


if __name__ == "__main__":
    unittest.main()
