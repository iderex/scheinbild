"""The atomic data the model reads, and what every number in it carries.

The binding energies and photoionisation cross sections of the neon lines are
not in the constant table beside this module and they are not in any module at
all. They are in a data file, one row per line, and the reason is in
../../docs/decisions/atomic-data.md: a reader who holds a different value for a
cross section has to be able to change it and re-run, and a number compiled into
a module is a number only its author can disagree with.

What this module is, then, is the loader for that file and nothing else. It
holds no value, and the one thing it decides on its own is how a cross section
between two tabulated photon energies is obtained, which the file names and this
module refuses to guess at.

## What a row carries, and why it is three fields rather than one

Every number carries the source it was taken from, how that source's terms were
understood, and whether the number was measured or calculated.

The terms field is not tidiness. The values here come from published tables
whose terms differ, and whether a number may be shipped in a public repository
at all is a question per source: some are freely redistributable, some permit
use but not redistribution of the compiled table. One answer for the whole file
would be wrong for part of it.

So where the terms permit it the entry carries the value, and where they do not
it carries the citation and a `fetch` step in place of the number. Both shapes
load; a row carrying neither, or both, does not.

The method field is what separates a level somebody sat down and measured from
one that fell out of a calculation, and the two do not deserve the same weight
in a result. Averaging across the pair would hide exactly the difference a
reader wants to see, which is why the third field exists rather than a footnote.

## Where sources disagree, both stand

A quantity may carry a `disagreement` beside it: another source, its own terms,
its own method, and either its value or the step that fetches it. The spread
across sources is itself an input to how much confidence a result deserves, so
it is recorded rather than averaged away, and nothing here reduces a pair to a
single number.

## The strength of a line, and the two shapes it comes in

A source either tabulates a photoionisation cross section in megabarn, as the
main line tables do, or it reports a strength relative to a main line, which is
what the satellite literature reports. An entry carries whichever of the two its
source tabulates, and exactly one of them, so the file stays comparable against
that source row by row.

Neither shape says what kind of line this is. A main line whose source reported
a ratio would load through the second shape and a satellite whose source
tabulated megabarn would load through the first, so nothing here tells the model
which of its lines are satellites.

## What the loader refuses

A row with no source, which is the rule the decision record puts first. A row
with no statement of terms, for the reason above. A row that does not say
whether its number was measured or calculated. A table whose photon energies do
not increase, because the interpolation below reads neighbours and a table that
doubles back has two of them. A value at or below zero, which is neither a
physical cross section nor a strength, and is also not a number a logarithm can
be taken of. A photon energy outside the tabulated range, because extending a
table past its ends is inventing a number rather than reading one. And an
intrinsic delay written anywhere into a data file, because that is a run
parameter and a number for it here would be a confidence the field does not
have.

Refused at load rather than where the value is used, so that a file whose
provenance was going to be completed later stops the run that reads it.
"""

import tomllib
from bisect import bisect_left
from dataclasses import dataclass
from importlib.resources import files
from math import exp, isfinite, log
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Union

# Where the packaged file sits. A file inside the package rather than beside the
# repository, so that a reader who installed this project has the data the model
# reads and not a path that only exists in a checkout.
DATA_DIRECTORY = "data"

NEON_MAIN_LINES = "neon-main-lines.toml"

NEON_2P_SHAKE_UP_SATELLITES = "neon-2p-shake-up-satellites.toml"

# How a number was arrived at. A measurement and a calculation are different
# claims about the world and a file that could not tell them apart would let a
# reader weigh them the same.
MEASURED = "measured"
CALCULATED = "calculated"
METHODS = (MEASURED, CALCULATED)

# The word a data file may not build a field name out of. The intrinsic delay of
# a line is a run parameter, so it arrives through the manifest and a number for
# it in a data file would be a value the freeze record never sees. Matched on
# the name rather than on a fixed list of spellings, because `delay`,
# `intrinsic_delay` and `delay_attosecond` are the same mistake.
DELAY = "delay"

# A straight line between neighbouring points in the logarithm of the photon
# energy and the logarithm of the cross section. The argument for it, and the
# measurement it was chosen on, are in the file's own header and in
# ../../docs/decisions/atomic-data.md.
LINEAR_IN_THE_LOGARITHMS = "linear-in-log-photon-energy-and-log-cross-section"

# Every method a file may name. There is no default: the value the model uses at
# a photon energy between two rows is a product of the table and of this choice
# together, so a file that did not say which it wanted cannot be read afterwards.
INTERPOLATIONS = (LINEAR_IN_THE_LOGARITHMS,)


