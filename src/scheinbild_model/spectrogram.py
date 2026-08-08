"""The spectrogram, and the states it refuses to exist in.

Intensity over kinetic energy and pulse delay, with both axes travelling with
the array and the manifest that produced it travelling with both. The decision
this implements is in ../../docs/decisions/spectrogram-type.md, which fixes the
axis order, the units, the uniform grids and the metadata the object may not
exist without.

## Refusing at construction rather than checking at use

A spectrogram that is wrong in the shape of its axes produces a picture that
looks right and a number that is wrong. By the time the number is wrong the
construction site is far away, and the reader is holding a plausible figure with
nothing on it to say which half of the pipeline to distrust. So every
consistency rule is decided once, at the moment the object comes into being, and
an object that exists has already passed all of them.

That only holds if there is one way in. `of` is the only constructor, its
arguments are keyword only, and every argument carrying a physical quantity has
its unit in its name. A caller who transposes the array has to write
`energy_axis_electronvolt=` in front of a delay axis to do it.

## What it cannot catch, said here rather than found later

A unit error that is a clean factor is invisible to this object. An energy axis
handed over in hartree rather than electronvolts is a set of positive, finite,
sorted, uniformly spaced numbers, and so is the correct one. Nothing here can
tell them apart, and nothing here claims to.

What stands against that is not this file. It is that the conversions live in
one module and nowhere else, and that the unit is written into the name of every
argument and attribute here, so the mistake has to survive being spelled out.
A future check comparing an axis against the manifest that produced it could go
further; none exists today.

## The operations

The three that everything downstream needs are here rather than rewritten
slightly differently in each place that wants one. The index of an energy, a
window over an energy range, and the total counts. Written once, a window that
is off by one bin is off by one bin in exactly one place.
"""

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest

# How far a spacing may drift from the mean spacing and still count as uniform.
# Relative, because the two axes are on different scales and an absolute
# tolerance would be strict on one and meaningless on the other.
#
# The value is set by what produces a real axis rather than by taste. An axis
# built with a floating point range accumulates a rounding error of a few units
# in the last place across its length, which is around 1e-13 relative for a grid
# of the sizes this board uses. A tolerance of 1e-9 admits that and refuses a
# grid whose spacing genuinely varies, since the smallest deliberate
# non-uniformity anybody would write is many orders of magnitude coarser.
UNIFORM_SPACING_TOLERANCE = 1e-9

# An axis needs two points before it has a spacing at all, and a spectrogram
# with one delay step is not a scan.
MINIMUM_AXIS_LENGTH = 2


class SpectrogramRefused(ValueError):
    """A spectrogram was asked to exist in a state it may not exist in.

    One exception type for every rule, because the caller's response is the same
    in each case, and the message carries which rule it was.
    """


def _as_axis(name: str, values: object) -> NDArray[np.float64]:
    """One axis, as an array of floats, refusing what an axis may not be."""
    axis = np.asarray(values, dtype=np.float64)

    if axis.ndim != 1:
        raise SpectrogramRefused(
            f"{name} has {axis.ndim} dimensions. An axis is one dimensional, and "
            "an axis that is not is a shape mistake that would otherwise be "
            "found by a broadcast doing something plausible."
        )
    if axis.size < MINIMUM_AXIS_LENGTH:
        raise SpectrogramRefused(
            f"{name} has {axis.size} point(s). An axis needs at least "
            f"{MINIMUM_AXIS_LENGTH} before it has a spacing, and a scan with one "
            "step is not a scan."
        )
    if not np.all(np.isfinite(axis)):
        raise SpectrogramRefused(
            f"{name} carries a value that is not finite. A grid point that is "
            "not a number propagates into every later transform and arrives as "
            "an empty region of a picture rather than as an error."
        )

    steps = np.diff(axis)
    if not np.all(steps > 0.0):
        raise SpectrogramRefused(
            f"{name} is not strictly increasing. A sorted axis is what makes a "
            "lookup and a window mean what they say, and an axis that is merely "
            "unsorted gives both of them a wrong answer rather than an error."
        )

    mean_step = float(steps.mean())
    drift = float(np.max(np.abs(steps - mean_step)))
    if drift > abs(mean_step) * UNIFORM_SPACING_TOLERANCE:
        raise SpectrogramRefused(
            f"{name} is not uniform. Its largest departure from the mean spacing "
            f"of {mean_step} is {drift}, and the tolerance is "
            f"{UNIFORM_SPACING_TOLERANCE} of the spacing. The analysis transforms "
            "along the delay axis, and a non uniform grid silently changes what "
            "that transform means. See docs/decisions/spectrogram-type.md."
        )

    return axis


