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

Both are enforced now. The entry shape is refused by the table's own loader,
which landed in issue #51 and refuses a row with no source at import time. The
bare literal is refused by `no-bare-numeric-literal-outside-the-constant-table`
in `tools/invariants.py`, which landed in issue #58.

That second one carries a register, `tools/literals-outside-the-table.toml`,
because the rule is about where a number came from and a reading of the source
cannot see that. `4.0 * log(2.0)` and a binding energy are the same shape to a
parser, so every narrowing that got the tree green admitted the value the rule
exists to refuse. Instead the literal stays refused everywhere and a site that
carries one is entered in the register with the reason it is not a physics
number. A value not entered is refused wherever it appears, and an entry whose
site no longer holds its value is refused as well, so the register cannot
quietly grow past what is true of the tree.

What no check makes is the judgement inside an entry. Whether a number really
carries no physics is a sentence a person wrote and a reviewer reads, and a
wrong one passes every route this repository has.

## What this does not settle

This document fixes the shape of the table and the rule each entry obeys. It does
not choose what fills it, and it would be satisfied by a table with one entry or
with none.

Which body of atomic data the model reads, and whether those values may be
shipped in the repository or only cited, was entry 6 in issue #1 and is answered
in [atomic-data.md](atomic-data.md). The answer does not change the rule above:
it adds a second field beside the source, saying how that source's terms were
understood, and it keeps binding energies and cross sections out of this table
and in data files a reader can edit.
