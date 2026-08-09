"""Three ways of reading a spectrogram file, and what each one proves.

A round trip is the obvious test and it is not sufficient on its own, because a
writer and a reader that share a mistake agree with each other perfectly. So
there are three.

The round trip proves the pair is self consistent.

The fixture, an archive written earlier and committed, proves the pair has not
moved together since. A writer and a reader changed in one commit pass a round
trip and fail this.

The file built by `tools/write_from_the_document`, which imports nothing from
this repository and not even the numerical library, proves the layout document
says enough for somebody outside this repository to produce a file this
repository reads. That is the only one of the three that tests the document.

The refusal cases are separate from all three. The reader is the part of this
project that touches bytes it did not produce, so what it does with bytes it
cannot accept is a property in its own right.
"""

import json
import struct
import unittest
import zipfile
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scheinbild_model.manifest import Manifest
from scheinbild_model.spectrogram import Spectrogram
from scheinbild_model.spectrogram_file import (
    MEMBERS,
    SpectrogramFileRefused,
    read,
    write,
)
from tools.write_from_the_document import _npy_member, archive_bytes

FIXTURE = Path(__file__).parent / "fixtures" / "spectrogram-written-2026-08-08.npz"


def a_spectrogram() -> Spectrogram:
    return Spectrogram.of(
        counts=np.arange(6.0).reshape(3, 2),
        energy_axis_electronvolt=np.array([100.0, 101.0, 102.0]),
        delay_axis_attosecond=np.array([-50.0, 50.0]),
        manifest=Manifest.of(
            parameters={"pulse_central_energy_electronvolt": 105.2, "label": "clean"},
            seeds={"counts": 7},
            code_version="0.0.0",
        ),
    )


