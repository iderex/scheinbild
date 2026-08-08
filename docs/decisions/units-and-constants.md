# The unit system, and where a constant comes from

Decided in issue #3.

Every equation this model implements is written in atomic units in the sources it
is taken from, and every number a reader of this field wants out of it is in
electronvolts and attoseconds. Mixing the two inside the core is how a conversion
factor gets lost somewhere nobody looks, and a lost factor of two is the exact
size of the effect this board exists to measure.

## The core works in atomic units

Hartree atomic units throughout the physics core. Energies in hartree, times in
atomic units of time, momenta and vector potentials in the atomic units that go
with them.

The reason is readability against the sources. The streaking relation, the vector
potential and the momentum shift can then be read line by line against the papers
they come from, so a reviewer checking the physics is comparing like with like
instead of unpicking somebody's conversions first. A defect in a formula and a
defect in a conversion look the same in a wrong number, and only one of them is
cheap to find.

## Conversion happens at the boundary

A value converts once, where it enters the core or where it leaves it, and never
in between.

Entering, that is where a parameter arrives from a manifest, a document or an
operator. Leaving, that is where a value is written onto an axis, into a file, or
into anything a person reads.

The two units a reader sees are fixed elsewhere and not restated here. What a
spectrogram's axes carry is in
[spectrogram-type.md](spectrogram-type.md), which is the authority for those
units, and this document adds only that the conversion to them is the boundary
conversion above and happens nowhere deeper.

One consequence is worth stating rather than discovering. A function inside the
core takes and returns atomic units, so a call site that passes electronvolts
into it is a defect at that call site, not an invitation to add a conversion
inside the function. Adding it there is what turns one conversion into two and
makes the second one invisible.

## The conversions live in one module

The conversion factors are themselves constants, so they obey the rule below,
and the functions that apply them sit in one module. Two modules that each know
how to turn electronvolts into hartree are two places to disagree.

## No bare literal, and every constant carries its source

No numeric constant appears as a literal in the code. Every constant lives in one
table, and each entry carries three things:

The value.

The unit the value is in.

The source it was taken from, precisely enough to find the number again.

A constant with no source does not go in the table. Not a constant with a source
to be added later, and not a constant with a comment saying where it probably
came from.

The reason is narrower than general tidiness and specific to this board. The
argument being made here is that a published number is wrong because of how it
was produced. A board making that argument cannot itself carry numbers whose
provenance is unrecorded, because the first reasonable question about any of its
own numbers is where that one came from.

Loop bounds, array indices, zero, one and the like are not constants of the
model and the rule is not aimed at them. What it is aimed at is any number that
carries physics: an energy, a cross section, an intensity ratio, a conversion
factor, a pulse duration.

## The form a check can refuse

The rule above is written as a property of the source text on purpose, because
that is a thing a machine can refuse:

A numeric literal carrying physics, outside the constant table module, is
refused.

An entry in the constant table missing its unit or its source is refused.

Neither is enforced today. The check that refuses a bare numeric literal outside
the constant table is one of the greppable invariants in issue #19, which names
that pattern already, and the entry shape is refused by the table's own loader
when issue #22 builds it. Until both land this document is prose that nothing
checks, and a constant added tomorrow without a source will pass every route
this repository has.

## What this does not settle

Which body of constants the values come from, and whether those values may be
shipped in the repository or only cited, is entry 6 in issue #1 and is open. This
document fixes the shape of the table and the rule each entry obeys. It does not
choose what fills it, and it would be satisfied by a table with one entry or
with none.
