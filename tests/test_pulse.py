"""The ionising pulse: built from a manifest, and refusing what cannot exist.

Three things are under test and they fail differently.

The pulse takes every parameter from a manifest and there is no other way to
build one. That is the arrangement the whole reproducibility rule rests on, and
the test for it is the one that would pass just as well if a default were added,
so it is written as an absence: a manifest missing a parameter has to raise out
of the manifest rather than be filled in.

The duration and the bandwidth are not independent. A combination below the
transform limit is a pulse no optics could make, and a model that built it would
produce a spectrogram that looks like a measurement.

A grid too short to hold the pulse truncates the envelope, which puts a step in
the time domain, which becomes structure in the spectrum, which then arrives in
the spectrogram looking like physics.

The analytic relation the unchirped case is checked against is derived in the
module's own docstring and is checked here against the constant table rather
than against a number written down twice.
"""

import math
import unittest

from scheinbild_model.constants import CONSTANTS
from scheinbild_model.manifest import Manifest, ParameterNotInManifest
from scheinbild_model.pulse import (
    BANDWIDTH,
    CENTRAL_ENERGY,
    CHIRP,
    DURATION,
    TIME_GRID_HALF_WIDTH,
    TRANSFORM_LIMIT,
    Pulse,
    PulseRefused,
)

# A pulse in the region this board is about: the measurement it argues with was
# made at 105.2 eV. The duration and the grid are round numbers chosen so that
# the grid comfortably holds the pulse, and neither is a value taken from any
# source.
_BASE = {
    CENTRAL_ENERGY: 105.2,
    DURATION: 200.0,
    CHIRP: 0.0,
    TIME_GRID_HALF_WIDTH: 500.0,
}


def _manifest(**overrides) -> Manifest:
    parameters = dict(_BASE)
    parameters.update(overrides)
    return Manifest.of(parameters=parameters, seeds={}, code_version="0.0.0")


def _hbar_in_electronvolt_attosecond() -> float:
    """The reduced Planck constant in the units this test compares in.

    Built out of the constant table rather than written down, because a second
    copy of a number is a second thing to keep right. In atomic units the
    reduced Planck constant is one, so it is one hartree times one atomic unit
    of time, and this is that product carried into electronvolts and
    attoseconds.
    """
    return (
        CONSTANTS["hartree_energy_in_electronvolt"].value
        * CONSTANTS["atomic_unit_of_time_in_second"].value
        * CONSTANTS["attoseconds_per_second"].value
    )


class ThePulseIsBuiltFromAManifestAndNothingElse(unittest.TestCase):
    """The model reads a parameter from the manifest or it does not read it."""

    def test_a_pulse_is_built_from_a_manifest_alone(self):
        # The constructor takes one argument and it is the manifest. There is
        # no configuration object, no keyword with a default, and no module
        # level value to fall back on.
        pulse = Pulse(_manifest())
        self.assertEqual(pulse.central_energy_electronvolt, 105.2)
        self.assertEqual(pulse.duration_attosecond, 200.0)

    def test_a_parameter_the_manifest_does_not_carry_stops_the_run(self):
        for missing in (CENTRAL_ENERGY, DURATION, CHIRP, TIME_GRID_HALF_WIDTH):
            with self.subTest(missing=missing):
                parameters = {
                    name: value
                    for name, value in _BASE.items()
                    if name != missing
                }
                manifest = Manifest.of(
                    parameters=parameters, seeds={}, code_version="0.0.0"
                )
                with self.assertRaises(ParameterNotInManifest):
                    Pulse(manifest)

    def test_a_parameter_that_is_not_a_quantity_is_refused(self):
        # A manifest may legitimately hold a string or a boolean, so the pulse
        # refuses one where it wanted a number rather than letting it through
        # into the arithmetic.
        with self.assertRaises(PulseRefused):
            Pulse(_manifest(**{DURATION: "200"}))

    def test_a_pulse_with_no_extent_is_refused(self):
        for override in (
            {CENTRAL_ENERGY: 0.0},
            {CENTRAL_ENERGY: -105.2},
            {DURATION: 0.0},
            {DURATION: -200.0},
            {TIME_GRID_HALF_WIDTH: 0.0},
        ):
            with self.subTest(override=override):
                with self.assertRaises(PulseRefused):
                    Pulse(_manifest(**override))


