"""The conversions between atomic units and the units a reader wants.

The core of this model works in Hartree atomic units, because that is how the
relations it implements are written in the sources they come from, and a
reviewer checking the physics should be comparing like with like rather than
unpicking somebody's conversions first. A reader of this field wants
electronvolts and attoseconds. The rule that reconciles those two, and the
reason it is a rule, is in ../../docs/decisions/units-and-constants.md.

A value converts once, where it enters the core or where it leaves it, and never
in between. Entering is where a parameter arrives from a manifest, a document or
an operator. Leaving is where a value is written onto an axis, into a file, or
into anything a person reads.

One consequence of that is worth having next to the functions rather than only
in the decision record. Everything inside the core takes and returns atomic
units, so a call site that hands one of those functions electronvolts is a
defect at that call site. It is not an invitation to add a conversion inside the
function, because that is what turns one conversion into two and makes the
second one invisible.

This module holds no number. Every factor it applies is read out of the constant
table beside it, which is the one place in the tree that may carry a numeric
literal with physics in it. Nothing here does arithmetic on a factor either: the
attoseconds in one atomic unit of time is a product of two table rows and is
computed once at import, so the two rows stay separately citable.

The functions take and return plain floats and use nothing but multiplication
and division, so they work unchanged on whatever array type this model later
carries. That is a property of how they are written rather than a promise, and
this package has no array dependency today.
"""

from scheinbild_model.constants import CONSTANTS

_HARTREE_IN_ELECTRONVOLT = CONSTANTS["hartree_energy_in_electronvolt"].value

_ATOMIC_TIME_IN_ATTOSECOND = (
    CONSTANTS["atomic_unit_of_time_in_second"].value
    * CONSTANTS["attoseconds_per_second"].value
)


def electronvolts_to_hartree(energy_in_electronvolt: float) -> float:
    """An energy in electronvolts, as the same energy in hartree.

    This is the boundary crossing inwards. Use it where an energy arrives from
    a manifest or an operator, once, and pass hartree everywhere after that.
    """
    return energy_in_electronvolt / _HARTREE_IN_ELECTRONVOLT


def hartree_to_electronvolts(energy_in_hartree: float) -> float:
    """An energy in hartree, as the same energy in electronvolts.

    This is the boundary crossing outwards. Use it where an energy is written
    onto an axis, into a file, or into anything a person reads.
    """
    return energy_in_hartree * _HARTREE_IN_ELECTRONVOLT


def attoseconds_to_atomic_time(time_in_attosecond: float) -> float:
    """A time in attoseconds, as the same time in atomic units of time.

    The delay this board is about is a number of attoseconds in every document
    that discusses it and a number of atomic units everywhere the model
    computes with it. This is where the first becomes the second.
    """
    return time_in_attosecond / _ATOMIC_TIME_IN_ATTOSECOND


def atomic_time_to_attoseconds(time_in_atomic_units: float) -> float:
    """A time in atomic units of time, as the same time in attoseconds."""
    return time_in_atomic_units * _ATOMIC_TIME_IN_ATTOSECOND
