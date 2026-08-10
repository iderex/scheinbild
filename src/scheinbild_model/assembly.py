"""Several lines, over a delay scan, as one spectrogram.

The clean model. The neon 2s and 2p lines together over a delay scan and nothing
else: no satellites, no instrument response, no counting statistics. It is the
trace everything later is compared against, and it is the input the standard
analysis has to get exactly right before any contaminated result means anything.

## A fold over lines, never a pair

`assemble` takes a sequence of lines and adds their traces. It has no idea how
many there are and no case for two, and that is the whole reason it is written
this way: adding a satellite set is then adding rows to a data file rather than
changing the model. A two line special case here would make that change a
rewrite, and a rewrite is where a difference in summation order or accumulation
type moves the output in its last digits, which
../../docs/decisions/determinism-and-seeding.md rules out comparing away with a
tolerance.

`neon_main_lines` is the caller that supplies the two. It is a caller and not a
mode.

## A run names its own lines

`named_lines_spectrogram` is the general caller, and what it supplies comes out of the
manifest: which data files to read, and which lines out of them to assemble, in
the order they are summed. A run carrying a satellite set is then a manifest
naming another file and some more line names, and nothing here is rewritten for
it.

Both arrive as one string of names separated by spaces, because a manifest holds
numbers, strings and booleans and nothing else. That restriction is
../../docs/decisions/determinism-and-seeding.md's and it is what makes the choice
of lines part of the run: a set of lines held in the code is a value that
influences the output and is not in the description of the run, which is exactly
what the manifest type exists to make impossible.

The order the names are written in is not decoration. It fixes which line the
strengths are relative to and the order the traces are added in, and that
determinism record rules out comparing two runs that differ in their last digits
with a tolerance.

The file names are held against the files the package ships. A name that is not
one of them is refused rather than opened, so a run description cannot reach a
path on the host it happens to be running on.

## Where each of a line's numbers comes from

The binding energy and the cross section come from the atomic data file, with
their sources, per ../../docs/decisions/atomic-data.md. The intrinsic delay
comes from the manifest, per the same record: it is not well known, and a number
for it beside a cited binding energy would be a confidence the field does not
have.

The relative strength is derived rather than stored. It is this line's cross
section over the FIRST line of the assembly's cross section, both at the run's
own photon energy, which makes the first line's strength exactly one and every
other line's strength the ratio the analysis will be read against. The choice of
reference moves every strength by one common factor and moves no ratio, and the
absolute scale a scan is worth in counts is applied later and elsewhere.

## Why the strengths are compared as counts and not as peaks

The Done-when this module answers asks that the relative heights match the cross
section ratio, and "height" has to mean the counts a line carries rather than
the tallest bin of its trace. The peak of a streaking trace is set by how fast
the map is moving the line in energy at that delay, and that speed goes as the
line's momentum, which differs between two lines of different binding energy. So
two lines in exactly the cross section ratio have peak bins that are not, and a
test asserting on peaks would be asserting on the difference in momentum.

## The scan the assembler refuses

A delay scan shorter than a stated number of cycles of the streaking field. The
oscillation the analysis fits is the field's, so a scan covering less than a
cycle or so of it leaves that fit poorly conditioned: the amplitude, the phase
and the offset are being separated from a piece of a sine, and a piece of a sine
is nearly a straight line. The refusal states the number of cycles the scan
covers and the number it has to.

The number of cycles is a manifest parameter rather than a constant here,
because it changes what the model will accept and is therefore a value a run is
described by. The cycle it is measured in comes from the streaking field, so a
scan cannot supply the number it is judged against.

## What is not refused, said here rather than found later

A step that is a simple fraction of the period aliases, and nothing here refuses
it. The scan length has a bound that can be written down and a step does not:
whether a given step aliases depends on what is being fitted to the trace, which
is the standard analysis and is not in this package. A run that wants to know
scans at two steps and compares.

Nothing here says the two lines do not overlap. At the photon energies this
board works at they sit tens of electronvolts apart and their excursions are a
few, so the windows are clean, but that is a property of the numbers a run
chose and not of this module. The energy grid is refused only where it clips,
which `streaking_map` decides.
"""

from math import pi
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.atomic_data import EmissionLine, neon_main_lines, packaged
from scheinbild_model.manifest import Manifest
from scheinbild_model.pulse import Pulse
from scheinbild_model.spectrogram import Spectrogram
from scheinbild_model.streaking_field import StreakingField
from scheinbild_model.streaking_map import Line, trace
from scheinbild_model.units import atomic_time_to_attoseconds, electronvolts_to_hartree

