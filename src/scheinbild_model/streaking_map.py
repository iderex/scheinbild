"""One emission line, as one streaking trace.

The classical streaking map. An electron born at a time inside the ionising
pulse leaves with the momentum it would have had, shifted by the vector
potential at that moment, and the trace is the ionising pulse intensity
distributed over final energy according to that shift.

Everything the map needs about a line is a binding energy, a relative strength
and an intrinsic delay. Nothing here asks what kind of line it is, which is the
arrangement ../../docs/decisions/satellite-lines.md keeps.

## The delay is put in, not worked out

The intrinsic delay is a plain input parameter. This module knows the true delay
of a line because the operator wrote it into the manifest, and everything the
standard analysis later extracts is measured against that value. The reason the
core takes the delay rather than computing it is argued in
../../docs/decisions/physics-core.md, and it is the whole reason this board can
tell a right answer from a wrong one.

Like every other parameter of this model, it is read through the manifest or it
is not read at all. There is no default and no second source.

## Two times, and which one the delay axis is

There are two clocks here and confusing them inverts a result.

`t` is a birth time inside the ionising pulse, measured from that pulse's own
peak. It runs over the pulse's time grid and the weight at each point is the
pulse's intensity envelope there.

`delay` is the peak of the IONISING pulse, measured from the peak of the
STREAKING field. It is the axis a delay scan runs along.

So an electron of a line whose intrinsic delay is `d`, born at `t`, samples the
streaking field at

    delay + t + d

in the field's own time coordinate, and that is the one place the three are put
together. Read straight off that expression: the centre of energy against delay
follows the potential unmirrored, and a line with a LARGER intrinsic delay
produces the same trace at an EARLIER delay, because the extra `d` has already
carried it to the same moment of the field. `trace` of a line with delay `d`
evaluated at `delay` is `trace` of the same line with delay zero evaluated at
`delay + d`, exactly, and the suite asserts that equality rather than describing
it.

## The energy, and what it is measured from

An electron of a line whose binding energy is `b`, ionised by a photon of energy
`h`, leaves with `h - b` before the streaking field touches it. The shift the
field adds comes from `streaking_field.energy_shift_electronvolt`, which is
where the sign of the map is decided and where it stays decided: nothing in this
module writes a minus in front of a potential.

## Distributing onto the energy grid

Each birth time carries its weight to one final energy, which in general falls
between two grid points. The weight is split between the two in proportion to
how far it sits from each. That is the choice with the property this issue's
evidence rests on: splitting linearly conserves the total weight AND its first
moment exactly, so the centre of energy of the trace is the intensity weighted
mean of the energies the map produced, to floating point rather than to within a
bin. Rounding to the nearest bin would conserve the total and move the centre by
up to half a bin, in a direction that depends on where the grid happens to sit.

## What runs off the grid, and why the totals will not tell you

Handed an energy outside the grid the split above does not stop. It extrapolates
past the end, putting more than the whole weight on the outermost bin and a
negative amount on the bin beside it, and doing so preserves both the total and
the first moment, which is exactly what makes it dangerous. An overshoot of half
a bin moves the column totals and the centre of energy by about 1e-15 and 1e-13
respectively, measured, so a run that lost part of its trace off the axis would
show nothing wrong in either of the numbers this model is read through.

What is wrong is that expected counts then sit at energies no electron of this
line reached, and one of them is negative, which has nothing to be Poisson
about. Far enough off the axis the negative wins and `Spectrogram.of` refuses
the array, so it is not silent all the way down; but the message a reader gets
there names a negative expectation and not an energy axis that is too narrow.

So a grid that does not hold every energy this map produces is refused here,
where the reason is still known, and the refusal names the range that would hold
it. `energy_span_electronvolt` answers the same question before a caller has
built a grid at all.

## What is not refused here, said now rather than found later

How finely the birth time grid is sampled is not judged. A grid coarse enough
that neighbouring birth times land several energy bins apart produces a comb of
spikes rather than a distribution, and the total counts and the centre of energy
of that comb are still right, so no property this module checks would notice. It
is a parameter of the run, it is in the manifest, and choosing it too coarse is
visible in the trace itself.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest
from scheinbild_model.pulse import Pulse
from scheinbild_model.spectrogram import Spectrogram
from scheinbild_model.streaking_field import StreakingField

# How many birth times the ionising pulse is sampled at, across the whole of the
# time grid the pulse describes. A parameter of the run rather than a constant,
# because it changes the output and a value that changes the output is in the
# manifest.
BIRTH_TIME_POINTS = "streaking_map_birth_time_points"

# What every line in a manifest is asked for, under its own name. A line called
# "2p" carries `line_2p_binding_energy_electronvolt` and the other two beside
# it. Written as a prefix and three suffixes rather than as a fixed set of
# names, so that a run carrying a different set of lines is a different manifest
# and not different code.
LINE_PREFIX = "line_"
BINDING_ENERGY = "binding_energy_electronvolt"
RELATIVE_STRENGTH = "relative_strength"
INTRINSIC_DELAY = "intrinsic_delay_attosecond"

# A birth time grid needs two points before it has a step at all, and one point
# is not a sampled pulse. A count of points rather than a quantity.
MINIMUM_BIRTH_TIME_POINTS = 2

# A deposit is split between the two grid points either side of it, so the lower
# of the pair is never the last point of the axis. A count of bins rather than a
# quantity.
BINS_PER_DEPOSIT = 2


class StreakingMapRefused(ValueError):
    """A trace was asked for that the map cannot produce onto the grid it was given."""


@dataclass(frozen=True)
class Line:
    """One emission channel, as the forward model computes with it.

    A binding energy, a relative strength and an intrinsic delay. There is no
    field saying whether this is a main line or a satellite, and there will not
    be one: a model that could tell them apart is a model whose output carries a
    marker the real measurement does not have.
    """

    name: str
    binding_energy_electronvolt: float
    relative_strength: float
    intrinsic_delay_attosecond: float

    @classmethod
    def of(cls, manifest: Manifest, name: str) -> "Line":
        """The line of this name, out of the manifest, or a refusal.

        The intrinsic delay is deliberately unconstrained in sign. A line that
        emits before the one it is measured against is the case this board
        exists to be able to represent, and a refusal of a negative delay would
        quietly halve what can be asked.
        """
        binding_energy = _as_float(manifest, name, BINDING_ENERGY)
        strength = _as_float(manifest, name, RELATIVE_STRENGTH)

        if binding_energy <= 0.0:
            raise StreakingMapRefused(
                f"The line {name!r} has a binding energy of {binding_energy} eV. "
                "A binding energy is the work it takes to remove the electron "
                "and is positive; a negative one here is a sign convention taken "
                "from the kinetic energy side, which would put the line at the "
                "wrong end of the axis rather than fail."
            )
        if strength <= 0.0:
            raise StreakingMapRefused(
                f"The line {name!r} has a relative strength of {strength}. A "
                "line with no strength contributes nothing and a line with a "
                "negative one contributes negative expected counts, which have "
                "nothing to be Poisson about. A run that does not want a line "
                "leaves it out."
            )

        return cls(
            name=name,
            binding_energy_electronvolt=binding_energy,
            relative_strength=strength,
            intrinsic_delay_attosecond=_as_float(manifest, name, INTRINSIC_DELAY),
        )


def parameter_name(line_name: str, quantity: str) -> str:
    """What one quantity of one line is called in a manifest.

    Public because a caller writing a manifest and this module reading one have
    to agree on the spelling, and two places that build the same string are two
    places that can stop agreeing.
    """
    return f"{LINE_PREFIX}{line_name}_{quantity}"


def _as_float(manifest: Manifest, line_name: str, quantity: str) -> float:
    """One of a line's quantities, as a float, refusing what is not a number."""
    name = parameter_name(line_name, quantity)
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StreakingMapRefused(
            f"The parameter {name!r} is {value!r}, which is not a number. A line "
            "is described by quantities, and a manifest may hold strings and "
            "booleans for parameters that are not quantities."
        )
    return float(value)


