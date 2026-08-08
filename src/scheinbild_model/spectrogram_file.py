"""Writing a spectrogram to a file and reading one back.

The layout is fixed in ../../docs/decisions/spectrogram-file-format.md and that
document is the specification rather than a description of one. This module
implements it and does not restate it: four members, `intensity.npy`,
`energy_ev.npy`, `delay_as.npy` and `manifest_json_utf8.npy`, in a compressed
archive with the extension `.npz`.

## The reader is the part that touches bytes it did not produce

Everything else in this package reads values the model itself produced. This
reads a file, and a file can have come from anywhere: a truncated download, a
different version of this repository, a deliberately built archive. So it is
written to fail in one direction only.

A malformed file produces `SpectrogramFileRefused` naming what was wrong, rather
than an exception from three layers down that a caller cannot tell from a bug.

No field read from the file is used as a size to allocate against. The container
library is asked for arrays and the arrays it returns are measured; nothing here
reads a length and then reserves it. A file claiming a billion element axis
therefore fails when the archive runs out of bytes, not when this module tries
to honour the claim.

Pickle is refused. The container can hold arbitrary objects, and loading one
executes code from the file, so `allow_pickle` is false at every call site and a
file relying on it is refused rather than opened.

The member list is closed. A file carrying a fifth member is refused rather than
ignored, because a reader that ignores what it does not recognise is how one
version of a format silently drops what a later version added.

## The manifest, and why it is JSON and not the canonical form

The manifest travels as JSON because the document says so and because a reader
outside this repository has a JSON parser and does not have the canonical form.
That form is a hashing input, not a serialisation, and it is deliberately not
what is written here.

The round trip is exact anyway. Every float is rendered by the standard library's
JSON writer using `repr`, which round trips on this interpreter, so a manifest
read back has the same digest as the one written. The suite asserts that rather
than assuming it, because the day it stops being true is the day a freeze record
stops matching the file it was taken from.
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest, ParameterValue
from scheinbild_model.spectrogram import Spectrogram, SpectrogramRefused

INTENSITY = "intensity"
ENERGY = "energy_ev"
DELAY = "delay_as"
MANIFEST = "manifest_json_utf8"

# The whole member list, and nothing outside it is accepted. A frozenset rather
# than a tuple because the archive's order is not part of the layout.
MEMBERS = frozenset({INTENSITY, ENERGY, DELAY, MANIFEST})

FILE_SUFFIX = ".npz"


class SpectrogramFileRefused(ValueError):
    """A file was not a spectrogram this module will read.

    Separate from SpectrogramRefused, which is about an object that cannot
    exist. This is about bytes that do not describe one, and a caller reading
    files from elsewhere wants to tell those two apart.
    """


def _manifest_as_json_bytes(manifest: Manifest) -> NDArray[np.uint8]:
    document = {
        "parameters": dict(manifest.parameters),
        "seeds": dict(manifest.seeds),
        "code_version": manifest.code_version,
    }
    # sort_keys so that one manifest produces one file. The archive is otherwise
    # a byte for byte function of the values, which is what makes two runs of
    # one manifest comparable with cmp rather than with a reader.
    encoded = json.dumps(document, sort_keys=True, allow_nan=False).encode("utf-8")
    return np.frombuffer(encoded, dtype=np.uint8)


def _manifest_from_json_bytes(raw: NDArray[np.uint8]) -> Manifest:
    if raw.dtype != np.uint8:
        raise SpectrogramFileRefused(
            f"The manifest member has dtype {raw.dtype} and the layout says "
            "|u1. A unicode array in this container is UTF-32, so a member of "
            "any other dtype is not the UTF-8 the layout describes."
        )
    if raw.ndim != 1:
        raise SpectrogramFileRefused(
            f"The manifest member has {raw.ndim} dimensions and the layout says one."
        )
    try:
        document: Any = json.loads(raw.tobytes().decode("utf-8"))
    except UnicodeDecodeError as broken:
        raise SpectrogramFileRefused(
            f"The manifest member is not UTF-8: {broken}."
        ) from broken
    except json.JSONDecodeError as broken:
        raise SpectrogramFileRefused(
            f"The manifest member is not JSON: {broken}."
        ) from broken

    if not isinstance(document, dict):
        raise SpectrogramFileRefused(
            f"The manifest is a {type(document).__name__} and a manifest is an "
            "object with parameters, seeds and a code version."
        )
    missing = {"parameters", "seeds", "code_version"} - set(document)
    if missing:
        raise SpectrogramFileRefused(
            f"The manifest is missing {sorted(missing)}. A run whose parameters "
            "or seeds did not survive the file cannot be checked against a "
            "freeze record, which is what the reference is carried for."
        )

    try:
        parameters: dict[str, ParameterValue] = dict(document["parameters"])
        seeds: dict[str, int] = dict(document["seeds"])
        return Manifest.of(
            parameters=parameters,
            seeds=seeds,
            code_version=document["code_version"],
        )
    except (TypeError, ValueError) as refused:
        # Manifest.of holds its own rules. Reaching one of them from a file is a
        # statement about the file, so it is re-raised as one rather than
        # arriving as a manifest error from a caller who never built a manifest.
        raise SpectrogramFileRefused(
            f"The manifest in the file is not a manifest this model accepts: {refused}"
        ) from refused


def write(spectrogram: Spectrogram, path: Path) -> Path:
    """Write a spectrogram to `path`, returning the path written.

    The suffix is appended by the container library when it is absent, so it is
    applied here instead and the returned path is the file that exists.
    """
    target = path if path.suffix == FILE_SUFFIX else path.with_suffix(FILE_SUFFIX)
    with target.open("wb") as handle:
        # The member names are written out here rather than unpacked from the
        # constants above, because the container library takes them as keyword
        # arguments and a mapping splatted into that call is indistinguishable
        # from its own options. The suite checks a written file's members
        # against the constants, so the two cannot drift in silence.
        np.savez_compressed(
            handle,
            intensity=spectrogram.counts,
            energy_ev=spectrogram.energy_axis_electronvolt,
            delay_as=spectrogram.delay_axis_attosecond,
            manifest_json_utf8=_manifest_as_json_bytes(spectrogram.manifest),
        )
    return target


def _member(archive: Any, name: str) -> NDArray[Any]:
    try:
        value = archive[name]
    except KeyError as missing:
        raise SpectrogramFileRefused(
            f"The file has no member named {name}.npy. The layout has four "
            f"members and this is one of them: {sorted(MEMBERS)}."
        ) from missing
    except (ValueError, zipfile.BadZipFile, EOFError) as broken:
        raise SpectrogramFileRefused(
            f"The member {name}.npy could not be read: {broken}. A member that "
            "does not decode is a truncated or rewritten archive rather than a "
            "spectrogram."
        ) from broken
    return np.asarray(value)


def read(path: Path) -> Spectrogram:
    """Read a spectrogram from `path`, or refuse the file and say why."""
    try:
        raw = path.read_bytes()
    except OSError as unreadable:
        raise SpectrogramFileRefused(f"{path} could not be read: {unreadable}.") from (
            unreadable
        )

    try:
        # allow_pickle stays false. The container can hold arbitrary objects and
        # loading one executes code out of the file.
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            present = set(archive.files)
            if present != MEMBERS:
                raise SpectrogramFileRefused(
                    f"The file holds {sorted(present)} and the layout has "
                    f"exactly {sorted(MEMBERS)}. A missing member is a file "
                    "that cannot be read, and an extra one is a file this "
                    "reader would be dropping something from."
                )
            intensity = _member(archive, INTENSITY)
            energy = _member(archive, ENERGY)
            delay = _member(archive, DELAY)
            manifest_bytes = _member(archive, MANIFEST)
    except SpectrogramFileRefused:
        raise
    except (ValueError, OSError, zipfile.BadZipFile, EOFError) as broken:
        raise SpectrogramFileRefused(
            f"{path} is not an archive this reader can open: {broken}. The "
            "layout is a ZIP archive of NPY members and is written out in "
            "docs/decisions/spectrogram-file-format.md."
        ) from broken

    manifest = _manifest_from_json_bytes(manifest_bytes)

    try:
        return Spectrogram.of(
            counts=intensity,
            energy_axis_electronvolt=energy,
            delay_axis_attosecond=delay,
            manifest=manifest,
        )
    except SpectrogramRefused as refused:
        # The object's own rules are the file's rules too. A file holding an
        # axis that disagrees with its array is refused here for the reason the
        # object would have refused it, rather than producing an object that
        # skipped the checks because it came from disk.
        raise SpectrogramFileRefused(
            f"{path} does not hold a spectrogram: {refused}"
        ) from refused
