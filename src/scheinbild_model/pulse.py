"""The ionising pulse, as an envelope in time and a spectrum in energy.

The pulse is a Gaussian in the field amplitude, which is what makes both its
envelope and its spectrum available in closed form and is the simplest shape
that can carry a chirp. Everything here is in atomic units internally and the
parameters arrive in electronvolts and attoseconds, converted once at the
boundary by units.py, which is the rule in
../../docs/decisions/units-and-constants.md.

Every parameter comes from the manifest and there is no other way to build one
of these. That is not a style choice: a value that influences the output and is
not in the manifest makes the manifest wrong, which is what
../../docs/decisions/determinism-and-seeding.md is about, and a default argument
here would be exactly such a value.

## The three things the constructor refuses

A duration and a bandwidth that no optics could produce together. They are not
independent. For a Gaussian, the product of the two intensity full widths at
half maximum is fixed at its smallest by the transform limit, and larger only in
proportion to the chirp. An operator who sets both to values below that limit
has described a pulse that cannot exist, and the model would otherwise build it
and produce a spectrogram that looks like a measurement.

A bandwidth that disagrees with the chirp. Above the transform limit the excess
IS the chirp, so a manifest carrying a duration, a chirp and a bandwidth carries
one number too many, and the refusal names the supplied and the derived value
rather than silently preferring one.

A time grid too short to hold the pulse. Truncating the envelope at the edge of
the grid puts a step into the time domain, and a step becomes structure in the
spectrum, which then arrives in the spectrogram as something a reader could
mistake for physics. The constructor evaluates the intensity envelope at both
edges and refuses a grid where it has not fallen below a stated fraction of the
peak.

## The chirp

Present from the start, and the first runs will not use it. A chirped ionising
pulse is one of the things that could plausibly bias a delay measurement, so it
has to be sweepable later, and a parameter that is absent cannot be swept after
the freeze in milestone 7 without changing the model.

It is written as the rate at which the instantaneous photon energy sweeps, in
electronvolts per attosecond, because that is a number a reader of this field
can picture. Inside, it is half that rate, which is the coefficient of the
quadratic term of the phase.

## The relations, written out

With the field amplitude E(t) proportional to exp(-(a - i b) t^2), a positive:

The intensity envelope is exp(-2 a t^2), so its full width at half maximum in
time is dt = sqrt(2 ln 2 / a), which inverts to a = 2 ln 2 / dt^2.

The spectral intensity is exp(-a w^2 / (2 (a^2 + b^2))), so its full width at
half maximum in angular frequency, which in atomic units is the same number as
the width in energy, is dE = 2 sqrt(2 ln 2 (a^2 + b^2) / a).

With b = 0 those two give dE dt = 4 ln 2, which is the transform limit for a
Gaussian and is the analytic relation the suite checks against. With b non-zero
the product is larger by sqrt(1 + (b / a)^2) and never smaller, which is why a
supplied bandwidth below the limit is refused rather than adjusted.
"""

from math import exp, log, sqrt

from scheinbild_model.manifest import Manifest
from scheinbild_model.units import (
    atomic_time_to_attoseconds,
    attoseconds_to_atomic_time,
    electronvolts_to_hartree,
    hartree_to_electronvolts,
)

# The transform limit for a Gaussian, as the product of the two intensity full
# widths at half maximum in atomic units. Not a measured quantity and not a
# constant of nature, so it is not a row of the constant table: it follows from
# the shape chosen for the pulse and is derived in this module's own docstring.
TRANSFORM_LIMIT = 4.0 * log(2.0)

# How far the intensity envelope has to have fallen at the edge of the time
# grid before the grid counts as holding the pulse. A modelling threshold
# rather than a physical value. One part in a million is about five times the
# intensity half width away from the peak, and the step it leaves in the time
# domain is below what any later stage of this model resolves.
EDGE_INTENSITY_FRACTION = 1e-6

# How closely a supplied bandwidth has to agree with the derived one. Loose
# enough that a value quoted to four figures in a manifest is accepted, tight
# enough that a factor, or a confusion between a half width and a full width,
# is not.
BANDWIDTH_AGREEMENT = 1e-3

