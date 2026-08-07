# What a spectrogram is, as a type

Decided in issue #4.

A streaking spectrogram is intensity over kinetic energy and pulse delay.
Passing it around as a bare two dimensional array is the shortest path to a
silent rebinning, because an array carries no memory of which axis is which,
what grid it sits on, or what units that grid is in. Boards other than this one
are expected to read these objects, so the axes travel with the array or they
get guessed.

## The object

A spectrogram is one object holding four things:

The intensity array, two dimensional.

The kinetic energy axis, in electronvolts.

The delay axis, in attoseconds.

A reference to the run manifest that produced it.

## Axis order

Energy is the first axis. Delay is the second. This is stated here once so that
nobody has to infer it from a shape, and so that a transposed array is a
disagreement with a written rule rather than a matter of opinion.

## Units

The energy axis is in electronvolts. The delay axis is in attoseconds. These are
the units a reader of this field wants to see, and the conversions to and from
atomic units live in one module and nowhere else.

## Both grids are uniform

Required, not preferred. The analysis in milestone 6 transforms along the delay
axis, and a non uniform grid there silently changes what that transform means.
The energy grid is held to the same rule so that the two axes do not need
separate reasoning.

Non uniform grids are not forbidden forever. Admitting them costs a resampling
step that carries its own error, and no requirement asks for one yet. If a
requirement does arrive, the restriction is lifted by amending this document
with the resampling rule, not by an object that happens to hold a ragged axis.

## What the intensity value means

Expected counts. Not a normalised probability and not an arbitrary intensity
scale.

The reason is downstream. The counting statistics in milestone 5 need a number
to be Poisson about, and a normalised array has already thrown that number away.
Recovering it by multiplying back through by a total is guessing at the quantity
that decides the noise level.

## Metadata a spectrogram may not exist without

An object missing any of these is not a spectrogram:

The intensity array.

The energy axis, with a length equal to the first dimension of the array.

The delay axis, with a length equal to the second dimension of the array.

The manifest reference identifying the run that produced the object.

Everything else is optional. The manifest reference is on this list rather than
below it because a spectrogram whose provenance is unknown cannot be checked
against a freeze record, which is what milestone 7 needs it for.
