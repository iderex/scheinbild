"""Each greppable invariant, with a case that trips it and one that does not.

The neighbouring case is the point of every pair. A rule proved only by
something that could never have passed says the checker can refuse; it does not
say the checker refuses the right thing. So each near miss below is the one
character or one line that somebody will actually get wrong: an import of the
package that does not select a backend, a generator built inside a function
rather than at module level, an import of a name that merely starts with the
forbidden one.

The subjects are source written in the test, parsed here. Nothing reads this
repository's own files to decide a rule, because a case built out of the tree
proves the state of the tree on the day it ran rather than the guard.
"""

import ast
import tempfile
import unittest
from collections.abc import Iterable
from pathlib import Path

from tools.invariants import (
    LITERAL_REGISTER,
    RULES,
    Refusal,
    RegisterUnreadable,
    WaivedSite,
    line_kind_refusals,
    literal_refusals,
    load_literal_register,
    network_refusals,
    plotting_refusals,
    random_state_refusals,
    refusals_for,
    register_dangling_refusals,
    register_refusals,
    wall_refusals,
)

ANALYSIS = Path("src/scheinbild_analysis/reader.py")
MODEL = Path("src/scheinbild_model/field.py")
OUTSIDE = Path("somewhere/else.py")


def parsed(source: str) -> ast.Module:
    return ast.parse(source)


def rules(refusals: Iterable[Refusal]) -> list[str]:
    return [refusal.rule for refusal in refusals]


class TheWallIsRefusedInBothDirections(unittest.TestCase):
    def test_the_analysis_importing_the_model_is_refused(self) -> None:
        found = list(wall_refusals(ANALYSIS, parsed("import scheinbild_model\n")))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_the_model_importing_the_analysis_is_refused(self) -> None:
        found = list(wall_refusals(MODEL, parsed("import scheinbild_analysis\n")))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_a_submodule_of_the_forbidden_package_is_refused(self) -> None:
        source = "from scheinbild_model.pulse import Pulse\n"
        found = list(wall_refusals(ANALYSIS, parsed(source)))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_each_package_may_import_itself(self) -> None:
        # The near miss. A rule that matched the package name anywhere would
        # refuse a module for importing its own neighbour, which is every file
        # in both packages.
        source = "from scheinbild_model.units import electronvolts_to_hartree\n"
        self.assertEqual(list(wall_refusals(MODEL, parsed(source))), [])

    def test_a_name_that_merely_starts_with_the_forbidden_one_is_clean(self) -> None:
        # The one character version of the same mistake. Prefix matching without
        # the dot refuses a third party package nobody has a rule about.
        source = "import scheinbild_analysis_helpers\n"
        self.assertEqual(list(wall_refusals(MODEL, parsed(source))), [])

    def test_a_file_in_neither_package_is_not_judged(self) -> None:
        source = "import scheinbild_model\n"
        self.assertEqual(list(wall_refusals(OUTSIDE, parsed(source))), [])


class GlobalRandomStateIsRefused(unittest.TestCase):
    def test_importing_the_standard_random_module_is_refused(self) -> None:
        found = list(random_state_refusals(MODEL, parsed("import random\n")))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_a_module_level_generator_is_refused(self) -> None:
        source = "import numpy\n\nRNG = numpy.random.default_rng()\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_seeding_is_refused(self) -> None:
        source = "def go(generator):\n    generator.seed(7)\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_reseeding_the_process_is_refused_even_when_its_result_is_used(
        self,
    ) -> None:
        # `numpy.random.seed` returns None, so assigning it is a way of writing
        # a reseed that the discrimination below would otherwise read as an
        # accessor. The named reseeders are refused whatever is done with them.
        source = (
            "import numpy\n\n\ndef go():\n"
            "    kept = numpy.random.seed(7)\n"
            "    return kept\n"
        )
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_the_bare_seed_function_is_refused(self) -> None:
        source = "def go():\n    seed(7)\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_reading_a_seed_out_of_a_manifest_is_clean(self) -> None:
        # The other direction of the same rule, and the reason the rule needed
        # a discrimination at all. `Manifest.seed` is the one sanctioned way to
        # read a seed inside src, and a rule matching the name alone refused it,
        # which left the sanctioned way unwritable. An accessor is called for
        # what it returns and the return is used.
        source = 'def go(manifest):\n    return manifest.seed("counting_statistics")\n'
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_seed_read_into_a_name_is_clean_too(self) -> None:
        source = (
            "def go(manifest):\n"
            '    value = manifest.seed("counting_statistics")\n'
            "    return value\n"
        )
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_generator_built_inside_a_function_is_clean(self) -> None:
        # The near miss, and the shape the rule is asking people to write. Only
        # the module level binding is state a manifest cannot describe.
        source = (
            "import numpy\n\n\ndef draw(seed):\n"
            "    generator = numpy.random.default_rng(seed)\n"
            "    return generator\n"
        )
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_name_that_merely_starts_with_random_is_clean(self) -> None:
        source = "import randomiser\n"
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])


