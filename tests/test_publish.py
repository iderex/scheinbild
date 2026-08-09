"""The one exit: what it shows, what it asks, and what it refuses to carry.

Nothing here needs a network, and that is a property of the design rather than
of the tests. The sending seam is passed in, so the order of the four steps is
what is exercised: build the payload, show it whole, stop unless the operator
says yes, and only then reach the one place that would leave the host.

The refusal cases are about the allowlist. It is a list of what may go in, so a
field nobody thought about has to be absent by default, and the case that proves
that is a payload with one extra key rather than a payload full of them.
"""

import unittest
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scheinbild_model.manifest import Manifest
from scheinbild_model.publish import (
    ALLOWED_PROVENANCE,
    NAMED_EXCLUSIONS,
    PublishRefused,
    describe,
    provenance_of,
    publish,
    refuse_anything_outside_the_allowlist,
    send,
)
from scheinbild_model.spectrogram import Spectrogram
from scheinbild_model.spectrogram_file import write


def a_manifest() -> Manifest:
    return Manifest.of(
        parameters={"pulse_central_energy_electronvolt": 105.2},
        seeds={"counts": 7},
        code_version="0.0.0",
    )


def a_file(directory: str) -> Path:
    spectrogram = Spectrogram.of(
        counts=np.ones((3, 2)),
        energy_axis_electronvolt=np.array([100.0, 101.0, 102.0]),
        delay_axis_attosecond=np.array([-50.0, 50.0]),
        manifest=a_manifest(),
    )
    return write(spectrogram, Path(directory) / "trace.npz")


class Recorder:
    """A stand in for the terminal and for the sending seam."""

    def __init__(self, answer: str = "yes") -> None:
        self.answer = answer
        self.printed: list[str] = []
        self.asked: list[str] = []
        self.sent: list[tuple[Path, dict[str, object]]] = []

    def out(self, text: str) -> None:
        self.printed.append(text)

    def ask(self, prompt: str) -> str:
        self.asked.append(prompt)
        return self.answer

    def send(self, path: Path, payload: Mapping[str, object]) -> None:
        self.sent.append((path, dict(payload)))

    def transcript(self) -> str:
        return "\n".join(self.printed)


class ThePayloadIsTheAllowlistAndNothingElse(unittest.TestCase):
    def test_it_carries_exactly_the_three_allowed_fields(self) -> None:
        self.assertEqual(
            sorted(provenance_of(a_manifest())), sorted(ALLOWED_PROVENANCE)
        )

    def test_the_digest_is_the_manifest_that_produced_the_file(self) -> None:
        manifest = a_manifest()
        self.assertEqual(provenance_of(manifest)["manifest_digest"], manifest.digest())

    def test_the_parameters_are_not_in_it(self) -> None:
        # Deliberately absent. They are in the file being published; what this
        # command adds beside the file is the three allowlisted fields.
        self.assertNotIn("parameters", provenance_of(a_manifest()))

    def test_one_extra_field_is_refused(self) -> None:
        payload = provenance_of(a_manifest())
        payload["hostname"] = "a-machine"
        with self.assertRaises(PublishRefused) as refusal:
            refuse_anything_outside_the_allowlist(payload)
        self.assertIn("hostname", str(refusal.exception))
        self.assertIn("excluded by name", str(refusal.exception))

    def test_a_field_nobody_named_is_refused_too(self) -> None:
        # The near miss that says the allowlist is a list of what may go in. A
        # rule built as a list of things to strip out passes this.
        payload = provenance_of(a_manifest())
        payload["operator_note"] = "nothing identifying, honestly"
        with self.assertRaises(PublishRefused) as refusal:
            refuse_anything_outside_the_allowlist(payload)
        self.assertIn("operator_note", str(refusal.exception))

    def test_a_payload_missing_a_field_is_refused(self) -> None:
        payload = provenance_of(a_manifest())
        del payload["seeds"]
        with self.assertRaises(PublishRefused) as refusal:
            refuse_anything_outside_the_allowlist(payload)
        self.assertIn("seeds", str(refusal.exception))

    def test_the_allowlisted_payload_passes(self) -> None:
        refuse_anything_outside_the_allowlist(provenance_of(a_manifest()))