class TheWidthsAreTheWidthsTheyAreCalled(unittest.TestCase):
    """The duration and the bandwidth are full widths at half maximum.

    A half width called a full width is the classic factor of two in this kind
    of code, and it does not show up as a wrong shape.
    """

    def test_the_intensity_envelope_is_half_at_half_the_duration(self):
        pulse = Pulse(_manifest())
        self.assertAlmostEqual(
            pulse.intensity_envelope(pulse.duration_attosecond / 2.0),
            0.5,
            places=12,
        )
        self.assertAlmostEqual(
            pulse.intensity_envelope(-pulse.duration_attosecond / 2.0),
            0.5,
            places=12,
        )

    def test_the_envelope_peaks_at_the_arrival_time(self):
        pulse = Pulse(_manifest())
        self.assertEqual(pulse.intensity_envelope(0.0), 1.0)

    def test_the_spectrum_is_half_at_half_the_bandwidth_from_the_centre(self):
        pulse = Pulse(_manifest())
        half = pulse.bandwidth_electronvolt / 2.0
        for offset in (half, -half):
            with self.subTest(offset=offset):
                self.assertAlmostEqual(
                    pulse.spectral_intensity(
                        pulse.central_energy_electronvolt + offset
                    ),
                    0.5,
                    places=12,
                )

    def test_the_spectrum_peaks_at_the_central_energy(self):
        pulse = Pulse(_manifest())
        self.assertEqual(
            pulse.spectral_intensity(pulse.central_energy_electronvolt), 1.0
        )


class TheUnchirpedPulseIsTransformLimited(unittest.TestCase):
    """The analytic relation, checked against the table and not against itself."""

    def test_the_product_of_the_two_widths_is_the_transform_limit(self):
        for duration in (50.0, 200.0, 800.0):
            with self.subTest(duration=duration):
                pulse = Pulse(
                    _manifest(
                        **{DURATION: duration, TIME_GRID_HALF_WIDTH: 4000.0}
                    )
                )
                product_in_electronvolt_attosecond = (
                    pulse.bandwidth_electronvolt * pulse.duration_attosecond
                )
                self.assertTrue(
                    math.isclose(
                        product_in_electronvolt_attosecond,
                        TRANSFORM_LIMIT * _hbar_in_electronvolt_attosecond(),
                        rel_tol=1e-12,
                    ),
                    f"{product_in_electronvolt_attosecond} against "
                    f"{TRANSFORM_LIMIT * _hbar_in_electronvolt_attosecond()}",
                )

    def test_a_two_hundred_attosecond_pulse_is_about_nine_electronvolts_wide(self):
        # Not a tolerance on a physical value. The assertion is that the
        # bandwidth is around nine electronvolts rather than nine tenths of one
        # or ninety, which is the size of every mistake this arithmetic can
        # make that a relation comparing two of its own quantities would miss.
        pulse = Pulse(_manifest())
        self.assertGreater(pulse.bandwidth_electronvolt, 9.0)
        self.assertLess(pulse.bandwidth_electronvolt, 9.3)

    def test_a_shorter_pulse_is_broader(self):
        short = Pulse(_manifest(**{DURATION: 100.0}))
        long = Pulse(_manifest(**{DURATION: 400.0, TIME_GRID_HALF_WIDTH: 1200.0}))
        self.assertGreater(
            short.bandwidth_electronvolt, long.bandwidth_electronvolt
        )


class TheChirpIsPresentAndDoesWhatAChirpDoes(unittest.TestCase):
    """Carried from the start so it can be swept after the freeze."""

    def test_a_chirp_broadens_the_spectrum_without_moving_the_envelope(self):
        unchirped = Pulse(_manifest())
        chirped = Pulse(_manifest(**{CHIRP: 0.05}))
        self.assertGreater(
            chirped.bandwidth_electronvolt, unchirped.bandwidth_electronvolt
        )
        # A chirp is a phase, and a phase moves no intensity in time.
        for time in (-150.0, -50.0, 0.0, 50.0, 150.0):
            with self.subTest(time=time):
                self.assertEqual(
                    chirped.intensity_envelope(time),
                    unchirped.intensity_envelope(time),
                )

    def test_a_chirp_of_either_sign_broadens_the_spectrum_the_same(self):
        up = Pulse(_manifest(**{CHIRP: 0.05}))
        down = Pulse(_manifest(**{CHIRP: -0.05}))
        self.assertAlmostEqual(
            up.bandwidth_electronvolt, down.bandwidth_electronvolt, places=12
        )

    def test_a_chirped_pulse_is_above_the_transform_limit(self):
        chirped = Pulse(_manifest(**{CHIRP: 0.05}))
        product = (
            chirped.bandwidth_electronvolt * chirped.duration_attosecond
        ) / _hbar_in_electronvolt_attosecond()
        self.assertGreater(product, TRANSFORM_LIMIT)