DELAY_FIRST = "delay_scan_first_attosecond"
DELAY_STEP = "delay_scan_step_attosecond"
DELAY_POINTS = "delay_scan_points"

ENERGY_FIRST = "energy_grid_first_electronvolt"
ENERGY_STEP = "energy_grid_step_electronvolt"
ENERGY_POINTS = "energy_grid_points"

MINIMUM_CYCLES = "delay_scan_minimum_cycles"

# Which data files the run's lines are read out of, and which lines it assembles
# out of them, in the order they are summed. Both are one string of names
# separated by spaces, because a manifest holds numbers, strings and booleans and
# nothing else: a list has no rendering that is identical on every machine, and a
# value the canonical form cannot render is a value the digest cannot see. So a
# run that names its lines is a run the freeze record covers, which a list held
# in the code would not have been.
#
# One name is separated from the next by a space. Splitting on whitespace with no
# separator given collapses runs of it and drops the empty pieces at both ends,
# so a value written with a stray double space describes the same run as one
# written tidily, and a run description that differs only in that is not two runs.
LINE_SOURCES = "line_sources"
LINE_NAMES = "line_names"

# The two lines of the shipped data file, in the order they are assembled. The
# order decides which line the strengths are relative to and it decides the
# order the traces are summed in, and both of those are things a byte identical
# comparison can see, so it is written down rather than taken from whatever a
# mapping happens to iterate as.
NEON_MAIN_LINE_NAMES = ("2p", "2s")

# An axis needs two points before it has a spacing. The same statement the
# spectrogram type makes about its own axes, repeated here because these
# refusals happen while the axis is being built and the message that helps is
# the one naming the parameter that was wrong.
MINIMUM_AXIS_POINTS = 2

# Radians in one turn, over two: the carrier's angular frequency times its
# period is one full turn. Geometry rather than a measurement.
RADIANS_PER_TURN = 2.0


class AssemblyRefused(ValueError):
    """A scan or a grid was described that this assembler will not produce onto."""


def _positive_float(manifest: Manifest, name: str) -> float:
    """One parameter, as a positive finite float, or a refusal naming it."""
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssemblyRefused(
            f"The parameter {name!r} is {value!r}, which is not a number. A grid "
            "is described by quantities, and a manifest may hold strings and "
            "booleans for parameters that are not quantities."
        )
    number = float(value)
    if not number > 0.0:
        raise AssemblyRefused(
            f"The parameter {name!r} is {number}. A step of zero puts every point "
            "of an axis at the same place and a negative one runs the axis "
            "backwards, and both are read as a grid by everything downstream."
        )
    return number


def _points(manifest: Manifest, name: str) -> int:
    """One count of grid points, as a whole number, or a refusal naming it."""
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssemblyRefused(
            f"The parameter {name!r} is {value!r}. A number of grid points is a "
            "whole number, and a float here is a count arrived at by arithmetic "
            "somebody did not mean to do."
        )
    if value < MINIMUM_AXIS_POINTS:
        raise AssemblyRefused(
            f"The parameter {name!r} is {value}, and an axis needs at least "
            f"{MINIMUM_AXIS_POINTS} points before it has a spacing at all. A scan "
            "of one delay step is not a scan."
        )
    return value


def _axis(first: float, step: float, points: int) -> NDArray[np.float64]:
    """A uniform axis from its first point, its step and its length.

    Built as first plus index times step rather than by accumulating, so the
    spacing does not drift along the axis and the grid the spectrogram type
    checks for uniformity is uniform for a reason rather than by luck.
    """
    return first + step * np.arange(points, dtype=np.float64)


def delay_axis_attosecond(manifest: Manifest) -> NDArray[np.float64]:
    """The delay scan this run describes."""
    return _axis(
        _delay_first(manifest),
        _positive_float(manifest, DELAY_STEP),
        _points(manifest, DELAY_POINTS),
    )


def _delay_first(manifest: Manifest) -> float:
    """Where the scan starts. Any sign: a scan runs either side of the field."""
    value = manifest.parameter(DELAY_FIRST)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssemblyRefused(
            f"The parameter {DELAY_FIRST!r} is {value!r}, which is not a number."
        )
    return float(value)


