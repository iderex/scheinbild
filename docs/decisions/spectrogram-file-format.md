# The on-disk format for a spectrogram

Decided in issue #11.

A spectrogram has to survive leaving the process. Boards other than this one are
expected to read these files, and anything reading a simulated trace has to know
exactly which grid the values sit on. The axes travel inside the same file as the
array or they get guessed, which is the same failure
[spectrogram-type.md](spectrogram-type.md) fixes in memory.

## The format

One file. A compressed archive in the container the numerical library writes,
holding the intensity array, both axis arrays, and a metadata block carrying the
run manifest. The file extension is `.npz`.

## The layout, precisely

Written out so that a reader can parse the file without any code from this
repository.

The file is a ZIP archive. Each member is deflate compressed. Each member is
named `<key>.npy` and holds one array in NPY format version 1.0, which is: the
six magic bytes `\x93NUMPY`, one byte major version `\x01`, one byte minor
version `\x00`, a two byte little endian unsigned header length, then that many
bytes of an ASCII header ending in a newline, then the raw array data. The header
is a mapping literal with the keys `descr`, `fortran_order` and `shape`.

Four members, and no others:

`intensity.npy`. Two dimensional, `descr` is `<f8`, `fortran_order` is false,
shape is `(n_energy, n_delay)`. Expected counts. Energy is the first axis, which
is the axis order in [spectrogram-type.md](spectrogram-type.md) and is not
restated as a choice here.

`energy_ev.npy`. One dimensional, `descr` is `<f8`, shape is `(n_energy,)`.
Kinetic energy in electronvolts, uniformly spaced and ascending.

`delay_as.npy`. One dimensional, `descr` is `<f8`, shape is `(n_delay,)`. Pulse
delay in attoseconds, uniformly spaced and ascending.

`manifest_json_utf8.npy`. One dimensional, `descr` is `|u1`, shape is
`(n_bytes,)`. The run manifest serialised as JSON and encoded as UTF-8, one byte
per element. What the manifest contains is issue #24 and is not fixed here.

Three properties of that layout are deliberate and each one is a decision rather
than a default.

Little endian and eight byte float, written explicitly, so the bytes do not
depend on the machine that wrote them. A file whose byte order follows the writer
is a file two operators can produce differently from one manifest, which is the
determinism rule in
[determinism-and-seeding.md](determinism-and-seeding.md) broken at the last step.

C order rather than Fortran order, so that a reader walking the buffer without
consulting `fortran_order` gets rows of constant energy rather than a transposed
picture. Readers should still consult it.

The manifest as bytes rather than as a text array. A unicode array in this
container is UTF-32, so its raw data is not the UTF-8 a reader outside the
numerical library expects, and the encoding would have to be documented as a
second thing. A `uint8` member is the JSON bytes themselves: unzip the member,
skip the NPY header, decode UTF-8, parse.

## The candidates that were rejected, and what each would have cost

HDF5. It is what beamline data actually uses, and it carries axes and attributes
natively, so the convention would be somebody else's and already documented. The
cost is a C library dependency on every consumer, including a consumer that only
wants to read a single number out of one file, and including whoever is checking
this work on a machine where that library is awkward to install. The dependency
cost falls on every reader while the benefit is a convention this board is small
enough to document itself, which is the trade this decision refuses.

NetCDF. Inherits the same cost through the same library, and adds a second
specification on top of it.

A plain text array with a sidecar metadata file. The most inspectable option and
the easiest to get out of step with itself, because two files can be separated and
one of them edited. A trace whose axes have drifted from its array is worse than
one that cannot be opened, since the second failure announces itself.

The chosen container has one real weakness and it is worth naming: it has no
convention of its own for what an axis is. That is why the member names, dtypes
and shapes above are written out here rather than left to the writer, and why
this section of this document is the specification rather than a description of
one.

## What this decision does not settle

Two things, and neither is a detail.

The format in which a real measured trace arrives. That is decided by whoever
produced the trace, not here.

The format in which a simulated trace is handed to a benchmark on another board.
That is shared with those boards and cannot be decided here alone. It is a
separate question, to be answered when a real trace and a real consumer exist,
and this document does not pretend to have covered it. Reading this file as the
cross board exchange format is a misreading of it.

## Nothing writes this yet

No dependency is declared in `pyproject.toml` today, so the library whose
container this is has not arrived, and nothing in the tree writes or reads a
file in this format. The round trip that proves a file written here comes back
the same is issue #25. Until that lands, this document is a specification with
no implementation to disagree with.
