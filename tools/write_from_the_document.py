"""Write a spectrogram file using the published layout and nothing else.

This exists to test the document rather than the code. A round trip through one
repository's own writer and reader proves the two agree with each other, which a
shared mistake satisfies perfectly. What it cannot prove is that
docs/decisions/spectrogram-file-format.md says enough for somebody outside this
repository to produce a file that this repository will read.

So this module imports nothing from `scheinbild_model` and nothing from the
numerical library either. It uses `zipfile`, `struct` and `json` from the
standard library and builds the NPY members byte by byte out of the paragraph in
that document, which is the strongest available form of the claim: if the
document were wrong or incomplete, this would be impossible to write from it and
the file it produced would be refused.

The layout, quoted only as far as this file has to act on it: a ZIP archive of
deflate compressed members, each named `<key>.npy`, each holding one array in
NPY format version 1.0, which is the six magic bytes, a major version byte, a
minor version byte, a two byte little endian unsigned header length, that many
bytes of ASCII header ending in a newline, then the raw array data. The header
is a mapping literal with `descr`, `fortran_order` and `shape`.

Run it directly to write a file somewhere, or call `archive_bytes` and get the
bytes. The suite calls the second, so nothing it does depends on a path.
"""

import io
import json
import struct
import zipfile
from typing import Sequence

MAGIC = b"\x93NUMPY"
VERSION = b"\x01\x00"

# The header is padded so that the array data begins on a 64 byte boundary. The
# format allows any padding, so this is a choice rather than a requirement, and
# it is the one the numerical library makes.
#
# It does not make the two writers agree byte for byte, and the suite has a test
# saying so. The shape inside the header is spelled `(3,2,)` here and `(3, 2)`
# there, both valid, because the layout document fixes the shape and not how it
# is written down. Comparing two files from two writers therefore compares who
# wrote them.
ALIGNMENT = 64


def _npy_member(descr: str, shape: tuple[int, ...], data: bytes) -> bytes:
    """One NPY 1.0 member: magic, version, header length, header, data."""
    shape_literal = "(" + "".join(f"{size}," for size in shape) + ")"
    header = (
        f"{{'descr': '{descr}', 'fortran_order': False, 'shape': {shape_literal}, }}"
    )
    prefix = len(MAGIC) + len(VERSION) + 2
    padding = -(prefix + len(header) + 1) % ALIGNMENT
    header = header + " " * padding + "\n"
    return (
        MAGIC + VERSION + struct.pack("<H", len(header)) + header.encode("ascii") + data
    )


def _float64_bytes(values: Sequence[float]) -> bytes:
    """Little endian eight byte floats, written explicitly rather than natively.

    The document requires `<f8` so that the bytes do not depend on the machine
    that wrote them, and `struct` with an explicit byte order is how a writer
    with no array library obeys that.
    """
    return struct.pack(f"<{len(values)}d", *values)


def archive_bytes(
    intensity: Sequence[Sequence[float]],
    energy_ev: Sequence[float],
    delay_as: Sequence[float],
    manifest: dict[str, object],
) -> bytes:
    """The whole file, as bytes, built from the layout alone."""
    rows = len(intensity)
    columns = len(intensity[0]) if rows else 0
    flattened = [value for row in intensity for value in row]

    manifest_bytes = json.dumps(manifest, sort_keys=True, allow_nan=False).encode(
        "utf-8"
    )

    members = {
        "intensity.npy": _npy_member("<f8", (rows, columns), _float64_bytes(flattened)),
        "energy_ev.npy": _npy_member(
            "<f8", (len(energy_ev),), _float64_bytes(energy_ev)
        ),
        "delay_as.npy": _npy_member("<f8", (len(delay_as),), _float64_bytes(delay_as)),
        "manifest_json_utf8.npy": _npy_member(
            "|u1", (len(manifest_bytes),), manifest_bytes
        ),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m tools.write_from_the_document <path.npz>")
        return 2
    with open(argv[0], "wb") as handle:
        handle.write(
            archive_bytes(
                intensity=[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
                energy_ev=[100.0, 101.0, 102.0],
                delay_as=[-50.0, 50.0],
                manifest={"parameters": {}, "seeds": {}, "code_version": "0.0.0"},
            )
        )
    print(f"wrote {argv[0]} from the layout in the decision document")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