class Spectrogram:
    """Expected counts over a kinetic energy axis and a pulse delay axis.

    Energy is the first axis and delay is the second, which is stated in
    ../../docs/decisions/spectrogram-type.md so that a transposed array is a
    disagreement with a written rule rather than a matter of opinion.

    The value is expected counts. Not a normalised probability and not an
    arbitrary intensity scale, because the counting statistics downstream need a
    number to be Poisson about and a normalised array has thrown that number
    away.
    """

    __slots__ = (
        "counts",
        "delay_axis_attosecond",
        "energy_axis_electronvolt",
        "manifest",
    )

    def __init__(
        self,
        counts: NDArray[np.float64],
        energy_axis_electronvolt: NDArray[np.float64],
        delay_axis_attosecond: NDArray[np.float64],
        manifest: Manifest,
    ) -> None:
        # Not the way in. `of` is, and it is what applies the rules. This takes
        # what `of` has already checked, so that there is one place where a
        # spectrogram becomes valid rather than two that have to agree.
        self.counts = counts
        self.energy_axis_electronvolt = energy_axis_electronvolt
        self.delay_axis_attosecond = delay_axis_attosecond
        self.manifest = manifest

    @classmethod
    def of(
        cls,
        *,
        counts: object,
        energy_axis_electronvolt: object,
        delay_axis_attosecond: object,
        manifest: Manifest,
    ) -> "Spectrogram":
        """The only way to make one. Every rule is decided here.

        Keyword only, and every physical argument carries its unit in its name.
        A caller transposing the array has to write the energy keyword in front
        of a delay axis, which is a different kind of mistake from passing two
        arrays in the wrong order.
        """
        energy = _as_axis("The energy axis", energy_axis_electronvolt)
        delay = _as_axis("The delay axis", delay_axis_attosecond)

        if np.any(energy < 0.0):
            raise SpectrogramRefused(
                "The energy axis carries a negative value. These are kinetic "
                "energies in electronvolts and a kinetic energy is not negative. "
                "This catches a sign convention taken from the binding energy "
                "side; it does not catch an axis handed over in another unit, "
                "which this module says in its own words."
            )

        array = np.asarray(counts, dtype=np.float64)

        if array.ndim != 2:
            raise SpectrogramRefused(
                f"The intensity array has {array.ndim} dimensions. A spectrogram "
                "is two dimensional, energy first and delay second."
            )
        if array.shape[0] != energy.size:
            raise SpectrogramRefused(
                f"The array's first dimension is {array.shape[0]} and the energy "
                f"axis has {energy.size} points. Energy is the first axis, so a "
                "disagreement here is either a transposed array or an axis built "
                "from a different grid, and both produce a picture that looks "
                "right. See docs/decisions/spectrogram-type.md."
            )
        if array.shape[1] != delay.size:
            raise SpectrogramRefused(
                f"The array's second dimension is {array.shape[1]} and the delay "
                f"axis has {delay.size} points. Delay is the second axis."
            )
        if not np.all(np.isfinite(array)):
            raise SpectrogramRefused(
                "The intensity array carries a value that is not finite. An "
                "expected count that is not a number cannot be drawn from and "
                "would reach the counting statistics as a silently empty bin."
            )
        if np.any(array < 0.0):
            raise SpectrogramRefused(
                "The intensity array carries a negative value. These are "
                "expected counts, and a negative expectation has nothing to be "
                "Poisson about."
            )

        return cls(array, energy, delay, manifest)

    def energy_index(self, energy_electronvolt: float) -> int:
        """The index of the bin nearest a given energy.

        Nearest rather than the first at or above, because a caller asking for
        an energy is asking where it sits, and rounding one way at every call
        site is a half bin of bias that nobody would notice.
        """
        axis = self.energy_axis_electronvolt
        if not axis[0] <= energy_electronvolt <= axis[-1]:
            raise SpectrogramRefused(
                f"{energy_electronvolt} eV is outside the energy axis, which "
                f"runs from {axis[0]} to {axis[-1]} eV. Clamping to the nearest "
                "end would return an index that looks like an answer."
            )
        return int(np.argmin(np.abs(axis - energy_electronvolt)))

    def energy_window(self, low_electronvolt: float, high_electronvolt: float) -> slice:
        """A slice over an energy range, inclusive of both ends.

        Returned as a slice rather than as a copied array so that a caller can
        apply it to the counts or to the axis and get halves that agree. Both
        ends are inclusive, and that is written here because half open and
        closed are the off-by-one this window exists to have in one place.
        """
        if high_electronvolt < low_electronvolt:
            raise SpectrogramRefused(
                f"The window runs from {low_electronvolt} to "
                f"{high_electronvolt} eV, which is backwards. A window built "
                "from a centre and a half width with the sign wrong is empty "
                "rather than wrong, and an empty window sums to zero counts."
            )
        first = self.energy_index(low_electronvolt)
        last = self.energy_index(high_electronvolt)
        return slice(first, last + 1)

    def total_counts(self) -> float:
        """Every expected count in the spectrogram, summed."""
        return float(self.counts.sum())