CENTRAL_ENERGY = "pulse_central_energy_electronvolt"
DURATION = "pulse_duration_attosecond"
CHIRP = "pulse_chirp_electronvolt_per_attosecond"
TIME_GRID_HALF_WIDTH = "pulse_time_grid_half_width_attosecond"
BANDWIDTH = "pulse_bandwidth_electronvolt"


class PulseRefused(ValueError):
    """A pulse was described that no optics could make, or no grid could hold."""


class Pulse:
    """A Gaussian ionising pulse, built from a manifest and from nothing else.

    Read the parameters off the instance in the units they were given in. The
    atomic unit values are the private ones, because a caller that wanted them
    is inside the core and should be calling the methods rather than doing its
    own arithmetic on the parameters.
    """

    def __init__(self, manifest: Manifest) -> None:
        """Build the pulse this manifest describes, or refuse to.

        The only argument is the manifest. There is no second source of
        configuration and no default, so a parameter this pulse reads is a
        parameter the manifest carries, and one it does not carry raises out of
        the manifest rather than being filled in here.
        """
        self.central_energy_electronvolt = _as_float(manifest, CENTRAL_ENERGY)
        self.duration_attosecond = _as_float(manifest, DURATION)
        self.chirp_electronvolt_per_attosecond = _as_float(manifest, CHIRP)
        self.time_grid_half_width_attosecond = _as_float(
            manifest, TIME_GRID_HALF_WIDTH
        )

        if self.central_energy_electronvolt <= 0.0:
            raise PulseRefused(
                f"The central photon energy is "
                f"{self.central_energy_electronvolt} eV. A pulse that ionises "
                "carries a positive photon energy."
            )
        if self.duration_attosecond <= 0.0:
            raise PulseRefused(
                f"The pulse duration is {self.duration_attosecond} as. The "
                "duration is the intensity full width at half maximum and is "
                "positive."
            )
        if self.time_grid_half_width_attosecond <= 0.0:
            raise PulseRefused(
                "The time grid half width is "
                f"{self.time_grid_half_width_attosecond} as. A grid with no "
                "extent holds no pulse."
            )

        self._central_energy = electronvolts_to_hartree(
            self.central_energy_electronvolt
        )
        self._duration = attoseconds_to_atomic_time(self.duration_attosecond)
        # An energy per time converts as an energy and then as a time, which is
        # why this reads as a product rather than as one call.
        self._chirp_rate = electronvolts_to_hartree(
            self.chirp_electronvolt_per_attosecond
        ) * atomic_time_to_attoseconds(1.0)

        # The real and imaginary parts of the Gaussian parameter. The quadratic
        # phase coefficient is half the rate at which the instantaneous energy
        # sweeps, because differentiating that phase gives back the rate.
        self._a = 2.0 * log(2.0) / (self._duration * self._duration)
        self._b = 0.5 * self._chirp_rate

        self._bandwidth = 2.0 * sqrt(
            2.0 * log(2.0) * (self._a * self._a + self._b * self._b) / self._a
        )
        self.bandwidth_electronvolt = hartree_to_electronvolts(self._bandwidth)

        self._refuse_a_bandwidth_that_cannot_go_with_this_duration(manifest)
        self._refuse_a_grid_that_truncates()

    def _refuse_a_bandwidth_that_cannot_go_with_this_duration(
        self, manifest: Manifest
    ) -> None:
        """Check a supplied bandwidth against the one this pulse implies.

        Silent when the manifest carries no bandwidth, which is the ordinary
        case: the bandwidth is derived, so a manifest that does not state it is
        complete rather than short of a parameter.
        """
        if BANDWIDTH not in manifest.parameters:
            return
        supplied = _as_float(manifest, BANDWIDTH)
        if supplied <= 0.0:
            raise PulseRefused(
                f"The supplied bandwidth is {supplied} eV. A bandwidth is "
                "positive."
            )
        product = attoseconds_to_atomic_time(
            self.duration_attosecond
        ) * electronvolts_to_hartree(supplied)
        if product < TRANSFORM_LIMIT * (1.0 - BANDWIDTH_AGREEMENT):
            raise PulseRefused(
                "A duration of "
                f"{self.duration_attosecond} as and a bandwidth of {supplied} "
                "eV cannot go together. Their product in atomic units is "
                f"{product}, and the transform limit for a Gaussian is "
                f"{TRANSFORM_LIMIT}. No optics make a pulse below that limit, "
                "so this manifest describes a pulse that cannot exist rather "
                "than one that is hard to produce. The shortest duration this "
                "bandwidth supports is "
                f"{atomic_time_to_attoseconds(TRANSFORM_LIMIT / electronvolts_to_hartree(supplied))} as."
            )
        if abs(supplied - self.bandwidth_electronvolt) > (
            BANDWIDTH_AGREEMENT * self.bandwidth_electronvolt
        ):
            raise PulseRefused(
                f"The manifest supplies a bandwidth of {supplied} eV, and a "
                f"duration of {self.duration_attosecond} as with a chirp of "
                f"{self.chirp_electronvolt_per_attosecond} eV/as implies "
                f"{self.bandwidth_electronvolt} eV. Above the transform limit "
                "the excess bandwidth is the chirp, so those three numbers are "
                "one too many and this pulse will not choose between them. "
                "Remove the bandwidth from the manifest and it is derived, or "
                "set the chirp to the value the bandwidth implies."
            )

    def _refuse_a_grid_that_truncates(self) -> None:
        """Refuse a time grid the pulse does not fit inside.

        A truncated envelope is a step in the time domain, a step is structure
        in the spectrum, and that structure arrives in the spectrogram looking
        like something to explain.
        """
        at_the_edge = self.intensity_envelope(
            self.time_grid_half_width_attosecond
        )
        if at_the_edge > EDGE_INTENSITY_FRACTION:
            raise PulseRefused(
                "The time grid is too short to hold this pulse. At its edge, "
                f"{self.time_grid_half_width_attosecond} as from the peak, the "
                f"intensity envelope is still {at_the_edge} of its maximum, "
                f"and it has to be at or below {EDGE_INTENSITY_FRACTION}. "
                "Truncating the envelope puts a step in the time domain, which "
                "becomes structure in the spectrum and then structure in the "
                "spectrogram that reads as physics. A half width of at least "
                f"{self.smallest_time_grid_half_width_attosecond()} as holds "
                "it."
            )

    def smallest_time_grid_half_width_attosecond(self) -> float:
        """The shortest grid half width that holds this pulse.

        Inverts the envelope at the stated edge fraction. Offered so that the
        refusal above can say what to do rather than only what is wrong.
        """
        return atomic_time_to_attoseconds(
            sqrt(-log(EDGE_INTENSITY_FRACTION) / (2.0 * self._a))
        )

    def intensity_envelope(self, time_attosecond: float) -> float:
        """The intensity envelope at a time, as a fraction of its peak.

        The chirp does not appear. It is a phase, and a phase does not move
        intensity in time, which is why the grid check below does not depend on
        it.
        """
        time = attoseconds_to_atomic_time(time_attosecond)
        return exp(-2.0 * self._a * time * time)

    def spectral_intensity(self, energy_electronvolt: float) -> float:
        """The spectral intensity at a photon energy, as a fraction of its peak."""
        offset = electronvolts_to_hartree(
            energy_electronvolt - self.central_energy_electronvolt
        )
        return exp(
            -self._a
            * offset
            * offset
            / (2.0 * (self._a * self._a + self._b * self._b))
        )


def _as_float(manifest: Manifest, name: str) -> float:
    """One parameter, as a float, refusing a value that is not a number.

    A string that looks like a number is what a manifest read out of a file
    would produce, and it survives every arithmetic operation this module does
    in exactly one direction. The manifest already refuses a value with no
    machine independent rendering; this refuses one that renders fine and is
    not a quantity.
    """
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PulseRefused(
            f"The parameter {name!r} is {value!r}, which is not a number. The "
            "pulse takes quantities, and a manifest may hold strings and "
            "booleans for parameters that are not quantities."
        )
    return float(value)
