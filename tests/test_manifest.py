"""The manifest is the only place a parameter comes from, and its hash holds still.

Two properties are under test and they fail in different ways.

A parameter the manifest does not carry has to be unreachable rather than
defaulted. A default is a value that influences the output and is not in the
description of the run, and the run that is then published cannot be rebuilt
from what was published with it.

The hash has to be stable for every reason that is not a change of parameters.
The freeze record is built on it, so a hash that moves because a key was written
in a different order, or because a float was rendered differently, or because
the run happened on another machine, would make every frozen result need
re-freezing after a change that touched nothing. Nobody keeps doing that, and a
mechanism nobody keeps doing is not a mechanism.

The last of those three is the one a single machine cannot prove on its own.
What stands in for it is a digest written out as a literal in this file: the
suite runs on ubuntu-latest, macos-latest and windows-latest, so three platforms
compare their own arithmetic against the same string, and a platform that hashed
differently would go red rather than agree with itself.
"""

import unittest

from scheinbild_model.manifest import (
    CANONICAL_FORM_VERSION,
    Manifest,
    ManifestRefused,
    ParameterNotInManifest,
    SeedNotInManifest,
)

# A manifest with one of every kind of value in it, and the digest it produces.
# The digest is written out rather than computed here on purpose. Computing it
# would compare this machine with itself and pass on every platform whatever
# each of them did.
_FIXED_PARAMETERS = {
    "photon_energy_electronvolt": 105.2,
    "delay_steps": 41,
    "chirp_present": False,
    "line_set": "neon-2s-2p",
}
_FIXED_SEEDS = {"counting_statistics": 20260808, "detector_noise": 0}
_FIXED_CODE_VERSION = "0.0.0"
_FIXED_DIGEST = "d9a3db1aa19c977d3215fd78bb47d30b8dd7970cfd92ccd3cb66cff12b81d738"


def _fixed_manifest() -> Manifest:
    return Manifest.of(
        parameters=dict(_FIXED_PARAMETERS),
        seeds=dict(_FIXED_SEEDS),
        code_version=_FIXED_CODE_VERSION,
    )


class AParameterComesFromTheManifestOrFromNowhere(unittest.TestCase):
    """The arrangement that makes the manifest complete rather than intended."""

    def test_a_parameter_in_the_manifest_is_readable(self):
        manifest = _fixed_manifest()
        self.assertEqual(manifest.parameter("photon_energy_electronvolt"), 105.2)
        self.assertEqual(manifest.seed("counting_statistics"), 20260808)

    def test_a_parameter_not_in_the_manifest_is_refused(self):
        manifest = _fixed_manifest()
        with self.assertRaises(ParameterNotInManifest) as refusal:
            manifest.parameter("pulse_duration_attosecond")
        # The message names what the manifest does carry, so the failure says
        # what to add rather than only that something is missing.
        self.assertIn("pulse_duration_attosecond", str(refusal.exception))
        self.assertIn("photon_energy_electronvolt", str(refusal.exception))

    def test_a_seed_not_in_the_manifest_is_refused(self):
        manifest = _fixed_manifest()
        with self.assertRaises(SeedNotInManifest):
            manifest.seed("a_seed_nobody_declared")

    def test_there_is_no_default_to_fall_back_to(self):
        # The refusal above is only worth having if there is no second way to
        # ask. A default argument on either reader would be exactly the value
        # that influences the output and is not in the manifest.
        manifest = _fixed_manifest()
        with self.assertRaises(TypeError):
            manifest.parameter("pulse_duration_attosecond", 0.0)
        with self.assertRaises(TypeError):
            manifest.seed("a_seed_nobody_declared", 0)

    def test_a_run_cannot_edit_its_own_description(self):
        manifest = _fixed_manifest()
        with self.assertRaises(TypeError):
            manifest.parameters["photon_energy_electronvolt"] = 90.0
        with self.assertRaises(TypeError):
            manifest.seeds["counting_statistics"] = 1
        with self.assertRaises(Exception):
            manifest.code_version = "0.0.1"


class TheManifestRefusesWhatCouldNotDescribeARun(unittest.TestCase):
    """Each refusal on its own, so a failure names the rule that stopped biting."""

    def test_a_manifest_with_no_code_version_is_refused(self):
        for version in ("", "   "):
            with self.subTest(version=version):
                with self.assertRaises(ManifestRefused):
                    Manifest.of(parameters={}, seeds={}, code_version=version)

    def test_a_nameless_parameter_is_refused(self):
        with self.assertRaises(ManifestRefused):
            Manifest.of(parameters={"  ": 1.0}, seeds={}, code_version="0.0.0")

    def test_a_name_carrying_a_separator_is_refused(self):
        # A tab or a newline in a name could be built to collide with a
        # different manifest, because those are what the canonical form uses to
        # separate its fields.
        for name in ("a\tb", "a\nb", "a\rb"):
            with self.subTest(name=name):
                with self.assertRaises(ManifestRefused) as refusal:
                    Manifest.of(parameters={name: 1.0}, seeds={}, code_version="0.0.0")
                self.assertIn("collide", str(refusal.exception))

    def test_a_string_value_carrying_a_separator_is_refused(self):
        with self.assertRaises(ManifestRefused):
            Manifest.of(
                parameters={"line_set": "neon\t2s"},
                seeds={},
                code_version="0.0.0",
            )

    def test_a_value_with_no_machine_independent_rendering_is_refused(self):
        for value in ([1.0, 2.0], {"a": 1}, None, (1.0,), complex(1, 2)):
            with self.subTest(value=value):
                with self.assertRaises(ManifestRefused):
                    Manifest.of(
                        parameters={"a_parameter": value},
                        seeds={},
                        code_version="0.0.0",
                    )

    def test_a_non_finite_parameter_is_refused(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ManifestRefused):
                    Manifest.of(
                        parameters={"a_parameter": value},
                        seeds={},
                        code_version="0.0.0",
                    )

    def test_a_seed_that_is_not_a_whole_number_is_refused(self):
        for value in (1.5, "7", True, None):
            with self.subTest(value=value):
                with self.assertRaises(ManifestRefused):
                    Manifest.of(
                        parameters={},
                        seeds={"a_seed": value},
                        code_version="0.0.0",
                    )

    def test_a_negative_seed_is_refused(self):
        with self.assertRaises(ManifestRefused):
            Manifest.of(parameters={}, seeds={"a_seed": -1}, code_version="0.0.0")