def energy_axis_electronvolt(manifest: Manifest) -> NDArray[np.float64]:
    """The kinetic energy grid this run describes."""
    return _axis(
        _positive_float(manifest, ENERGY_FIRST),
        _positive_float(manifest, ENERGY_STEP),
        _points(manifest, ENERGY_POINTS),
    )


def streaking_period_attosecond(field: StreakingField) -> float:
    """One cycle of the streaking carrier, in attoseconds.

    Taken from the field's own photon energy. Public because a caller choosing a
    delay scan needs the number the scan will be judged against, and a caller
    that had to work it out would be free to work out a different one.
    """
    return atomic_time_to_attoseconds(
        RADIANS_PER_TURN
        * pi
        / electronvolts_to_hartree(field.photon_energy_electronvolt)
    )


def _refuse_a_scan_too_short_to_fit(
    manifest: Manifest, field: StreakingField, delays: NDArray[np.float64]
) -> None:
    """Refuse a delay scan covering less of the field's oscillation than asked."""
    minimum = _positive_float(manifest, MINIMUM_CYCLES)
    period = streaking_period_attosecond(field)
    span = float(delays[-1]) - float(delays[0])
    cycles = span / period
    if cycles < minimum:
        raise AssemblyRefused(
            f"The delay scan runs over {span} as, which is {cycles} cycle(s) of a "
            f"streaking field whose period is {period} as, and this run asks for "
            f"at least {minimum}. Below that the oscillation the analysis fits is "
            "a piece of a sine, and a piece of a sine is nearly a straight line: "
            "its amplitude, its phase and its offset stop being separable, so a "
            "delay read off it is a number the fit was free to choose. A scan of "
            f"{minimum * period} as or longer covers what this run asked for."
        )


def relative_strengths(
    entries: Mapping[str, EmissionLine],
    names: Sequence[str],
    photon_energy_electronvolt: float,
) -> tuple[float, ...]:
    """Each line's cross section as a fraction of the first line's.

    Derived here rather than stored in the data file, so the file stays
    comparable against the source it was copied from row by row, which is what
    ../../docs/decisions/atomic-data.md asks of it. The reference is the first
    name given: that puts a one in the first place and the ratio the analysis is
    read against in every other, and a different reference moves them all by one
    factor and moves no ratio between them.
    """
    if not names:
        raise AssemblyRefused(
            "No lines were named. A spectrogram assembled from nothing is an "
            "empty picture rather than a failure, and somebody has to notice it."
        )
    reference = _entry(entries, names[0])
    return tuple(
        _entry(entries, name)
        .tabulated_cross_section()
        .megabarn_at(photon_energy_electronvolt)
        / reference.tabulated_cross_section().megabarn_at(photon_energy_electronvolt)
        for name in names
    )


def _entry(entries: Mapping[str, EmissionLine], name: str) -> EmissionLine:
    try:
        return entries[name]
    except KeyError:
        raise AssemblyRefused(
            f"The run asks for the line {name!r} and the data file does not carry "
            f"it. The file holds: {sorted(entries)}. A line the model cannot read "
            "a binding energy for is not a line it can put anywhere."
        ) from None


def lines_of(
    manifest: Manifest, entries: Mapping[str, EmissionLine], names: Sequence[str]
) -> tuple[Line, ...]:
    """The lines this run assembles, from the data file and from the manifest."""
    photon_energy = Pulse(manifest).central_energy_electronvolt
    strengths = relative_strengths(entries, names, photon_energy)
    return tuple(
        Line.of(
            manifest,
            name,
            _entry(entries, name).binding_energy.electronvolt,
            strength,
        )
        for name, strength in zip(names, strengths)
    )


def assemble(manifest: Manifest, lines: Sequence[Line]) -> Spectrogram:
    """One spectrogram, as the sum of one trace per line.

    A fold over however many lines there are. The sum is taken in the order the
    lines were given, into one array, starting from zero: an order that is
    written down is an order two runs can agree on, and adding to zero is exact,
    so a two line assembly and the two traces added by hand are the same bytes
    rather than the same number to within a tolerance.
    """
    if not lines:
        raise AssemblyRefused(
            "No lines were given. A spectrogram assembled from nothing is an "
            "empty picture rather than a failure, and somebody has to notice it."
        )

    field = StreakingField(manifest)
    delays = delay_axis_attosecond(manifest)
    _refuse_a_scan_too_short_to_fit(manifest, field, delays)
    energies = energy_axis_electronvolt(manifest)

    counts = np.zeros((energies.size, delays.size), dtype=np.float64)
    for line in lines:
        counts += trace(manifest, line, energies, delays).counts

    return Spectrogram.of(
        counts=counts,
        energy_axis_electronvolt=energies,
        delay_axis_attosecond=delays,
        manifest=manifest,
    )


