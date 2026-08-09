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

## What a row carries, and why it is two fields rather than one

Every number carries the source it was taken from and how that source's terms
were understood. The second field is not tidiness. The values here come from
published tables whose terms differ, and whether a number may be shipped in a
public repository at all is a question per source: some are freely
redistributable, some permit use but not redistribution of the compiled table.
One answer for the whole file would be wrong for part of it.

So where the terms permit it the entry carries the value, and where they do not
it carries the citation and a `fetch` step in place of the number. Both shapes
load; a row carrying neither, or both, does not. Nothing in the file shipped
today needs the second shape, and the loader carries it because the terms of the
next source are not this file's to promise.

## What the loader refuses

A row with no source, which is the rule the decision record puts first. A row
with no statement of terms, for the reason above. A cross section table whose
photon energies do not increase, because the interpolation below reads
neighbours and a table that doubles back has two of them. A cross section at or
below zero, which is not a physical cross section and is also not a number a
logarithm can be taken of. And a photon energy outside the tabulated range,
because extending a table past its ends is inventing a number rather than
reading one.

Refused at load rather than where the value is used, so that a file whose
provenance was going to be completed later stops the run that reads it.
"""

import tomllib
from bisect import bisect_left
from dataclasses import dataclass
from importlib.resources import files
from math import exp, isfinite, log
from types import MappingProxyType
from typing import Mapping, Union

# Where the packaged file sits. A file inside the package rather than beside the
# repository, so that a reader who installed this project has the data the model
# reads and not a path that only exists in a checkout.
DATA_DIRECTORY = "data"

NEON_MAIN_LINES = "neon-main-lines.toml"

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
class CitedEnergy:
    """One energy, with where it came from and under what terms."""

    electronvolt: float
    source: str
    terms: str


@dataclass(frozen=True)
class CrossSectionTable:
    """A subshell cross section against photon energy, as the source tabulates it."""

    photon_energy_electronvolt: tuple[float, ...]
    megabarn: tuple[float, ...]
    source: str
    terms: str

    def megabarn_at(self, photon_energy_electronvolt: float) -> float:
        """The cross section at one photon energy, interpolated between rows.

        Exact at a tabulated point, and exact in the arithmetic rather than
        within a tolerance: a photon energy that is in the table is answered by
        reading the table, so the round trip through two logarithms and an
        exponential never happens and cannot move the last place.
        """
        grid = self.photon_energy_electronvolt
        if not grid[0] <= photon_energy_electronvolt <= grid[-1]:
            raise AtomicDataRefused(
                f"The cross section was asked for at {photon_energy_electronvolt} "
                f"eV and this table runs from {grid[0]} eV to {grid[-1]} eV. "
                "Continuing the table past its ends is inventing a number rather "
                "than reading one, and a cross section is not a straight line "
                "anywhere: below the first row it has a threshold and above the "
                "last it falls by decades. Add the rows the run needs, with their "
                "source, rather than extending these."
            )
        index = bisect_left(grid, photon_energy_electronvolt)
        if grid[index] == photon_energy_electronvolt:
            return self.megabarn[index]
        below = index - 1
        span = log(grid[index]) - log(grid[below])
        along = (log(photon_energy_electronvolt) - log(grid[below])) / span
        rise = log(self.megabarn[index]) - log(self.megabarn[below])
        return exp(log(self.megabarn[below]) + along * rise)


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
    fetch: str


CrossSection = Union[CrossSectionTable, FetchStep]


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
    cross_section: CrossSection

    def tabulated_cross_section(self) -> CrossSectionTable:
        """The cross section table, or a refusal naming the step that fetches it."""
        if isinstance(self.cross_section, FetchStep):
            raise AtomicDataRefused(
                f"The line {self.name!r} carries a citation for its cross section "
                "and not a value, because the terms of its source do not permit "
                "the table to be shipped here. Retrieve it first: "
                f"{self.cross_section.fetch}"
            )
        return self.cross_section


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


def _energy(fields: Mapping[str, object], where: str) -> CitedEnergy:
    return CitedEnergy(
        electronvolt=_number(fields.get("value"), f"the value of {where}"),
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
    )


def _numbers(value: object, where: str) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise AtomicDataRefused(f"{where} is {value!r} rather than a list of numbers.")
    return tuple(_number(item, f"an entry of {where}") for item in value)


def _tabulated(fields: Mapping[str, object], where: str) -> CrossSectionTable:
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
                f"{where} holds {value}. A cross section at or below zero is not "
                "a channel that is closed, it is a number the interpolation "
                "cannot take the logarithm of, and an empty cell in a source "
                "table is not a zero. Leave the row out instead."
            )
    return CrossSectionTable(
        photon_energy_electronvolt=energies,
        megabarn=values,
        source=_text(fields, "source", where),
        terms=_text(fields, "terms", where),
    )


def _cross_section(fields: Mapping[str, object], where: str) -> CrossSection:
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
    if carries_fetch:
        return FetchStep(
            source=_text(fields, "source", where),
            terms=_text(fields, "terms", where),
            fetch=_text(fields, "fetch", where),
        )
    return _tabulated(fields, where)


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
        lines[name] = EmissionLine(
            name=name,
            binding_energy=_energy(
                _table(fields.get("binding_energy"), f"the binding energy of {name}"),
                f"the binding energy of {name}",
            ),
            cross_section=_cross_section(
                _table(fields.get("cross_section"), f"the cross section of {name}"),
                f"the cross section of {name}",
            ),
        )
    return MappingProxyType(lines)


def neon_main_lines() -> Mapping[str, EmissionLine]:
    """The 2s and 2p lines of neon, out of the file shipped in this package."""
    packaged = files(__package__ or "") / DATA_DIRECTORY / NEON_MAIN_LINES
    return load(packaged.read_text(encoding="utf-8"))