class ItSaysWhatItWouldSendBeforeItSendsIt(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = a_file(self.directory.name)

    def test_the_preview_names_every_field_that_would_go(self) -> None:
        payload = provenance_of(a_manifest())
        text = describe(self.path, payload)
        for field in ALLOWED_PROVENANCE:
            self.assertIn(field, text)

    def test_the_preview_carries_the_values_and_not_only_the_names(self) -> None:
        # A preview that lists field names without their values is what the
        # operator will believe and is not what would be sent.
        payload = provenance_of(a_manifest())
        self.assertIn(payload["manifest_digest"], describe(self.path, payload))

    def test_the_preview_names_what_is_excluded(self) -> None:
        text = describe(self.path, provenance_of(a_manifest()))
        for excluded in NAMED_EXCLUSIONS:
            self.assertIn(excluded, text)

    def test_the_preview_is_printed_before_the_question_is_asked(self) -> None:
        recorder = Recorder(answer="no")
        publish(self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send)
        self.assertTrue(recorder.printed, "nothing was shown to the operator")
        self.assertIn("would send", recorder.transcript())
        self.assertTrue(recorder.asked, "the operator was never asked")


class ItStopsUnlessTheOperatorSaysYes(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = a_file(self.directory.name)

    def test_a_no_reaches_no_sender(self) -> None:
        recorder = Recorder(answer="no")
        code = publish(
            self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send
        )
        self.assertEqual(recorder.sent, [])
        self.assertEqual(code, 1)
        self.assertIn("Nothing was sent.", recorder.transcript())

    def test_an_empty_answer_reaches_no_sender(self) -> None:
        # The near miss that matters. Somebody pressing return is the commonest
        # answer there is, and a check written as "not a refusal" sends on it.
        recorder = Recorder(answer="")
        publish(self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send)
        self.assertEqual(recorder.sent, [])

    def test_a_y_is_not_a_yes(self) -> None:
        recorder = Recorder(answer="y")
        publish(self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send)
        self.assertEqual(recorder.sent, [])

    def test_a_yes_reaches_the_sender_with_the_allowlisted_payload(self) -> None:
        recorder = Recorder(answer="yes")
        code = publish(
            self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(recorder.sent), 1)
        sent_path, sent_payload = recorder.sent[0]
        self.assertEqual(sent_path, self.path)
        self.assertEqual(sorted(sent_payload), sorted(ALLOWED_PROVENANCE))

    def test_a_yes_with_surrounding_space_and_capitals_is_a_yes(self) -> None:
        recorder = Recorder(answer="  YES \n")
        publish(self.path, ask=recorder.ask, out=recorder.out, sender=recorder.send)
        self.assertEqual(len(recorder.sent), 1)


class TheSeamRefuses(unittest.TestCase):
    """Nothing leaves this host today, and this is where that is true."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = a_file(self.directory.name)

    def test_the_real_sender_refuses_rather_than_quietly_doing_nothing(self) -> None:
        with self.assertRaises(PublishRefused) as refusal:
            send(self.path, provenance_of(a_manifest()))
        self.assertIn("Nothing was sent", str(refusal.exception))
        self.assertIn("no destination", str(refusal.exception))

    def test_the_seam_checks_the_allowlist_again_at_the_last_moment(self) -> None:
        # Checked where the bytes would leave and not only where the payload is
        # built, so a caller assembling its own payload cannot walk past it.
        payload = provenance_of(a_manifest())
        payload["hostname"] = "a-machine"
        with self.assertRaises(PublishRefused) as refusal:
            send(self.path, payload)
        self.assertIn("hostname", str(refusal.exception))

    def test_the_default_sender_is_the_real_one(self) -> None:
        # The tests above pass a recorder in. This is what says the command an
        # operator runs does not.
        recorder = Recorder(answer="yes")
        with self.assertRaises(PublishRefused):
            publish(self.path, ask=recorder.ask, out=recorder.out)


class ItIsReachableFromNoOtherModule(unittest.TestCase):
    """A command that sends and a command that computes are different commands."""

    def test_nothing_else_in_the_package_imports_it(self) -> None:
        import ast

        package = Path(__file__).resolve().parents[1] / "src" / "scheinbild_model"
        importers = []
        for module in sorted(package.rglob("*.py")):
            if module.name == "publish.py":
                continue
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                if any("publish" in name.split(".") for name in names):
                    importers.append(module.name)
        self.assertEqual(
            importers,
            [],
            "publish is reachable from another module, so producing a result "
            "could send one",
        )


if __name__ == "__main__":
    unittest.main()