class ThePlottingImportMustComeAfterTheBackendIsForced(unittest.TestCase):
    def test_importing_pyplot_with_nothing_forced_is_refused(self) -> None:
        source = "import matplotlib.pyplot as plt\n"
        found = list(plotting_refusals(MODEL, source, parsed(source)))
        self.assertEqual(
            rules(found), ["no-plotting-import-before-the-backend-is-forced"]
        )

    def test_forcing_the_backend_after_the_import_is_still_refused(self) -> None:
        # The near miss that matters most. The lines are both present, so a rule
        # that only asked whether the file mentions a backend would pass this,
        # and the library has already chosen by the time the second line runs.
        source = (
            "import matplotlib.pyplot as plt\n"
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
        )
        found = list(plotting_refusals(MODEL, source, parsed(source)))
        self.assertEqual(
            rules(found), ["no-plotting-import-before-the-backend-is-forced"]
        )

    def test_forcing_the_backend_first_is_clean(self) -> None:
        source = (
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "import matplotlib.pyplot as plt\n"
        )
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])

    def test_the_environment_variable_counts_as_forcing_it(self) -> None:
        source = (
            "import os\n"
            "os.environ['MPLBACKEND'] = 'Agg'\n"
            "import matplotlib.pyplot as plt\n"
        )
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])

    def test_importing_the_package_alone_is_clean(self) -> None:
        # Importing matplotlib does not select a backend. A rule that refused it
        # would refuse the first line of the only correct pattern there is.
        source = "import matplotlib\n"
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])


THE_EXIT = Path("src/scheinbild_model/publish.py")


NETWORK_RULE = "no-network-capable-import-outside-the-one-exit"