class AtomicDataRefused(ValueError):
    """A data file was offered that the model may not read a number out of."""


@dataclass(frozen=True)
class Disagreement:
    """What a second source says about a number the file already carries.

    Kept beside the value rather than resolved into it. Two sources that differ
    are two claims, and the distance between them is what says how much the
    number deserves to be trusted; an average is one number with that
    information deleted and nothing on its face admitting the deletion.

    Carries a value where its own terms permit one and the step that retrieves
    it where they do not, which is the same pair of shapes the quantity it
    disagrees with may take.
    """

    source: str
    terms: str
    method: str
    value: Optional[float]
    fetch: Optional[str]


def _between_the_logarithms(
    grid: Sequence[float], values: Sequence[float], at: float, quantity: str
) -> float:
    """One value off a table, interpolated the way the file says it is.

    A straight line between neighbouring points in the logarithm of the photon
    energy and the logarithm of the value. Shared by the two tabulated shapes
    below, so that a strength and a cross section between two rows are obtained
    by one rule rather than by two that could drift apart.

    Exact at a tabulated point, and exact in the arithmetic rather than within a
    tolerance: a photon energy that is in the table is answered by reading the
    table, so the round trip through two logarithms and an exponential never
    happens and cannot move the last place.
    """
    if not grid[0] <= at <= grid[-1]:
        raise AtomicDataRefused(
            f"The {quantity} was asked for at {at} eV and this table runs from "
            f"{grid[0]} eV to {grid[-1]} eV. Continuing the table past its ends "
            "is inventing a number rather than reading one, and neither of these "
            "quantities is a straight line anywhere: below the first row there is "
            "a threshold and above the last it falls by decades. Add the rows the "
            "run needs, with their source, rather than extending these."
        )
    index = bisect_left(grid, at)
    if grid[index] == at:
        return values[index]
    below = index - 1
    span = log(grid[index]) - log(grid[below])
    along = (log(at) - log(grid[below])) / span
    rise = log(values[index]) - log(values[below])
    return exp(log(values[below]) + along * rise)


@dataclass(frozen=True)
class CitedEnergy:
    """One energy, with where it came from, under what terms and how."""

    electronvolt: float
    source: str
    terms: str
    method: str
    disagreements: tuple[Disagreement, ...] = ()


@dataclass(frozen=True)
class CrossSectionTable:
    """A subshell cross section against photon energy, as the source tabulates it."""

    photon_energy_electronvolt: tuple[float, ...]
    megabarn: tuple[float, ...]
    source: str
    terms: str
    method: str
    disagreements: tuple[Disagreement, ...] = ()

    def megabarn_at(self, photon_energy_electronvolt: float) -> float:
        """The cross section at one photon energy, interpolated between rows."""
        return _between_the_logarithms(
            self.photon_energy_electronvolt,
            self.megabarn,
            photon_energy_electronvolt,
            "cross section",
        )


@dataclass(frozen=True)
class RelativeStrengthTable:
    """A line's strength against a main line, as the source reports it.

    The shape the satellite literature comes in. A shake up satellite has no
    tabulated photoionisation cross section in megabarn anywhere; what is
    reported is how strong it is beside the main line it accompanies, at the
    photon energy the report was made at. So the file carries that, and carries
    the photon energies it applies to, because the ratio moves with photon
    energy and a single number would be one run's answer written as if it were
    every run's.
    """

    photon_energy_electronvolt: tuple[float, ...]
    strength: tuple[float, ...]
    source: str
    terms: str
    method: str
    disagreements: tuple[Disagreement, ...] = ()

    def strength_at(self, photon_energy_electronvolt: float) -> float:
        """The strength at one photon energy, interpolated between rows."""
        return _between_the_logarithms(
            self.photon_energy_electronvolt,
            self.strength,
            photon_energy_electronvolt,
            "relative strength",
        )


@dataclass(frozen=True)
class FetchStep:
    """A number this repository cites and does not carry.

    What stands in the file where a value would be, when the source's terms do
    not permit the compiled table to be redistributed. It is not a placeholder
    to be filled in: the citation and the step that retrieves the number are the
    entry, and a run that needs the value follows the step.
    """

    source: str
    terms: str
    method: str
    fetch: str
    disagreements: tuple[Disagreement, ...] = ()


CrossSection = Union[CrossSectionTable, FetchStep]

RelativeStrength = Union[RelativeStrengthTable, FetchStep]