class TheRoundTrip(unittest.TestCase):
    """What a writer and a reader that share a mistake would also pass."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "trace.npz"

    def test_the_array_survives(self) -> None:
        original = a_spectrogram()
        returned = read(write(original, self.path))
        self.assertTrue(np.array_equal(returned.counts, original.counts))

    def test_both_axes_survive(self) -> None:
        original = a_spectrogram()
        returned = read(write(original, self.path))
        self.assertTrue(
            np.array_equal(
                returned.energy_axis_electronvolt, original.energy_axis_electronvolt
            )
        )
        self.assertTrue(
            np.array_equal(
                returned.delay_axis_attosecond, original.delay_axis_attosecond
            )
        )

    def test_the_manifest_survives_exactly(self) -> None:
        # The digest rather than the fields, because the digest is what a freeze
        # record is compared against, and a float that survived to fifteen
        # figures and not to the last bit would pass a field comparison.
        original = a_spectrogram()
        returned = read(write(original, self.path))
        self.assertEqual(returned.manifest.digest(), original.manifest.digest())

    def test_the_suffix_is_applied_when_it_is_missing(self) -> None:
        written = write(a_spectrogram(), Path(self.directory.name) / "trace")
        self.assertEqual(written.suffix, ".npz")
        self.assertTrue(written.exists())

    def test_one_spectrogram_writes_one_archive(self) -> None:
        first = write(a_spectrogram(), Path(self.directory.name) / "a.npz")
        second = write(a_spectrogram(), Path(self.directory.name) / "b.npz")
        with zipfile.ZipFile(first) as one, zipfile.ZipFile(second) as two:
            for name in sorted(MEMBERS):
                self.assertEqual(
                    one.read(f"{name}.npy"),
                    two.read(f"{name}.npy"),
                    f"{name}.npy differs between two writes of one spectrogram",
                )


class TheMembersAreTheOnesTheLayoutNames(unittest.TestCase):
    def test_a_written_file_holds_exactly_the_declared_members(self) -> None:
        # The writer names its members as keyword arguments and the reader
        # compares against the constants, so this is what stops the two from
        # drifting apart without a red row.
        with TemporaryDirectory() as directory:
            written = write(a_spectrogram(), Path(directory) / "trace.npz")
            with zipfile.ZipFile(written) as archive:
                names = {Path(member).stem for member in archive.namelist()}
        self.assertEqual(names, set(MEMBERS))


class TheFixtureWrittenEarlier(unittest.TestCase):
    """The case a round trip cannot catch: both sides moving together.

    The file was written by the writer at the commit that added it and is in the
    tree. A change to the writer and the reader in one commit passes every round
    trip above and fails here.
    """

    def test_the_fixture_is_in_the_tree(self) -> None:
        self.assertTrue(FIXTURE.exists(), f"{FIXTURE} is missing from the tree")

    def test_it_reads_back_to_what_it_was_written_from(self) -> None:
        returned = read(FIXTURE)
        expected = a_spectrogram()
        self.assertTrue(np.array_equal(returned.counts, expected.counts))
        self.assertTrue(
            np.array_equal(
                returned.energy_axis_electronvolt, expected.energy_axis_electronvolt
            )
        )
        self.assertTrue(
            np.array_equal(
                returned.delay_axis_attosecond, expected.delay_axis_attosecond
            )
        )

    def test_its_manifest_still_hashes_the_same(self) -> None:
        self.assertEqual(
            read(FIXTURE).manifest.digest(), a_spectrogram().manifest.digest()
        )


class TheFileBuiltFromTheDocumentAlone(unittest.TestCase):
    """The only test here that is about the document rather than the code."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "outside.npz"
        self.path.write_bytes(
            archive_bytes(
                intensity=[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
                energy_ev=[100.0, 101.0, 102.0],
                delay_as=[-50.0, 50.0],
                manifest={
                    "parameters": {"label": "from the document"},
                    "seeds": {"counts": 7},
                    "code_version": "0.0.0",
                },
            )
        )

    def test_this_repository_reads_it(self) -> None:
        returned = read(self.path)
        self.assertEqual(returned.counts.shape, (3, 2))
        self.assertEqual(returned.manifest.parameter("label"), "from the document")
        self.assertEqual(returned.manifest.seed("counts"), 7)

    def test_the_values_arrive_in_the_documented_axis_order(self) -> None:
        # C order and energy first. A writer that got either wrong produces a
        # transposed picture that a shape check alone would pass if the two
        # dimensions matched, so the values are compared and not just the shape.
        returned = read(self.path)
        self.assertTrue(
            np.array_equal(
                returned.counts, np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
            )
        )

    def test_two_independent_writers_do_not_produce_the_same_bytes(self) -> None:
        # Asserted rather than assumed, because the opposite was assumed first
        # and it is wrong. The document fixes the members, their dtypes, their
        # shapes and the axis order, and it does not fix how the shape is
        # spelled inside the NPY header: this writer produces `(3,2,)` and the
        # numerical library produces `(3, 2)`. Both are valid headers for the
        # same array.
        #
        # So comparing two files byte for byte is a test of who wrote them, not
        # of what they hold. The determinism property that does hold is one
        # writer producing one archive from one spectrogram, which is tested
        # against the writer in this repository above.
        mine = write(
            Spectrogram.of(
                counts=np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
                energy_axis_electronvolt=np.array([100.0, 101.0, 102.0]),
                delay_axis_attosecond=np.array([-50.0, 50.0]),
                manifest=Manifest.of(
                    parameters={"label": "from the document"},
                    seeds={"counts": 7},
                    code_version="0.0.0",
                ),
            ),
            Path(self.directory.name) / "mine.npz",
        )
        with zipfile.ZipFile(mine) as ours, zipfile.ZipFile(self.path) as theirs:
            self.assertNotEqual(
                ours.read("intensity.npy"), theirs.read("intensity.npy")
            )
            # The values are the same even though the bytes are not, which is
            # the half that matters and the half a byte comparison would have
            # hidden behind a red row.
            self.assertTrue(np.array_equal(read(mine).counts, read(self.path).counts))


class AMalformedFileIsRefusedAndSaysWhy(unittest.TestCase):
    """The reader touches bytes it did not produce, so this is its own property."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "broken.npz"

    def valid(self, **overrides: object) -> bytes:
        arguments: dict[str, object] = {
            "intensity": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            "energy_ev": [100.0, 101.0, 102.0],
            "delay_as": [-50.0, 50.0],
            "manifest": {"parameters": {}, "seeds": {}, "code_version": "0.0.0"},
        }
        arguments.update(overrides)
        # Every case in this class replaces one member of a valid file with
        # something the layout does not allow, so the overrides are values
        # the builder does not declare on purpose. That is the subject of
        # the class rather than a slip.
        return archive_bytes(**arguments)  # type: ignore[arg-type]

    def test_bytes_that_are_not_an_archive_are_refused(self) -> None:
        self.path.write_bytes(b"not an archive at all")
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("not an archive this reader can open", str(refusal.exception))

    def test_a_truncated_archive_is_refused(self) -> None:
        whole = self.valid()
        self.path.write_bytes(whole[: len(whole) // 2])
        with self.assertRaises(SpectrogramFileRefused):
            read(self.path)

    def test_a_missing_file_is_refused(self) -> None:
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path.with_name("was-never-written.npz"))
        self.assertIn("could not be read", str(refusal.exception))

    def test_a_missing_member_is_refused(self) -> None:
        source = self.valid()
        with self._rebuilt(source, drop="delay_as.npy") as rebuilt:
            self.path.write_bytes(rebuilt)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("exactly", str(refusal.exception))

    def test_an_extra_member_is_refused_rather_than_ignored(self) -> None:
        # A reader that ignores what it does not recognise is how one version of
        # a format silently drops what a later version added.
        source = self.valid()
        with self._rebuilt(source, add=("surprise.npy", b"\x93NUMPY")) as rebuilt:
            self.path.write_bytes(rebuilt)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("exactly", str(refusal.exception))

    def test_a_manifest_that_is_not_json_is_refused(self) -> None:
        self.path.write_bytes(self.valid())
        rewritten = self._replace_member(
            self.path.read_bytes(), "manifest_json_utf8.npy", _u1_member(b"{not json")
        )
        self.path.write_bytes(rewritten)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("not JSON", str(refusal.exception))

    def test_a_manifest_member_in_the_wrong_dtype_is_refused(self) -> None:
        # Found by removing the guard and watching the suite stay green. A
        # unicode array in this container is UTF-32, so a writer who reached for
        # the obvious string type produces a member whose bytes are not the
        # UTF-8 the layout describes, and every byte of it decodes to something.
        self.path.write_bytes(self.valid())
        rewritten = self._replace_member(
            self.path.read_bytes(),
            "manifest_json_utf8.npy",
            _npy_member("<f8", (2,), struct.pack("<2d", 1.0, 2.0)),
        )
        self.path.write_bytes(rewritten)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("dtype", str(refusal.exception))

    def test_a_two_dimensional_manifest_member_is_refused(self) -> None:
        # Same finding. The layout says one dimensional, and a member shaped as
        # a block of lines still decodes to bytes in row order, so a reader that
        # skipped this would parse a manifest out of a shape the layout forbids.
        self.path.write_bytes(self.valid())
        payload = b'{"parameters":{},"seeds":{},"code_version":"0.0.0"}'
        rewritten = self._replace_member(
            self.path.read_bytes(),
            "manifest_json_utf8.npy",
            _npy_member("|u1", (2, len(payload) // 2), payload),
        )
        self.path.write_bytes(rewritten)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("dimensions", str(refusal.exception))

    def test_a_manifest_that_is_json_but_not_an_object_is_refused(self) -> None:
        # Same finding again. A JSON array parses, so a reader that only caught
        # a decode error would reach the key lookup with a list and fail there
        # with a message about the wrong thing.
        self.path.write_bytes(self.valid())
        rewritten = self._replace_member(
            self.path.read_bytes(), "manifest_json_utf8.npy", _u1_member(b"[1, 2, 3]")
        )
        self.path.write_bytes(rewritten)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("is a list", str(refusal.exception))

    def test_a_manifest_missing_a_key_is_refused(self) -> None:
        self.path.write_bytes(self.valid())
        payload = json.dumps({"parameters": {}, "seeds": {}}).encode("utf-8")
        rewritten = self._replace_member(
            self.path.read_bytes(), "manifest_json_utf8.npy", _u1_member(payload)
        )
        self.path.write_bytes(rewritten)
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("code_version", str(refusal.exception))

    def test_an_axis_that_disagrees_with_the_array_is_refused(self) -> None:
        # The object's rules are the file's rules. A file assembled by hand can
        # hold an axis that does not match its array, and reading one has to
        # refuse for the same reason building one would.
        self.path.write_bytes(self.valid(energy_ev=[100.0, 101.0]))
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("does not hold a spectrogram", str(refusal.exception))

    def test_a_non_uniform_axis_in_a_file_is_refused(self) -> None:
        self.path.write_bytes(self.valid(energy_ev=[100.0, 101.0, 105.0]))
        with self.assertRaises(SpectrogramFileRefused) as refusal:
            read(self.path)
        self.assertIn("not uniform", str(refusal.exception))

    def test_a_well_formed_file_is_still_accepted(self) -> None:
        # The near miss for the whole class. Every case above is one change away
        # from this, so this is what says the refusals are about the change.
        self.path.write_bytes(self.valid())
        self.assertEqual(read(self.path).counts.shape, (3, 2))

    def _rebuilt(
        self,
        source: bytes,
        drop: str | None = None,
        add: tuple[str, bytes] | None = None,
    ) -> AbstractContextManager[bytes]:
        import io as _io
        from contextlib import contextmanager

        @contextmanager
        def rebuild() -> Iterator[bytes]:
            buffer = _io.BytesIO()
            with (
                zipfile.ZipFile(_io.BytesIO(source)) as original,
                zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as rebuilt_archive,
            ):
                for name in original.namelist():
                    if name != drop:
                        rebuilt_archive.writestr(name, original.read(name))
                if add is not None:
                    rebuilt_archive.writestr(add[0], add[1])
            yield buffer.getvalue()

        return rebuild()

    def _replace_member(self, source: bytes, name: str, payload: bytes) -> bytes:
        import io as _io

        buffer = _io.BytesIO()
        with (
            zipfile.ZipFile(_io.BytesIO(source)) as original,
            zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as rebuilt,
        ):
            for member in original.namelist():
                rebuilt.writestr(
                    member, payload if member == name else original.read(member)
                )
        return buffer.getvalue()


def _u1_member(payload: bytes) -> bytes:
    """One `|u1` NPY member holding exactly these bytes, built as the layout says."""
    return _npy_member("|u1", (len(payload),), payload)


if __name__ == "__main__":
    unittest.main()
