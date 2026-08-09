"""The streaking field, written down as a vector potential and derived from it.

The infrared field that does the streaking, as an envelope, a carrier, a carrier
envelope phase and a peak intensity. What the physics uses is the vector
potential, and how the potential is obtained is a modelling choice rather than an
implementation detail, so this module makes the choice and makes the other one
unreachable.

## The potential is written down and the field is differentiated from it

A field written down directly does not in general integrate to a potential that
returns to zero after the pulse has passed. A residual potential at late times is
unphysical: it says the pulse left a constant momentum behind it. In a delay scan
that shows up as a drift along the delay axis, which is a systematic effect
sitting on exactly the axis the extracted delay is read off.

So the vector potential is the primitive here. It is a Gaussian envelope times a
carrier, which goes to zero at both ends of time by construction, and the
electric field is its derivative in closed form. The other direction, writing the
field down and integrating it, is not available in this module and is not
available anywhere else either: nothing in this package returns a potential built
that way, and a caller that wants one has to write it.

The cost is stated rather than hidden. The duration below is the intensity full
width at half maximum of the envelope the POTENTIAL carries. The field's own
envelope differs from it by the term that comes off differentiating the envelope,
which is of the order of one over the carrier frequency times the duration. For a
pulse of many cycles that is a small correction and for a pulse of one or two it
is not, and this module does not pretend otherwise.

## The sign, in words as well as in symbols

An electron has charge minus one in atomic units. With the field written as the
negative time derivative of the potential,

    E(t) = -dA/dt

Newton's equation for the electron is

    dp/dt = -E(t) = +dA/dt

and integrating from the moment of ionisation to long after the pulse, where the
potential has gone,

    p(after) = p(at ionisation) - A(at ionisation)

So the final momentum is the initial momentum MINUS the vector potential at the
moment the electron was born. In words: an electron born while the potential is
positive comes out slower along the polarisation direction, and one born while
the potential is negative comes out faster.

That sentence is the whole convention, and it is worth reading twice, because a
sign error here inverts the direction of every extracted delay and produces a
result that is internally consistent and backwards. `momentum_shift` is the one
place the sign is applied, so a caller never writes it again.

The same statement is in ../../docs/decisions/physics-core.md, which is where the
core's approximations are argued, and the two say the same thing on purpose.

## What is one dimensional here

Momentum along the polarisation direction, which is the direction the classical
streaking map is written for and the direction a detector on this kind of
measurement looks along. There is no angular distribution in this module and the
core it belongs to does not have one either.
"""

from math import cos, exp, log, sin, sqrt

from scheinbild_model.manifest import Manifest
from scheinbild_model.units import (
    atomic_time_to_attoseconds,
    attoseconds_to_atomic_time,
    electronvolts_to_hartree,
    hartree_to_electronvolts,
    peak_intensity_to_atomic_field,
)

PHOTON_ENERGY = "streaking_field_photon_energy_electronvolt"
DURATION = "streaking_field_duration_attosecond"
CARRIER_ENVELOPE_PHASE = "streaking_field_carrier_envelope_phase_radian"
PEAK_INTENSITY = "streaking_field_peak_intensity_watt_per_square_centimetre"

# The Gaussian two, in both the places it appears. The envelope the potential
# carries is exp(-a t^2) in the amplitude, so the intensity envelope is
# exp(-2 a t^2) and a full width at half maximum of tau in the intensity gives
# a = 2 ln 2 / tau^2. Algebra of the chosen shape rather than a measurement.
GAUSSIAN_EXPONENT = 2.0

# A kinetic energy of K in atomic units belongs to a momentum of sqrt(2 K), and
# an energy is a momentum squared over two. The same two, for the same reason:
# it is the definition of kinetic energy and not a quantity anything measured.
KINETIC_ENERGY_COEFFICIENT = 2.0


class StreakingFieldRefused(ValueError):
    """A streaking field was described that is not a field."""