@dataclass(frozen=True)
class EmissionLine:
    """One emission channel, as the data file describes it.

    A binding energy and a cross section, and nothing that says what kind of
    line this is. The model does not learn from this type which of its lines are
    main lines and which are satellites, which is the arrangement
    ../../docs/decisions/satellite-lines.md exists to keep.
    """

    name: str
    binding_energy: CitedEnergy
    cross_section: Optional[CrossSection] = None
    relative_strength: Optional[RelativeStrength] = None
    strength_relative_to: Optional[str] = None

    def tabulated_cross_section(self) -> CrossSectionTable:
        """The cross section table, or a refusal naming why there is none."""
        if self.cross_section is None:
            raise AtomicDataRefused(
                f"The line {self.name!r} carries a strength relative to another "
                "line and no cross section, because that is what its source "
                "reports. Read its strength instead, or take the cross section "
                "from a source that tabulates one and add the row."
            )
        if isinstance(self.cross_section, FetchStep):
            raise AtomicDataRefused(
                f"The line {self.name!r} carries a citation for its cross section "
                "and not a value, because the terms of its source do not permit "
                "the table to be shipped here. Retrieve it first: "
                f"{self.cross_section.fetch}"
            )
        return self.cross_section

    def tabulated_relative_strength(self) -> RelativeStrengthTable:
        """The strength table, or a refusal naming why there is none."""
        if self.relative_strength is None:
            raise AtomicDataRefused(
                f"The line {self.name!r} carries a cross section and no strength "
                "relative to another line, because that is what its source "
                "tabulates. The strength of one line against another is then the "
                "ratio of their cross sections at the run's own photon energy."
            )
        if isinstance(self.relative_strength, FetchStep):
            raise AtomicDataRefused(
                f"The line {self.name!r} carries a citation for its relative "
                "strength and not a value, because the terms of its source do not "
                "permit the table to be shipped here. Retrieve it first: "
                f"{self.relative_strength.fetch}"
            )
        return self.relative_strength


def relative_cross_section(
    line: EmissionLine, reference: EmissionLine, photon_energy_electronvolt: float
) -> float:
    """One line's cross section as a fraction of another's, at one photon energy.

    This is the factor by which one trace is weaker than another, and on this
    board it is the factor that decides how badly a weak line can be distorted
    by what overlaps it. It is derived here rather than tabulated, so that the
    file stays comparable against the source it was copied from row by row.
    """
    here = line.tabulated_cross_section().megabarn_at(photon_energy_electronvolt)
    there = reference.tabulated_cross_section().megabarn_at(photon_energy_electronvolt)
    return here / there