def neon_main_lines_spectrogram(manifest: Manifest) -> Spectrogram:
    """The neon 2s and 2p lines together, over the delay scan this run describes.

    The caller that supplies the two, and the only thing on this board that
    knows there are two of them. Everything it hands `assemble` is a sequence,
    so a run with a different set of lines is a different call and not a
    different assembler.
    """
    entries = neon_main_lines()
    return assemble(manifest, lines_of(manifest, entries, NEON_MAIN_LINE_NAMES))


def _names(manifest: Manifest, parameter: str) -> tuple[str, ...]:
    """One manifest parameter as the list of names it holds, or a refusal."""
    value = manifest.parameter(parameter)
    if not isinstance(value, str):
        raise AssemblyRefused(
            f"The parameter {parameter!r} is {value!r}, and it is read as a list "
            "of names separated by spaces. A manifest holds numbers, strings and "
            "booleans, because those are what render identically on every "
            "machine, so a list arrives as a string or it does not arrive."
        )
    names = tuple(value.split())
    if not names:
        raise AssemblyRefused(
            f"The parameter {parameter!r} names nothing. A run that names no "
            "lines assembles an empty picture rather than failing, and an empty "
            "picture is a result somebody has to notice by looking at it."
        )
    repeated = tuple(sorted({name for name in names if names.count(name) > 1}))
    if repeated:
        raise AssemblyRefused(
            f"The parameter {parameter!r} names {list(repeated)} more than once. "
            "The assembly sums what it is given in the order it is given, so a "
            "name written twice is a line at twice its strength, which is a "
            "picture that looks like a strong line rather than like a mistake."
        )
    return names


def line_sources(manifest: Manifest) -> tuple[str, ...]:
    """The atomic data files this run reads its lines out of."""
    return _names(manifest, LINE_SOURCES)


def line_names(manifest: Manifest) -> tuple[str, ...]:
    """The lines this run assembles, in the order they are summed.

    The order is part of the run rather than of the data file. It decides which
    line the relative strengths are taken against and it decides the order the
    traces are added in, and ../../docs/decisions/determinism-and-seeding.md
    rules out comparing two runs that differ in the last digits with a tolerance.
    """
    return _names(manifest, LINE_NAMES)


def merge(
    files: Sequence[tuple[str, Mapping[str, EmissionLine]]],
) -> Mapping[str, EmissionLine]:
    """Several data files as one mapping of lines, refusing a name both carry.

    Nothing about the merge says what kind of line came from which file. A name
    is looked up in what the run asked to read, and which file it was found in is
    not recorded anywhere the model can reach.

    A name two of the files both carry is refused rather than resolved by order.
    Two files holding one line is two sources for it, which
    ../../docs/decisions/atomic-data.md records as a disagreement inside an entry
    and never settles by letting one file win, and reading order is not a choice
    anybody made.
    """
    merged: dict[str, EmissionLine] = {}
    carried_by: dict[str, str] = {}
    for source, entries in files:
        for name, entry in entries.items():
            if name in merged:
                raise AssemblyRefused(
                    f"The line {name!r} is carried by {carried_by[name]!r} and by "
                    f"{source!r}, and this run reads both. Which of the two the "
                    "model would take is decided by reading order, which is not a "
                    "choice anybody made. Two files holding one line are two "
                    "sources for it, and a disagreement between sources is "
                    "recorded inside the entry rather than settled here."
                )
            merged[name] = entry
            carried_by[name] = source
    return MappingProxyType(merged)


def entries_for(manifest: Manifest) -> Mapping[str, EmissionLine]:
    """Every line the data files this run names carry, as one mapping.

    Read here rather than passed in, so that adding a set of lines to a run is
    adding a file name and some line names to its manifest.
    """
    return merge([(source, packaged(source)) for source in line_sources(manifest)])


def named_lines_spectrogram(manifest: Manifest) -> Spectrogram:
    """The lines this run names, over the delay scan it describes.

    The general caller. It reads which files to open and which lines to assemble
    out of the manifest, so a run carrying a different set of lines is a
    different manifest and not different code, and every line it assembled is in
    the description the freeze record hashes.
    """
    return assemble(
        manifest, lines_of(manifest, entries_for(manifest), line_names(manifest))
    )
