# Where the atomic data comes from, and how a number between two rows is obtained

Decided in issue #1, entry 6, and in issue #29.

The forward model needs binding energies and photoionisation cross sections for
neon. Two questions had to be answered before any of them could be written down:
whether a value from a published table may be shipped in this repository at all,
and what the model does at a photon energy the table does not hold.

## Every number carries its source and the terms of that source

Two fields beside every value, not one.

The source, precisely enough to find the number again. That is the rule from
[units-and-constants.md](units-and-constants.md) and the reason is the same one:
a board arguing that a published number is wrong because of how it was produced
cannot carry numbers whose provenance is unrecorded.

The terms, meaning how the conditions attached to that source were understood.
This is the answer to entry 6 of issue #1. The values here come from published
tables and databases whose conditions differ, so one answer for the whole body of
data would be wrong for part of it, and the part it was wrong about would be
invisible. Where the terms permit redistribution the value is in the file. Where
they do not, the entry carries the citation and a step that retrieves the number,
in place of the number.

That is the cost of this arrangement and it is stated rather than hidden: a
clone can compute offline for everything whose source permits it, and where it
cannot, the file says which number is missing and why. The intent in milestone 10
is met for the first part and visibly not met for the second.

The loader refuses a row missing either field, and refuses a row carrying both a
value and a fetch step, because such a row says the number was and was not
redistributed.

## What the neon main lines use today

The binding energies come from the NIST Atomic Spectra Database. Works of NIST
employees are not subject to copyright protection in the United States and NIST
asks to be acknowledged explicitly as the source, which the citations do.

The cross sections are the Hartree-Fock-Slater tables of Yeh and Lindau (1985),
read through a digitisation published under CC BY 4.0. That licence permits
redistribution with attribution, so the values are in the file and both the
digitisation and the paper it digitises are cited. Attribution being a condition
of the licence rather than a courtesy is exactly the kind of thing the terms
field exists to record.

Neither source needed a fetch step. The loader carries that shape anyway,
because the terms of the next source are not this decision's to promise.

## The data is a file, not a module

One row per line, loaded like any other input, compiled into nothing. This
extends the arrangement [satellite-lines.md](satellite-lines.md) fixed for the
satellite set to the main lines as well, for the same reason: a reader who holds
a different value for a cross section changes the row and re-runs, and a number
written into a module is a number only its author can disagree with.

It also keeps the file comparable against the source it was copied from, row by
row. So the cross sections are stored as the source tabulates them, in megabarns
against photon energy, and the relative strength one line has against another is
derived where it is used rather than stored as a third column that could drift
against the two it came from.

## A straight line in the logarithms, and what it costs

Between two tabulated photon energies, a cross section is obtained by a straight
line in the logarithm of the photon energy and the logarithm of the cross
section. The file names the method and the loader refuses a file that names one
it does not implement. There is no default, because the number the model uses at
a photon energy between two rows comes from the table and from this choice
together, and a run that did not record which it used cannot be compared against
the source afterwards.

Two properties decide it.

It cannot overshoot. A spline through points this sparse can: the shipped table
has nine points across four decades of cross section above 132.3 eV, and a spline
that dips below zero there produces a negative cross section that nothing
downstream would question.

It is closer to what these curves do. A subshell cross section above its
threshold is near a power law in photon energy, which is a straight line in these
coordinates and a steep curve in the values themselves.

The second half is measured. Dropping each interior point of the two shipped
tables in turn and interpolating it back from its neighbours gives a worst
relative error of 0.271 for 2p and 0.083 for 2s under this method, against 2.487
and 0.890 for a straight line in the values. The command that produced those
numbers is in the pull request that landed the file.

What the choice does not fix is written here rather than left to be found. The 2p
worst case sits at 80 eV, where that cross section is turning over near its
maximum, and a power law does not describe a maximum. Between 40.8 eV and 132.3
eV this file is a coarse description of that curve under either method, and what
repairs it is more tabulated rows rather than a cleverer interpolation. This
matters to the result: at 100 eV the two methods differ by about eighteen per
cent in the 2p cross section, which is a factor the relative strength of the
lines is read through.

Outside the tabulated range nothing is returned. Continuing a cross section past
the ends of its table is inventing a number rather than reading one, and below
the first row there is a threshold rather than a straight line of any kind.

## What this does not settle

The intrinsic delay of a line is not here and is not in any data file. It is a
run parameter, for the reason issue #33 gives: it is not well known, and writing
a number for it into a data file would be a confidence the field does not have.

The fine structure of the 2p threshold is not carried. The binding energy in the
file is the threshold to the lower of the two levels of the ion, so a run against
it has one 2p line where a high resolution measurement resolves a doublet.

Whether the values in the file are the right ones is not a question this
arrangement answers, and it is not one a check can. What it makes possible is
that a reader who thinks a value is wrong can say so by changing it and showing
what moves.