def _birth_time_points(manifest: Manifest) -> int:
    """How many birth times the pulse is sampled at, refusing too few."""
    value = manifest.parameter(BIRTH_TIME_POINTS)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StreakingMapRefused(
            f"The parameter {BIRTH_TIME_POINTS!r} is {value!r}. A number of grid "
            "points is a whole number, and a float here is a count that was "
            "arrived at by arithmetic somebody did not mean to do."
        )
    if value < MINIMUM_BIRTH_TIME_POINTS:
        raise StreakingMapRefused(
            f"The pulse is sampled at {value} birth time(s), and it takes at "
            f"least {MINIMUM_BIRTH_TIME_POINTS} before the grid has a step at "
            "all. A pulse sampled at one point is a single electron leaving at "
            "the peak, which has a streaking shift and no width."
        )
    return value


def unstreaked_energy_electronvolt(pulse: Pulse, line: Line) -> float:
    """What this line's electrons leave with before the streaking field acts.

    The photon energy less the binding energy. Public because it is where a
    line sits on the energy axis with the streaking off, which is what a caller
    choosing an energy grid needs to know before it can choose one.
    """
    energy = pulse.central_energy_electronvolt - line.binding_energy_electronvolt
    if energy <= 0.0:
        raise StreakingMapRefused(
            f"The line {line.name!r} has a binding energy of "
            f"{line.binding_energy_electronvolt} eV and the ionising pulse "
            f"carries {pulse.central_energy_electronvolt} eV, which leaves "
            f"{energy} eV of kinetic energy. This photon does not open this "
            "channel, so there is no trace to produce rather than an empty one."
        )
    return energy