def _table(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise AtomicDataRefused(f"{where} is {value!r} rather than a table of fields.")
    return value


def _text(fields: Mapping[str, object], field: str, where: str) -> str:
    value = fields.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AtomicDataRefused(
            f"{where} carries no {field}. Every number in this file names the "
            "source it was taken from, precisely enough to find the number "
            "again, and how that source's terms were understood. A source to be "
            "added later is not a source. See docs/decisions/atomic-data.md."
        )
    return value.strip()


def _number(value: object, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AtomicDataRefused(f"{where} is {value!r}, which is not a number.")
    number = float(value)
    if not isfinite(number):
        raise AtomicDataRefused(
            f"{where} is {number!r}. A not-a-number or an infinity does not fail "
            "where it is read; it spreads through the arithmetic that uses it "
            "and surfaces somewhere else as an empty result."
        )
    return number


def _method(fields: Mapping[str, object], where: str) -> str:
    named = _text(fields, "method", where)
    if named not in METHODS:
        raise AtomicDataRefused(
            f"{where} says its number was obtained by {named!r} and it is one of "
            f"{list(METHODS)}. A measurement and a calculation are different "
            "claims about the world, and a file that did not separate them would "
            "let a reader give them the same weight without deciding to."
        )
    return named


def _refuse_a_delay(fields: Mapping[str, object], where: str) -> None:
    """Refuse an intrinsic delay written anywhere inside an entry.

    Read over the nested tables as well as the top level, because the place
    somebody puts it is beside the binding energy it belongs to rather than at
    the top of the row.
    """
    for field, value in fields.items():
        if DELAY in field.lower():
            raise AtomicDataRefused(
                f"{where} carries the field {field!r}. The intrinsic delay of a "
                "line is a run parameter and arrives through the manifest, "
                "because it is not well known and a number for it beside a cited "
                "binding energy would be a confidence the field does not have. A "
                "delay written here is also a value no freeze record covers, "
                "since the manifest is what a run is described by. See "
                "docs/decisions/atomic-data.md."
            )
        if isinstance(value, dict):
            _refuse_a_delay(value, f"{field} of {where}")


def _disagreements(
    fields: Mapping[str, object], where: str
) -> tuple[Disagreement, ...]:
    """Every other source recorded against one number, and none of them merged."""
    entries = fields.get("disagreement", [])
    if not isinstance(entries, list):
        raise AtomicDataRefused(
            f"The disagreement recorded against {where} is {entries!r} rather "
            "than a list of sources. There can be more than one, and a shape that "
            "held only the last would drop the rest without saying so."
        )
    recorded = []
    for position, entry in enumerate(entries):
        beside = f"disagreement {position} against {where}"
        against = _table(entry, beside)
        carries_value = "value" in against
        carries_fetch = "fetch" in against
        if carries_value == carries_fetch:
            raise AtomicDataRefused(
                f"{beside} carries "
                f"{'both a value and a fetch step' if carries_value else 'neither a value nor a fetch step'}. "
                "A recorded disagreement says what the other source holds, so it "
                "is the number where the terms permit one and the step that "
                "retrieves it where they do not, and exactly one of the two."
            )
        recorded.append(
            Disagreement(
                source=_text(against, "source", beside),
                terms=_text(against, "terms", beside),
                method=_method(against, beside),
                value=(
                    _number(against.get("value"), f"the value of {beside}")
                    if carries_value
                    else None
                ),
                fetch=_text(against, "fetch", beside) if carries_fetch else None,
            )
        )
    return tuple(recorded)


def _energy(fields: Mapping[str, object], where: str) -> CitedEnergy:
    return CitedEnergy(
        electronvolt=_number(fields.get("value"), f"the value of {where}"),
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
        method=_method(fields, where),
        disagreements=_disagreements(fields, where),
    )


def _numbers(value: object, where: str) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise AtomicDataRefused(f"{where} is {value!r} rather than a list of numbers.")
    return tuple(_number(item, f"an entry of {where}") for item in value)


def _columns(
    fields: Mapping[str, object], where: str
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The photon axis and the values beside it, held to what a table has to be.

    Shared by the two tabulated shapes, so a strength table and a cross section
    table are refused by one set of rules rather than by two.
    """
    energies = _numbers(
        fields.get("photon_energy_electronvolt"), f"{where} photon axis"
    )
    values = _numbers(fields.get("value"), f"{where} values")
    if len(energies) != len(values):
        raise AtomicDataRefused(
            f"{where} has {len(energies)} photon energies and {len(values)} "
            "values. A row is a photon energy and the cross section at it, so a "
            "table where the two columns differ in length has rows whose energy "
            "is whatever happened to be at the same position."
        )
    for earlier, later in zip(energies, energies[1:]):
        if not earlier < later:
            raise AtomicDataRefused(
                f"{where} has {later} eV at or below {earlier} eV. The photon "
                "energies increase, because the interpolation reads the two rows "
                "either side of a value and a table that doubles back has more "
                "than two."
            )
    for value in values:
        if not value > 0.0:
            raise AtomicDataRefused(
                f"{where} holds {value}. A cross section or a strength at or "
                "below zero is not a channel that is closed, it is a number the "
                "interpolation cannot take the logarithm of, and an empty cell in "
                "a source table is not a zero. Leave the row out instead."
            )
    return energies, values


def _fetch_step(fields: Mapping[str, object], where: str) -> FetchStep:
    return FetchStep(
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
        method=_method(fields, where),
        fetch=_text(fields, "fetch", where),
        disagreements=_disagreements(fields, where),
    )


def _refuse_neither_or_both(fields: Mapping[str, object], where: str) -> bool:
    """Whether this quantity is fetched, refusing a row that says both or says nothing."""
    carries_value = "value" in fields
    carries_fetch = "fetch" in fields
    if carries_value and carries_fetch:
        raise AtomicDataRefused(
            f"{where} carries both a value and a fetch step. The fetch step is "
            "what stands in place of a number whose source does not permit it to "
            "be shipped here, so an entry with both says the number was and was "
            "not redistributed."
        )
    if not carries_value and not carries_fetch:
        raise AtomicDataRefused(
            f"{where} carries neither a value nor a fetch step. Where the terms "
            "of the source permit it, the number is here; where they do not, the "
            "step that retrieves it is. An entry with nothing is an entry the "
            "model cannot read and a reader cannot check."
        )
    return carries_fetch


def _cross_section(fields: Mapping[str, object], where: str) -> CrossSection:
    if _refuse_neither_or_both(fields, where):
        return _fetch_step(fields, where)
    energies, values = _columns(fields, where)
    return CrossSectionTable(
        photon_energy_electronvolt=energies,
        megabarn=values,
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
        method=_method(fields, where),
        disagreements=_disagreements(fields, where),
    )


def _relative_strength(fields: Mapping[str, object], where: str) -> RelativeStrength:
    if _refuse_neither_or_both(fields, where):
        return _fetch_step(fields, where)
    energies, values = _columns(fields, where)
    return RelativeStrengthTable(
        photon_energy_electronvolt=energies,
        strength=values,
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
        method=_method(fields, where),
        disagreements=_disagreements(fields, where),
    )


def load(document: str) -> Mapping[str, EmissionLine]:
    """The emission lines a data file describes, refusing what may not be read.

    Takes the text rather than a path, so that the refusals above can be proved
    against a document written in the test that proves them instead of against a
    file somebody has to keep in step with the assertions.
    """
    try:
        parsed = tomllib.loads(document)
    except tomllib.TOMLDecodeError as unreadable:
        raise AtomicDataRefused(
            f"The data file could not be parsed: {unreadable}. A file this "
            "loader cannot read is not a file with nothing in it, so the run "
            "stops here rather than continuing with no lines."
        ) from None

    named = _text(parsed, "interpolation", "the document")
    if named not in INTERPOLATIONS:
        raise AtomicDataRefused(
            f"The document asks for the interpolation {named!r} and it is one of "
            f"{list(INTERPOLATIONS)}. There is no default: the cross section the "
            "model uses at a photon energy between two rows comes from the table "
            "and from this choice together, so a run that did not say which it "
            "used cannot be compared against the source afterwards."
        )

    entries = parsed.get("line")
    if not isinstance(entries, list) or not entries:
        raise AtomicDataRefused(
            "The document declares no emission line. A data file with no lines "
            "in it loads as an empty model rather than as a failure, and a "
            "spectrogram with nothing in it is a picture somebody has to notice."
        )

    lines: dict[str, EmissionLine] = {}
    for position, entry in enumerate(entries):
        where = f"line {position}"
        fields = _table(entry, where)
        name = _text(fields, "name", where)
        if name in lines:
            raise AtomicDataRefused(
                f"The line {name!r} is declared twice. A lookup would answer with "
                "whichever row was loaded second, so the file refuses the pair "
                "rather than choosing between them."
            )
        _refuse_a_delay(fields, f"the line {name!r}")
        carries_cross_section = "cross_section" in fields
        carries_strength = "relative_strength" in fields
        if carries_cross_section == carries_strength:
            raise AtomicDataRefused(
                f"The line {name!r} carries "
                f"{'both a cross section and a relative strength' if carries_cross_section else 'neither a cross section nor a relative strength'}"
                ". A line is as strong as its source says it is, and a source "
                "either tabulates a cross section or reports a strength beside "
                "another line. An entry carrying both has two answers that can "
                "drift apart and an entry carrying neither has none."
            )
        strength = (
            _relative_strength(
                _table(
                    fields.get("relative_strength"),
                    f"the relative strength of {name}",
                ),
                f"the relative strength of {name}",
            )
            if carries_strength
            else None
        )
        lines[name] = EmissionLine(
            name=name,
            binding_energy=_energy(
                _table(fields.get("binding_energy"), f"the binding energy of {name}"),
                f"the binding energy of {name}",
            ),
            cross_section=(
                _cross_section(
                    _table(fields.get("cross_section"), f"the cross section of {name}"),
                    f"the cross section of {name}",
                )
                if carries_cross_section
                else None
            ),
            relative_strength=strength,
            strength_relative_to=(
                _text(
                    _table(
                        fields.get("relative_strength"),
                        f"the relative strength of {name}",
                    ),
                    "relative_to",
                    f"the relative strength of {name}",
                )
                if carries_strength
                else None
            ),
        )
    return MappingProxyType(lines)


def neon_main_lines() -> Mapping[str, EmissionLine]:
    """The 2s and 2p lines of neon, out of the file shipped in this package."""
    return _packaged(NEON_MAIN_LINES)


def neon_2p_shake_up_satellites() -> Mapping[str, EmissionLine]:
    """The shake up satellites accompanying 2p emission, out of the shipped file.

    A separate file from the main lines rather than more rows in that one. The
    two are read at different photon energies from different sources under
    different terms, and a run that wants the clean model reads one of them
    while a run that wants the contaminated model reads both. Nothing in either
    file says which of the two it is; the file names say it, and a file name is
    not something the model branches on.
    """
    return _packaged(NEON_2P_SHAKE_UP_SATELLITES)


def _packaged(name: str) -> Mapping[str, EmissionLine]:
    """One data file shipped inside this package, loaded and held to the rules."""
    packaged = files(__package__ or "") / DATA_DIRECTORY / name
    return load(packaged.read_text(encoding="utf-8"))