class TheHashDoesNotMoveForAReasonThatIsNotAParameter(unittest.TestCase):
    """Everything the digest has to ignore."""

    def test_reordering_the_keys_does_not_move_the_hash(self):
        forwards = _fixed_manifest()
        backwards = Manifest.of(
            parameters={
                name: _FIXED_PARAMETERS[name]
                for name in reversed(list(_FIXED_PARAMETERS))
            },
            seeds={name: _FIXED_SEEDS[name] for name in reversed(list(_FIXED_SEEDS))},
            code_version=_FIXED_CODE_VERSION,
        )
        # The insertion orders really are different, so this is not comparing a
        # dict with itself.
        self.assertNotEqual(list(forwards.parameters), list(backwards.parameters))
        self.assertEqual(forwards.digest(), backwards.digest())

    def test_the_same_value_written_differently_does_not_move_the_hash(self):
        # 0.1 + 0.2 and the decimal that prints for it are the same double.
        # A rendering that shortened either would make them hash differently.
        first = Manifest.of(
            parameters={"a_parameter": 0.1 + 0.2},
            seeds={},
            code_version="0.0.0",
        )
        second = Manifest.of(
            parameters={"a_parameter": 0.30000000000000004},
            seeds={},
            code_version="0.0.0",
        )
        self.assertEqual(first.digest(), second.digest())

    def test_a_change_of_one_bit_moves_the_hash(self):
        first = Manifest.of(
            parameters={"a_parameter": 0.3}, seeds={}, code_version="0.0.0"
        )
        second = Manifest.of(
            parameters={"a_parameter": 0.30000000000000004},
            seeds={},
            code_version="0.0.0",
        )
        self.assertNotEqual(first.digest(), second.digest())

    def test_a_whole_number_and_a_float_of_the_same_value_hash_differently(self):
        # A count of one and a length of one are different parameters. Without
        # the type tag in the canonical form they would render the same, and a
        # manifest that turned one into the other would be indistinguishable
        # from the one it replaced.
        whole = Manifest.of(
            parameters={"a_parameter": 1}, seeds={}, code_version="0.0.0"
        )
        fractional = Manifest.of(
            parameters={"a_parameter": 1.0}, seeds={}, code_version="0.0.0"
        )
        self.assertNotEqual(whole.digest(), fractional.digest())

    def test_a_signed_zero_is_not_the_same_run_as_an_unsigned_one(self):
        # Written down rather than left to be discovered. The two are different
        # bit patterns and they can produce different output, so they are
        # different runs here, even though they compare equal.
        positive = Manifest.of(
            parameters={"a_parameter": 0.0}, seeds={}, code_version="0.0.0"
        )
        negative = Manifest.of(
            parameters={"a_parameter": -0.0}, seeds={}, code_version="0.0.0"
        )
        self.assertNotEqual(positive.digest(), negative.digest())

    def test_a_change_of_code_version_moves_the_hash(self):
        later = Manifest.of(
            parameters=dict(_FIXED_PARAMETERS),
            seeds=dict(_FIXED_SEEDS),
            code_version="0.0.1",
        )
        self.assertNotEqual(_fixed_manifest().digest(), later.digest())

    def test_a_seed_is_part_of_the_run(self):
        other = Manifest.of(
            parameters=dict(_FIXED_PARAMETERS),
            seeds={"counting_statistics": 1, "detector_noise": 0},
            code_version=_FIXED_CODE_VERSION,
        )
        self.assertNotEqual(_fixed_manifest().digest(), other.digest())


class TheHashIsTheSameOnEveryPlatform(unittest.TestCase):
    """The digest of one fixed manifest, written out as a literal.

    This is the only test here that a single machine cannot prove anything with
    on its own. The suite runs on ubuntu-latest, macos-latest and
    windows-latest, so a platform whose float rendering, line ending or sort
    order differed would fail this rather than agree with itself.
    """

    def test_the_fixed_manifest_hashes_to_the_recorded_digest(self):
        self.assertEqual(_fixed_manifest().digest(), _FIXED_DIGEST)

    def test_the_canonical_form_is_what_was_hashed(self):
        # The form is readable rather than trusted, so two manifests that hash
        # differently can be diffed to find out where.
        form = _fixed_manifest().canonical_form()
        self.assertTrue(form.startswith(CANONICAL_FORM_VERSION + "\n"))
        self.assertNotIn("\r", form)
        self.assertIn("parameter\tphoton_energy_electronvolt\tfloat\t", form)
        self.assertIn("seed\tcounting_statistics\tint\t20260808", form)


if __name__ == "__main__":
    unittest.main()