def _birth_times(pulse: Pulse, points: int) -> NDArray[np.float64]:
    """The times the pulse is sampled at, across the grid it describes.

    The grid half width is the pulse's own, which `Pulse` has already refused to
    build where the envelope does not fit inside it. So the birth times reach as
    far as the ionising pulse does and no further, and this module does not
    decide again what "as far as the pulse reaches" means.
    """
    half_width = pulse.time_grid_half_width_attosecond
    return np.linspace(-half_width, half_width, points, dtype=np.float64)


def _final_energies(
    pulse: Pulse,
    field: StreakingField,
    line: Line,
    birth_times_attosecond: NDArray[np.float64],
    delay_axis_attosecond: NDArray[np.float64],
) -> NDArray[np.float64]:
    """The energy each birth time lands at, at each delay of the scan.

    One row per birth time and one column per delay, which is the order the
    weights broadcast along and not the order a spectrogram is stored in.

    The shift is asked for one value at a time rather than derived again here.
    `streaking_field` is where the sign of the map lives, and a second
    expression for it in this module is a second place it can be got wrong.
    """
    unstreaked = unstreaked_energy_electronvolt(pulse, line)

    energies = np.empty(
        (birth_times_attosecond.size, delay_axis_attosecond.size), dtype=np.float64
    )
    for row, birth in enumerate(birth_times_attosecond.tolist()):
        for column, delay in enumerate(delay_axis_attosecond.tolist()):
            energies[row, column] = unstreaked + field.energy_shift_electronvolt(
                unstreaked, delay + birth + line.intrinsic_delay_attosecond
            )
    return energies


def energy_span_electronvolt(
    manifest: Manifest, line: Line, delay_axis_attosecond: NDArray[np.float64]
) -> tuple[float, float]:
    """The lowest and the highest energy this line reaches over this scan.

    What an energy grid has to hold, so that a caller choosing one can ask
    rather than guess and then be refused. It is the map's own answer and not an
    estimate of it: the same energies the trace is built from, at their two
    extremes, so an axis running from the first of these to the second holds the
    trace with nothing to spare and nothing missing.
    """
    pulse = Pulse(manifest)
    energies = _final_energies(
        pulse,
        StreakingField(manifest),
        line,
        _birth_times(pulse, _birth_time_points(manifest)),
        np.asarray(delay_axis_attosecond, dtype=np.float64),
    )
    return float(energies.min()), float(energies.max())


def _refuse_a_grid_that_clips(
    energies: NDArray[np.float64], energy_axis_electronvolt: NDArray[np.float64]
) -> None:
    """Refuse an energy grid that does not hold every energy the map produced."""
    lowest = float(energies.min())
    highest = float(energies.max())
    first = float(energy_axis_electronvolt[0])
    last = float(energy_axis_electronvolt[-1])
    if lowest < first or highest > last:
        raise StreakingMapRefused(
            f"The streaking excursion carries this line from {lowest} eV to "
            f"{highest} eV and the energy axis runs from {first} eV to {last} "
            "eV, so part of the trace falls off the grid. Refused here rather "
            "than left to be noticed downstream: the deposition extrapolates "
            "past the end of an axis and keeps the totals right while doing it, "
            "so the counts and the centre of energy of a clipped trace look "
            "exactly like those of a good one. An axis covering "
            f"{lowest} eV to {highest} eV holds this line at this intensity."
        )