class StreakingField:
    """The streaking pulse, built from a manifest and from nothing else.

    Read the parameters off the instance in the units they arrived in. The
    potential and the field are returned in atomic units, because they are used
    inside the core and there is no reader facing unit for a vector potential
    that anyone would recognise; the energy shift is returned in electronvolts,
    because that one is read off an axis.
    """

    def __init__(self, manifest: Manifest) -> None:
        """Build the streaking field this manifest describes, or refuse to."""
        self.photon_energy_electronvolt = _as_float(manifest, PHOTON_ENERGY)
        self.duration_attosecond = _as_float(manifest, DURATION)
        self.carrier_envelope_phase_radian = _as_float(manifest, CARRIER_ENVELOPE_PHASE)
        self.peak_intensity_watt_per_square_centimetre = _as_float(
            manifest, PEAK_INTENSITY
        )

        if self.photon_energy_electronvolt <= 0.0:
            raise StreakingFieldRefused(
                f"The streaking photon energy is {self.photon_energy_electronvolt} "
                "eV. The carrier frequency divides the field to give the "
                "potential, so a frequency of zero or less is not a slow field, "
                "it is no field at all."
            )
        if self.duration_attosecond <= 0.0:
            raise StreakingFieldRefused(
                f"The streaking duration is {self.duration_attosecond} as. The "
                "duration is the intensity full width at half maximum of the "
                "envelope and is positive."
            )
        if self.peak_intensity_watt_per_square_centimetre <= 0.0:
            raise StreakingFieldRefused(
                "The streaking peak intensity is "
                f"{self.peak_intensity_watt_per_square_centimetre} W/cm^2. A run "
                "that wants no streaking at all does not apply a field; an "
                "intensity of zero or less would be a field whose amplitude is "
                "the square root of a number that is not positive."
            )

        self._angular_frequency = electronvolts_to_hartree(
            self.photon_energy_electronvolt
        )
        duration = attoseconds_to_atomic_time(self.duration_attosecond)
        self._envelope_rate = (
            GAUSSIAN_EXPONENT * log(GAUSSIAN_EXPONENT) / (duration * duration)
        )

        self.peak_field_strength = peak_intensity_to_atomic_field(
            self.peak_intensity_watt_per_square_centimetre
        )

        # The amplitude of the potential that goes with that field amplitude,
        # in the many cycle limit where the field is the carrier frequency times
        # the potential. It is exact as the peak of the potential this module
        # returns, and approximate as a statement about the peak of the field,
        # which is the correction the docstring above names.
        self.peak_vector_potential = self.peak_field_strength / self._angular_frequency

    def _phase(self, time: float) -> float:
        return self._angular_frequency * time + self.carrier_envelope_phase_radian

    def _envelope(self, time: float) -> float:
        return exp(-self._envelope_rate * time * time)

    def vector_potential(self, time_attosecond: float) -> float:
        """The vector potential at a time, in atomic units.

        The primitive of this module. Everything else here is derived from it,
        which is what makes the potential go to zero at both ends of time by
        construction rather than by a check somebody has to remember.
        """
        time = attoseconds_to_atomic_time(time_attosecond)
        return (
            self.peak_vector_potential * self._envelope(time) * cos(self._phase(time))
        )

    def electric_field(self, time_attosecond: float) -> float:
        """The electric field at a time, in atomic units, as minus dA/dt.

        Differentiated in closed form rather than numerically, so the field and
        the potential agree exactly rather than to within a step size. Both terms
        are here: the carrier term, which is the one a slowly varying envelope
        treatment keeps, and the envelope term, which is the one that makes the
        field's own envelope differ from the potential's.
        """
        time = attoseconds_to_atomic_time(time_attosecond)
        carrier = self._angular_frequency * sin(self._phase(time))
        from_the_envelope = (
            GAUSSIAN_EXPONENT * self._envelope_rate * time * cos(self._phase(time))
        )
        return (
            self.peak_vector_potential
            * self._envelope(time)
            * (carrier + from_the_envelope)
        )

    def momentum_shift(self, time_attosecond: float) -> float:
        """What an electron born at this time takes away, in atomic units.

        Minus the vector potential at that moment, and this is the one place in
        the model where that sign is written. The derivation is in the module
        docstring; the short form is that the electron's charge is negative, so
        the final momentum is the initial momentum minus the potential at birth.
        """
        return -self.vector_potential(time_attosecond)

    def energy_shift_electronvolt(
        self, kinetic_energy_electronvolt: float, time_attosecond: float
    ) -> float:
        """How much the streaking moves an electron of this kinetic energy.

        The full classical shift and not only the term that is linear in the
        potential. The linear term is what a streaking trace is read through and
        the quadratic term is what makes the trace's excursion asymmetric about
        the unstreaked energy, and dropping it is a choice this model does not
        make.
        """
        if kinetic_energy_electronvolt < 0.0:
            raise StreakingFieldRefused(
                f"The kinetic energy is {kinetic_energy_electronvolt} eV. An "
                "electron that has left carries a kinetic energy at or above "
                "zero, and a negative one has no momentum to shift."
            )
        kinetic_energy = electronvolts_to_hartree(kinetic_energy_electronvolt)
        momentum = sqrt(KINETIC_ENERGY_COEFFICIENT * kinetic_energy)
        shift = self.momentum_shift(time_attosecond)
        return hartree_to_electronvolts(
            momentum * shift + shift * shift / KINETIC_ENERGY_COEFFICIENT
        )

    def time_the_envelope_has_fallen_to_attosecond(self, fraction: float) -> float:
        """When the intensity envelope of the potential has fallen this far.

        Offered so that a caller asking whether the potential has gone can say
        how far gone it wants rather than taking a number this module chose. The
        answer is measured from the peak and is positive; the envelope is
        symmetric, so the same distance before the peak says the same thing.
        """
        if not 0.0 < fraction < 1.0:
            raise StreakingFieldRefused(
                f"The envelope was asked for the time it has fallen to {fraction} "
                "of its peak. A fraction of a peak lies strictly between zero and "
                "one: at one it is the peak, and it never reaches zero."
            )
        return atomic_time_to_attoseconds(
            sqrt(-log(fraction) / (GAUSSIAN_EXPONENT * self._envelope_rate))
        )


def _as_float(manifest: Manifest, name: str) -> float:
    """One parameter, as a float, refusing a value that is not a number.

    The same refusal the pulse makes, for the same reason: the manifest may hold
    a string for a parameter that is not a quantity, and a string survives some
    of the arithmetic below rather than failing at it.
    """
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StreakingFieldRefused(
            f"The parameter {name!r} is {value!r}, which is not a number. The "
            "streaking field takes quantities, and a manifest may hold strings "
            "and booleans for parameters that are not quantities."
        )
    return float(value)