class TheNetworkHasExactlyOneExit(unittest.TestCase):
    def test_importing_socket_anywhere_else_is_refused(self) -> None:
        found = list(network_refusals(MODEL, parsed("import socket\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_client_library_is_refused(self) -> None:
        found = list(network_refusals(MODEL, parsed("import requests\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_submodule_is_refused(self) -> None:
        source = "from urllib.request import urlopen\n"
        found = list(network_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_an_import_inside_a_function_is_refused_too(self) -> None:
        # The near miss somebody actually writes. Moving the import into the
        # function that uses it is the ordinary way to make a dependency look
        # optional, and a rule reading only the top of the file passes it.
        source = "def fetch():\n    import socket\n\n    return socket\n"
        found = list(network_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_the_one_exit_may_import_one(self) -> None:
        found = list(network_refusals(THE_EXIT, parsed("import socket\n")))
        self.assertEqual(found, [])

    def test_a_file_called_publish_somewhere_else_is_not_the_exit(self) -> None:
        # The exemption is on the path and not on the file name, so a module
        # called publish.py in another package does not inherit it.
        elsewhere = Path("src/scheinbild_analysis/publish.py")
        found = list(network_refusals(elsewhere, parsed("import socket\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_name_that_merely_starts_with_a_network_module_is_clean(self) -> None:
        found = list(network_refusals(MODEL, parsed("import sockets_r_us\n")))
        self.assertEqual(found, [])

    def test_an_ordinary_module_is_clean(self) -> None:
        source = "import json\nfrom pathlib import Path\n"
        self.assertEqual(list(network_refusals(MODEL, parsed(source))), [])


LITERAL_RULE = "no-bare-numeric-literal-outside-the-constant-table"
REGISTER_RULE = "the-literal-register-says-only-what-is-true"

THE_TABLE = Path("src/scheinbild_model/constants.py")


def waiver(
    definition: str, literals: tuple[float | int, ...], path: Path = MODEL
) -> WaivedSite:
    return WaivedSite(path.as_posix(), definition, literals, "because the test says so")


class ANumberOutsideTheTableIsRefused(unittest.TestCase):
    def test_a_physics_number_written_into_the_code_is_refused(self) -> None:
        found = list(literal_refusals(MODEL, parsed("BINDING = 48.47\n"), ()))
        self.assertEqual(rules(found), [LITERAL_RULE])

    def test_the_refusal_names_the_definition_it_sits_in(self) -> None:
        source = "class Line:\n    def energy(self):\n        return 48.47\n"
        found = list(literal_refusals(MODEL, parsed(source), ()))
        self.assertIn("Line.energy", found[0].detail)

    def test_zero_and_one_are_allowed_anywhere(self) -> None:
        source = "A = 0\nB = 1\nC = 1.0\nD = 0.0\n"
        self.assertEqual(list(literal_refusals(MODEL, parsed(source), ())), [])

    def test_the_constant_table_is_where_a_number_belongs(self) -> None:
        found = list(literal_refusals(THE_TABLE, parsed("BINDING = 48.47\n"), ()))
        self.assertEqual(found, [])

    def test_a_waived_value_passes(self) -> None:
        register = (waiver("TRANSFORM_LIMIT", (4.0, 2.0)),)
        source = "TRANSFORM_LIMIT = 4.0 * log(2.0)\n"
        self.assertEqual(list(literal_refusals(MODEL, parsed(source), register)), [])

    def test_a_value_the_waiver_does_not_name_is_still_refused(self) -> None:
        # The case the register exists to keep open. A definition already waived
        # for its own algebra is not a place a binding energy may be written.
        register = (waiver("TRANSFORM_LIMIT", (4.0, 2.0)),)
        source = "TRANSFORM_LIMIT = 4.0 * log(2.0) * 48.47\n"
        found = list(literal_refusals(MODEL, parsed(source), register))
        self.assertEqual(rules(found), [LITERAL_RULE])
        self.assertIn("48.47", found[0].detail)

    def test_an_integer_waiver_does_not_cover_the_float_beside_it(self) -> None:
        # The one character version. `2` is a count of dimensions and `2.0` is a
        # coefficient, they are equal in Python, and a register comparing by
        # value alone would let either stand in for the other.
        register = (waiver("Grid.of", (2,)),)
        source = "class Grid:\n    def of(self):\n        return 2.0\n"
        found = list(literal_refusals(MODEL, parsed(source), register))
        self.assertEqual(rules(found), [LITERAL_RULE])

    def test_a_waiver_does_not_reach_the_definition_next_door(self) -> None:
        register = (waiver("First.__init__", (2.0,)),)
        source = (
            "class First:\n    def __init__(self):\n        self.a = 2.0\n\n\n"
            "class Second:\n    def __init__(self):\n        self.a = 2.0\n"
        )
        found = list(literal_refusals(MODEL, parsed(source), register))
        self.assertEqual(rules(found), [LITERAL_RULE])
        self.assertIn("Second.__init__", found[0].detail)

    def test_a_waiver_for_another_file_does_not_reach_this_one(self) -> None:
        register = (waiver("BINDING", (48.47,), path=ANALYSIS),)
        found = list(literal_refusals(MODEL, parsed("BINDING = 48.47\n"), register))
        self.assertEqual(rules(found), [LITERAL_RULE])

    def test_a_flag_is_not_a_numeric_literal(self) -> None:
        # The near miss in the other direction. `True` is an `int` to
        # `isinstance`, and refusing it would refuse every keyword argument in
        # the tree.
        source = "def go():\n    return dict(write=False, copy=True)\n"
        self.assertEqual(list(literal_refusals(MODEL, parsed(source), ())), [])


class TheRegisterSaysOnlyWhatIsTrue(unittest.TestCase):
    def test_a_waiver_whose_literal_is_gone_is_refused(self) -> None:
        register = (waiver("TRANSFORM_LIMIT", (4.0,)),)
        seen = {MODEL.as_posix()}
        found = list(register_refusals(register, {}, seen))
        self.assertEqual(rules(found), [REGISTER_RULE])

    def test_a_waiver_whose_literal_is_still_there_is_clean(self) -> None:
        register = (waiver("TRANSFORM_LIMIT", (4.0,)),)
        seen = {MODEL.as_posix()}
        present: dict[tuple[str, str], set[tuple[str, object]]] = {
            (MODEL.as_posix(), "TRANSFORM_LIMIT"): {("float", 4.0)}
        }
        self.assertEqual(list(register_refusals(register, present, seen)), [])

    def test_a_waiver_for_a_file_this_run_did_not_read_is_left_alone(self) -> None:
        # Not a pass and not a refusal. A run over a narrower root has not
        # cleared the rest of the register, and saying so is what the run's own
        # register line is for.
        register = (waiver("TRANSFORM_LIMIT", (4.0,)),)
        self.assertEqual(list(register_refusals(register, {}, set())), [])

    def test_a_waiver_naming_a_file_that_is_not_there_is_refused(self) -> None:
        register = (waiver("TRANSFORM_LIMIT", (4.0,)),)
        found = list(register_dangling_refusals(register, [Path("src")], set()))
        self.assertEqual(rules(found), [REGISTER_RULE])

    def test_a_waiver_outside_the_roots_is_not_called_dangling(self) -> None:
        register = (waiver("TRANSFORM_LIMIT", (4.0,)),)
        found = list(register_dangling_refusals(register, [Path("tools")], set()))
        self.assertEqual(found, [])


class TheRegisterIsRefusedRatherThanGuessedAt(unittest.TestCase):
    def written(self, text: str) -> Path:
        directory = self.enterContext(tempfile.TemporaryDirectory())
        register = Path(directory) / "register.toml"
        register.write_text(text, encoding="utf-8")
        return register

    def test_the_register_in_the_tree_loads(self) -> None:
        self.assertTrue(load_literal_register(LITERAL_REGISTER))

    def test_an_entry_with_no_reason_is_refused(self) -> None:
        text = '[[site]]\npath = "a.py"\ndefinition = "X"\nliterals = [2.0]\n'
        with self.assertRaises(RegisterUnreadable):
            load_literal_register(self.written(text))

    def test_an_entry_waiving_nothing_is_refused(self) -> None:
        text = (
            '[[site]]\npath = "a.py"\ndefinition = "X"\n'
            'literals = []\nreason = "none"\n'
        )
        with self.assertRaises(RegisterUnreadable):
            load_literal_register(self.written(text))

    def test_an_entry_waiving_something_that_is_not_a_number_is_refused(self) -> None:
        text = (
            '[[site]]\npath = "a.py"\ndefinition = "X"\n'
            'literals = ["48.47"]\nreason = "none"\n'
        )
        with self.assertRaises(RegisterUnreadable):
            load_literal_register(self.written(text))

    def test_a_register_that_cannot_be_read_is_not_an_empty_one(self) -> None:
        with self.assertRaises(RegisterUnreadable):
            load_literal_register(Path("no-such-register.toml"))


class TheModelMayNotKnowWhatKindOfLineALineIs(unittest.TestCase):
    """The rule, the spellings it survives, and the four things it must not touch.

    The near misses here matter more than the hits, and two of them are why the
    rule is written in two halves rather than as one substring. A rule over text
    would refuse every docstring in this tree arguing why the model may not know,
    which is most of the places the argument is written down. A rule refusing the
    word wherever it appeared would refuse the loader for the shipped satellite
    file and the constant holding that file's name, and the repair somebody would
    reach for is to rename the file, which buys the property nothing.

    So a name that carries the word is refused where a value is read off a line,
    and a name that asks what kind a line is, is refused everywhere.
    """

    def test_a_parameter_saying_satellite_is_refused(self) -> None:
        source = "def trace(line, is_satellite):\n    return line\n"
        found = list(line_kind_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_an_attribute_saying_satellite_is_refused(self) -> None:
        source = "def widen(line):\n    return line.satellite\n"
        found = list(line_kind_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_keyword_argument_saying_satellite_is_refused(self) -> None:
        source = "def build(line):\n    return trace(line, satellite=True)\n"
        found = list(line_kind_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_declared_field_saying_satellite_is_refused(self) -> None:
        source = "class Line:\n    is_satellite: bool\n"
        found = list(line_kind_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_branch_on_a_line_saying_what_it_is_is_refused(self) -> None:
        # The shape the rule exists for, written out as somebody would write it
        # the day a satellite turns out to be inconvenient.
        source = (
            "def widen(line, width):\n"
            "    if line.is_satellite:\n"
            "        return width\n"
            "    return width\n"
        )
        found = list(line_kind_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_the_spelling_does_not_save_it(self) -> None:
        for name in ("isSatellite", "IS_SATELLITE", "is_shake_up", "satellite_flag"):
            with self.subTest(name=name):
                source = f"def trace(line, {name}):\n    return line\n"
                found = list(line_kind_refusals(MODEL, parsed(source)))
                self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_name_asking_what_kind_without_the_word_is_refused(self) -> None:
        for name in ("line_kind", "line_type", "line_class", "kind_of_line"):
            with self.subTest(name=name):
                source = f"def trace(line, {name}):\n    return line\n"
                found = list(line_kind_refusals(MODEL, parsed(source)))
                self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_question_defined_rather_than_taken_is_refused(self) -> None:
        # The way past the first half of the rule: ask the question in a
        # function of your own instead of taking the answer as a parameter.
        for source in (
            "def is_satellite(line):\n    return False\n",
            "class IsMainLine:\n    pass\n",
            "SHAKE_UP_FLAG = True\n",
        ):
            with self.subTest(source=source):
                found = list(line_kind_refusals(MODEL, parsed(source)))
                self.assertEqual(rules(found), ["no-line-kind-in-the-model"])

    def test_a_docstring_arguing_the_rule_is_not_refused(self) -> None:
        # The near miss that decides whether this rule can exist at all. The
        # argument for it is written in docstrings in this package, and a rule
        # over text would refuse the sentences that explain it.
        source = (
            '"""A line has no field saying whether it is a satellite, and the\n'
            'model cannot tell a shake-up line from a main line."""\n'
            "def trace(line):\n"
            "    return line\n"
        )
        self.assertEqual(list(line_kind_refusals(MODEL, parsed(source))), [])

    def test_the_loader_for_the_shipped_satellite_file_is_not_refused(self) -> None:
        # Both halves of the real case, which is in `atomic_data`. The file is
        # named by whoever assembles the run and the model never sees the name,
        # so neither of these is a line saying what it is.
        source = (
            'NEON_2P_SHAKE_UP_SATELLITES = "neon-2p-shake-up-satellites.toml"\n'
            "def neon_2p_shake_up_satellites():\n"
            "    return _packaged(NEON_2P_SHAKE_UP_SATELLITES)\n"
        )
        self.assertEqual(list(line_kind_refusals(MODEL, parsed(source))), [])

    def test_a_caller_naming_which_lines_it_supplies_is_not_refused(self) -> None:
        # The one character version. `main line` as a substring would refuse
        # this, which is a caller saying what it assembles rather than a line
        # saying what it is.
        source = 'NEON_MAIN_LINE_NAMES = ("2p", "2s")\n'
        self.assertEqual(list(line_kind_refusals(MODEL, parsed(source))), [])

    def test_an_ordinary_line_is_not_refused(self) -> None:
        source = (
            "def trace(line, energy_axis_electronvolt):\n"
            "    return line.relative_strength\n"
        )
        self.assertEqual(list(line_kind_refusals(MODEL, parsed(source))), [])

    def test_the_analysis_is_not_judged_by_this_rule(self) -> None:
        # Deliberate and stated in the tool. What the standard analysis may know
        # is its own question, and answering it inside a rule about the model
        # would answer it in the wrong file.
        source = "def read(trace, is_satellite):\n    return trace\n"
        self.assertEqual(list(line_kind_refusals(ANALYSIS, parsed(source))), [])

    def test_a_file_in_neither_package_is_not_judged(self) -> None:
        source = "def read(trace, is_satellite):\n    return trace\n"
        self.assertEqual(list(line_kind_refusals(OUTSIDE, parsed(source))), [])

    def test_a_run_over_a_file_applies_the_rule(self) -> None:
        # The wiring, which the cases above do not reach because they call the
        # operator. One missing line in `refusals_for` takes the rule out of
        # every run while the run goes on printing its name, which reads as
        # coverage rather than as a rule nothing applies.
        directory = self.enterContext(tempfile.TemporaryDirectory())
        package = Path(directory) / "src" / "scheinbild_model"
        package.mkdir(parents=True)
        judged = package / "widening.py"
        judged.write_text(
            "def widen(line, is_satellite):\n    return line\n", encoding="utf-8"
        )
        self.assertIn("no-line-kind-in-the-model", rules(refusals_for(judged)))
        self.assertIn("no-line-kind-in-the-model", RULES)


class AFileThatCannotBeReadIsNotAFileThatPassed(unittest.TestCase):
    def test_unparsable_source_is_refused_rather_than_skipped(self) -> None:
        unreadable = Path(__file__).with_name("no-such-file-exists.py")
        found = list(refusals_for(unreadable))
        self.assertEqual(rules(found), ["source-could-not-be-read"])

    def test_that_refusal_is_not_one_of_the_declared_rules(self) -> None:
        # It is the tool saying it could not judge, which is a different thing
        # from a rule being broken, and the run list is what a reader compares
        # a report against.
        self.assertNotIn("source-could-not-be-read", RULES)


if __name__ == "__main__":
    unittest.main()