def _deposit(
    counts: NDArray[np.float64],
    energy_axis_electronvolt: NDArray[np.float64],
    energies: NDArray[np.float64],
    weights: NDArray[np.float64],
) -> None:
    """Split each birth time's weight between the two grid points either side.

    Linear in the distance to each, which conserves the total weight and its
    first moment. Called after the grid has been shown to hold every energy, so
    every deposit lands on the axis.
    """
    first = float(energy_axis_electronvolt[0])
    points = energy_axis_electronvolt.size
    # The mean spacing rather than a difference of neighbours. The axis has
    # already been through `Spectrogram.of`, which is where uniformity is
    # decided, and the mean is the value that agrees with the whole axis rather
    # than with its first pair.
    spacing = (float(energy_axis_electronvolt[-1]) - first) / (points - 1)

    position = (energies - first) / spacing
    lower = np.clip(np.floor(position).astype(np.intp), 0, points - BINS_PER_DEPOSIT)
    fraction = position - lower

    delay_index = np.broadcast_to(np.arange(counts.shape[1]), energies.shape)
    share = weights[:, np.newaxis]
    np.add.at(counts, (lower, delay_index), share * (1.0 - fraction))
    np.add.at(counts, (lower + 1, delay_index), share * fraction)


def trace(
    manifest: Manifest,
    line: Line,
    energy_axis_electronvolt: NDArray[np.float64],
    delay_axis_attosecond: NDArray[np.float64],
) -> Spectrogram:
    """The streaking trace of one line, over a delay scan.

    Expected counts, summing to the line's relative strength at every delay
    step. The absolute scale is not applied here: what a scan is worth in counts
    is a separate parameter and a separate stage, so a trace carries only how
    strong this line is against the others.
    """
    pulse = Pulse(manifest)
    field = StreakingField(manifest)
    points = _birth_time_points(manifest)

    counts = np.zeros(
        (np.shape(energy_axis_electronvolt) + np.shape(delay_axis_attosecond)),
        dtype=np.float64,
    )
    # The axes go through the spectrogram before anything is deposited on them.
    # The arithmetic below assumes a one dimensional, increasing, uniform grid,
    # and where that is decided is `Spectrogram.of`; deciding it a second time
    # here would be a second rule to keep in step with the first.
    checked = Spectrogram.of(
        counts=counts,
        energy_axis_electronvolt=energy_axis_electronvolt,
        delay_axis_attosecond=delay_axis_attosecond,
        manifest=manifest,
    )
    energy_axis = checked.energy_axis_electronvolt
    delay_axis = checked.delay_axis_attosecond

    birth_times = _birth_times(pulse, points)
    envelope = np.array(
        [pulse.intensity_envelope(birth) for birth in birth_times.tolist()],
        dtype=np.float64,
    )
    weights = line.relative_strength * envelope / envelope.sum()

    energies = _final_energies(pulse, field, line, birth_times, delay_axis)
    _refuse_a_grid_that_clips(energies, energy_axis)
    _deposit(counts, energy_axis, energies, weights)

    return Spectrogram.of(
        counts=counts,
        energy_axis_electronvolt=energy_axis,
        delay_axis_attosecond=delay_axis,
        manifest=manifest,
    )


def centre_of_energy_electronvolt(spectrogram: Spectrogram) -> NDArray[np.float64]:
    """The centre of energy at each delay step.

    The quantity a streaking trace is read through, here rather than written out
    again at each place that wants one. It sits beside the map rather than on
    the spectrogram type because it is what this map's own evidence is stated
    in; a spectrogram is a container and this is a reading of one.

    A delay step with no counts in it has no centre of energy, and this refuses
    rather than returning the zero over zero that arithmetic would give.
    """
    totals = spectrogram.counts.sum(axis=0)
    if not np.all(totals > 0.0):
        raise StreakingMapRefused(
            "A delay step of this spectrogram carries no counts at all, so it "
            "has no centre of energy. An empty column is what a trace that fell "
            "entirely off its grid looks like, and a centre of energy computed "
            "from it would be a number rather than an error."
        )
    weighted = spectrogram.energy_axis_electronvolt @ spectrogram.counts
    centre: NDArray[np.float64] = weighted / totals
    return centre
