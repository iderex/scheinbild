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

Every quantity this module applies is read out of the constant table beside it,
which is the one place in the tree that may carry a numeric literal with physics
in it. Where a conversion needs more than one row, the rows are combined here
once at import rather than written down as a single number, so that each of them
stays separately citable: the attoseconds in one atomic unit of time is a product
of two rows, and the intensity one atomic unit of field carries is built from
three rows and a prefix factor.

The one literal below carries no physics. It is the cycle average of a squared
sinusoid, which follows from the shape of a wave rather than from any
measurement, and it is named and argued for where it is written.

The functions take and return plain floats. All but one use nothing but
multiplication and division, so they work unchanged on whatever array type this
model later carries; the intensity conversion takes a square root, and a square
root is the reason it is a function rather than a factor. That is a property of
how they are written rather than a promise, and this package has no array
dependency today.
"""

from math import sqrt

from scheinbild_model.constants import CONSTANTS

_HARTREE_IN_ELECTRONVOLT = CONSTANTS["hartree_energy_in_electronvolt"].value

_ATOMIC_TIME_IN_ATTOSECOND = (
    CONSTANTS["atomic_unit_of_time_in_second"].value
    * CONSTANTS["attoseconds_per_second"].value
)

# The cycle average of a squared sinusoid. It is what makes the relation below a
# statement about the intensity an experimenter measures, which is averaged over
# the optical cycle, rather than about the instantaneous one. Algebra rather than
# a measurement, so it is not a row of the table.
_CYCLE_AVERAGE = 0.5

# The intensity that one atomic unit of electric field carries, in the units a
# peak intensity is quoted in. Built from three table rows and one prefix factor
# at import, so each of them stays separately citable:
#
#     I = cycle average * permittivity * speed of light * field squared
#
# which is the plane wave relation between a peak field amplitude and the cycle
# averaged intensity, divided by the number of square centimetres in a square
# metre because the value it is compared against arrives per square centimetre.
_ATOMIC_INTENSITY_IN_WATT_PER_SQUARE_CENTIMETRE = (
    _CYCLE_AVERAGE
    * CONSTANTS["vacuum_electric_permittivity"].value
    * CONSTANTS["speed_of_light_in_vacuum"].value
    * CONSTANTS["atomic_unit_of_electric_field"].value
    * CONSTANTS["atomic_unit_of_electric_field"].value
    / CONSTANTS["square_centimetres_per_square_metre"].value
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


def peak_intensity_to_atomic_field(
    peak_intensity_in_watt_per_square_centimetre: float,
) -> float:
    """A peak intensity, as the peak electric field amplitude in atomic units.

    The boundary crossing inwards for the one parameter of this model that
    arrives as a power per area. An experimenter quotes a streaking pulse by its
    peak intensity and the physics is written in terms of the field, so this is
    where the first becomes the second, once.

    It is a square root rather than a factor, which is why it is a function here
    and not a constant somebody multiplies by: an intensity is quadratic in the
    field, so a call site doing its own arithmetic gets the direction right and
    the power wrong, and a field out by a square root is a streaking amplitude
    out by a square root.
    """
    return sqrt(
        peak_intensity_in_watt_per_square_centimetre
        / _ATOMIC_INTENSITY_IN_WATT_PER_SQUARE_CENTIMETRE
    )
