"""The constant table.

Every physical constant this project uses lives here, and this is the only
module in the tree that may hold a numeric literal carrying physics. The rule
and the reason for it are in ../../docs/decisions/units-and-constants.md: the
argument this board makes is that a published number is wrong because of how it
was produced, and the first reasonable question about any number of this board's
own is where that one came from.

Each row carries four things. The symbol it is known by, the value, the unit the
value is in, and the source the value was taken from, precisely enough to find
the number again.

A row with no source does not load. Not a row with a source to be added later,
and not a row with a comment saying where the number probably came from. The
refusal happens when this module is imported, so the absence of a citation stops
a run rather than waiting for a reviewer to notice it.

What is in the table today is the conversion factors and the exact SI values
they are checked against, and nothing else. The atomic data this model needs for
neon, the binding energies and cross sections and satellite intensities, is not
here and will not be. Entry 6 of issue #1 answered where it comes from and
whether it may be shipped, and the answer put it in data files with a statement
of terms beside every citation, which is written down in
../../docs/decisions/atomic-data.md. A cross section against photon energy is a
column rather than a row, and a reader has to be able to disagree with one by
editing it, so neither shape belongs in this table.

Some rows here are exact by definition rather than measured. The Planck
constant, the elementary charge and the speed of light have fixed values in the
SI, so their rows carry no uncertainty and cannot drift with a later adjustment,
and the prefix factors are exact for the same kind of reason. Which rows those
are is read off their sources rather than counted here. They are in the table
because the test suite uses them to check the measured rows, which is a check on
the numbers this file ships rather than a restatement of them.
"""

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Iterable, Mapping


class ConstantRefused(ValueError):
    """A row was offered to the table that the table may not hold.

    Raised at import time, because a constant with no source is a defect in the
    tree rather than a condition a caller can handle.
    """


@dataclass(frozen=True)
class Constant:
    """One row of the table.

    Frozen, so a value read out of the table cannot be rewritten by whoever
    read it. A model that could edit its own constants at run time would make
    the manifest an incomplete description of the run, which is the property
    issue #24 has to make true.
    """

    symbol: str
    value: float
    unit: str
    source: str


def load(rows: Iterable[Constant]) -> Mapping[str, Constant]:
    """Turn rows into the table, refusing every row that breaks the rule.

    Refused, one reason per row, and the message names the symbol so that the
    failure says which row rather than that some row is wrong:

    A symbol that is empty or blank, because a row nothing can ask for is a row
    nothing reads.

    A value that is not a finite real number. An infinity or a not-a-number in
    the table propagates silently through every arithmetic operation downstream
    and surfaces as an empty plot rather than as an error.

    A unit that is empty or blank. A number whose unit is not written down is
    the defect the conversion rule in units.py exists to prevent, and it is not
    recoverable from the value.

    A source that is empty or blank. This is the rule the decision record puts
    first and the one this loader exists for.

    A symbol that another row already used, because a table with two rows under
    one name answers a lookup with whichever row happened to be second.
    """
    table: dict[str, Constant] = {}
    for row in rows:
        symbol = row.symbol.strip()
        if not symbol:
            raise ConstantRefused(
                "A constant with no symbol was offered to the table. Every row "
                f"is looked up by its symbol. The row was {row!r}."
            )
        if not isinstance(row.value, float) or not isfinite(row.value):
            raise ConstantRefused(
                f"The constant {symbol!r} has the value {row.value!r}, which is "
                "not a finite real number. A non-finite constant does not fail "
                "where it is read; it spreads through the arithmetic that uses "
                "it and surfaces somewhere else as an empty result."
            )
        if not row.unit.strip():
            raise ConstantRefused(
                f"The constant {symbol!r} carries no unit. The unit is not "
                "recoverable from the value, and a number whose unit is not "
                "written down is what the conversion rule in "
                "docs/decisions/units-and-constants.md exists to prevent."
            )
        if not row.source.strip():
            raise ConstantRefused(
                f"The constant {symbol!r} carries no source. Every value in "
                "this table names where it was taken from, precisely enough to "
                "find the number again. A source to be added later is not a "
                "source. The rule is in docs/decisions/units-and-constants.md."
            )
        if symbol in table:
            raise ConstantRefused(
                f"The constant {symbol!r} is declared twice. A lookup would "
                "answer with whichever row was loaded second, so the table "
                "refuses the pair rather than choosing between them."
            )
        table[symbol] = row
    return MappingProxyType(table)


_ROWS = (
    Constant(
        symbol="hartree_energy_in_electronvolt",
        value=27.211386245981,
        unit="eV",
        source=(
            "CODATA 2022 recommended values, hartree-electron volt "
            "relationship, standard uncertainty 0.000000000030 eV. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?hrev"
        ),
    ),
    Constant(
        symbol="atomic_unit_of_time_in_second",
        value=2.4188843265864e-17,
        unit="s",
        source=(
            "CODATA 2022 recommended values, atomic unit of time, standard "
            "uncertainty 0.0000000000026e-17 s. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?aut"
        ),
    ),
    Constant(
        symbol="hartree_energy_in_joule",
        value=4.3597447222060e-18,
        unit="J",
        source=(
            "CODATA 2022 recommended values, Hartree energy, standard "
            "uncertainty 0.0000000000048e-18 J. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?hr"
        ),
    ),
    Constant(
        symbol="elementary_charge",
        value=1.602176634e-19,
        unit="C",
        source=(
            "CODATA 2022 recommended values, elementary charge, exact by the "
            "SI definition of the ampere. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?e"
        ),
    ),
    Constant(
        symbol="planck_constant",
        value=6.62607015e-34,
        unit="J Hz^-1",
        source=(
            "CODATA 2022 recommended values, Planck constant, exact by the SI "
            "definition of the kilogram. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?h"
        ),
    ),
    Constant(
        symbol="attoseconds_per_second",
        value=1e18,
        unit="as s^-1",
        source=(
            "SI Brochure, 9th edition 2019, the table of SI prefixes: atto is "
            "10^-18, so this factor is exact by definition. "
            "https://www.bipm.org/en/publications/si-brochure"
        ),
    ),
    Constant(
        symbol="atomic_unit_of_electric_field",
        value=5.14220675112e11,
        unit="V m^-1",
        source=(
            "CODATA 2022 recommended values, atomic unit of electric field, "
            "standard uncertainty 0.00000000080e11 V m^-1. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?auefld"
        ),
    ),
    Constant(
        symbol="vacuum_electric_permittivity",
        value=8.8541878188e-12,
        unit="F m^-1",
        source=(
            "CODATA 2022 recommended values, vacuum electric permittivity, "
            "standard uncertainty 0.0000000014e-12 F m^-1. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?ep0"
        ),
    ),
    Constant(
        symbol="speed_of_light_in_vacuum",
        value=299792458.0,
        unit="m s^-1",
        source=(
            "CODATA 2022 recommended values, speed of light in vacuum, exact by "
            "the SI definition of the metre. "
            "https://physics.nist.gov/cgi-bin/cuu/Value?c"
        ),
    ),
    Constant(
        symbol="square_centimetres_per_square_metre",
        value=1e4,
        unit="cm^2 m^-2",
        source=(
            "SI Brochure, 9th edition 2019, the table of SI prefixes: centi is "
            "10^-2, so a square metre is 10^4 square centimetres and this factor "
            "is exact by definition. "
            "https://www.bipm.org/en/publications/si-brochure"
        ),
    ),
)

CONSTANTS: Mapping[str, Constant] = load(_ROWS)