class ADurationAndABandwidthThatCannotGoTogetherAreRefused(unittest.TestCase):
    """The refusal names both numbers, because either one could be the mistake."""

    def test_a_bandwidth_below_the_transform_limit_is_refused(self):
        # Half the bandwidth a 200 as pulse can have. No optics make it.
        with self.assertRaises(PulseRefused) as refusal:
            Pulse(_manifest(**{BANDWIDTH: 4.5}))
        message = str(refusal.exception)
        self.assertIn("4.5", message)
        self.assertIn("200.0", message)
        # The phrase, not the exception type. Both refusals in this class are
        # PulseRefused and both would fire on this manifest, so a test that
        # only asked for the type would pass with the transform limit check
        # deleted, on the strength of the other one. That is not a hypothetical:
        # it is what this test did before, and deleting the check left the
        # suite green.
        self.assertIn("cannot exist", message)

    def test_a_bandwidth_above_the_limit_but_not_matching_the_chirp_is_refused(
        self,
    ):
        # Twice the transform limited bandwidth is a pulse that exists, and it
        # is not this one: the chirp is zero, so this manifest carries one
        # number too many.
        with self.assertRaises(PulseRefused) as refusal:
            Pulse(_manifest(**{BANDWIDTH: 18.3}))
        message = str(refusal.exception)
        self.assertIn("18.3", message)
        self.assertIn("one too many", message)

    def test_a_bandwidth_that_agrees_is_accepted(self):
        # The control. Without it every refusal above would also pass against a
        # constructor that refused any supplied bandwidth at all.
        derived = Pulse(_manifest()).bandwidth_electronvolt
        pulse = Pulse(_manifest(**{BANDWIDTH: derived}))
        self.assertAlmostEqual(
            pulse.bandwidth_electronvolt, derived, places=12
        )

    def test_a_manifest_with_no_bandwidth_derives_one(self):
        # The ordinary case. A manifest that does not state the bandwidth is
        # complete rather than short of a parameter, because the bandwidth
        # follows from the duration and the chirp.
        self.assertNotIn(BANDWIDTH, _manifest().parameters)
        self.assertGreater(Pulse(_manifest()).bandwidth_electronvolt, 0.0)


class AGridTooShortToHoldThePulseIsRefused(unittest.TestCase):
    """Truncation is a step in time and structure in the spectrum."""

    def test_a_grid_that_cuts_the_envelope_is_refused(self):
        with self.assertRaises(PulseRefused) as refusal:
            Pulse(_manifest(**{TIME_GRID_HALF_WIDTH: 300.0}))
        message = str(refusal.exception)
        self.assertIn("300.0", message)
        self.assertIn("too short", message)

    def test_the_refusal_says_what_grid_would_work(self):
        pulse = Pulse(_manifest())
        smallest = pulse.smallest_time_grid_half_width_attosecond()
        # Just inside the number the refusal offers is refused, and just
        # outside it is not, so the number is the boundary rather than a
        # comfortable overestimate somebody wrote down.
        with self.assertRaises(PulseRefused):
            Pulse(_manifest(**{TIME_GRID_HALF_WIDTH: smallest * 0.999}))
        Pulse(_manifest(**{TIME_GRID_HALF_WIDTH: smallest * 1.001}))

    def test_a_longer_pulse_needs_a_longer_grid(self):
        short = Pulse(_manifest())
        long = Pulse(_manifest(**{DURATION: 400.0, TIME_GRID_HALF_WIDTH: 1200.0}))
        self.assertGreater(
            long.smallest_time_grid_half_width_attosecond(),
            short.smallest_time_grid_half_width_attosecond(),
        )


if __name__ == "__main__":
    unittest.main()
