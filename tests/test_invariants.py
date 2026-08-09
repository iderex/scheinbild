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
import unittest
from pathlib import Path

from tools.invariants import (
    RULES,
    network_refusals,
    plotting_refusals,
    random_state_refusals,
    refusals_for,
    wall_refusals,
)

ANALYSIS = Path("src/scheinbild_analysis/reader.py")
MODEL = Path("src/scheinbild_model/field.py")
OUTSIDE = Path("somewhere/else.py")


def parsed(source):
    return ast.parse(source)


def rules(refusals):
    return [refusal.rule for refusal in refusals]


class TheWallIsRefusedInBothDirections(unittest.TestCase):
    def test_the_analysis_importing_the_model_is_refused(self):
        found = list(wall_refusals(ANALYSIS, parsed("import scheinbild_model\n")))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_the_model_importing_the_analysis_is_refused(self):
        found = list(wall_refusals(MODEL, parsed("import scheinbild_analysis\n")))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_a_submodule_of_the_forbidden_package_is_refused(self):
        source = "from scheinbild_model.pulse import Pulse\n"
        found = list(wall_refusals(ANALYSIS, parsed(source)))
        self.assertEqual(rules(found), ["no-crossing-the-model-analysis-wall"])

    def test_each_package_may_import_itself(self):
        # The near miss. A rule that matched the package name anywhere would
        # refuse a module for importing its own neighbour, which is every file
        # in both packages.
        source = "from scheinbild_model.units import electronvolts_to_hartree\n"
        self.assertEqual(list(wall_refusals(MODEL, parsed(source))), [])

    def test_a_name_that_merely_starts_with_the_forbidden_one_is_clean(self):
        # The one character version of the same mistake. Prefix matching without
        # the dot refuses a third party package nobody has a rule about.
        source = "import scheinbild_analysis_helpers\n"
        self.assertEqual(list(wall_refusals(MODEL, parsed(source))), [])

    def test_a_file_in_neither_package_is_not_judged(self):
        source = "import scheinbild_model\n"
        self.assertEqual(list(wall_refusals(OUTSIDE, parsed(source))), [])


class GlobalRandomStateIsRefused(unittest.TestCase):
    def test_importing_the_standard_random_module_is_refused(self):
        found = list(random_state_refusals(MODEL, parsed("import random\n")))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_a_module_level_generator_is_refused(self):
        source = "import numpy\n\nRNG = numpy.random.default_rng()\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_seeding_is_refused(self):
        source = "def go(generator):\n    generator.seed(7)\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_reseeding_the_process_is_refused_even_when_its_result_is_used(self):
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

    def test_the_bare_seed_function_is_refused(self):
        source = "def go():\n    seed(7)\n"
        found = list(random_state_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), ["no-global-random-state"])

    def test_reading_a_seed_out_of_a_manifest_is_clean(self):
        # The other direction of the same rule, and the reason the rule needed
        # a discrimination at all. `Manifest.seed` is the one sanctioned way to
        # read a seed inside src, and a rule matching the name alone refused it,
        # which left the sanctioned way unwritable. An accessor is called for
        # what it returns and the return is used.
        source = 'def go(manifest):\n    return manifest.seed("counting_statistics")\n'
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_seed_read_into_a_name_is_clean_too(self):
        source = (
            "def go(manifest):\n"
            '    value = manifest.seed("counting_statistics")\n'
            "    return value\n"
        )
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_generator_built_inside_a_function_is_clean(self):
        # The near miss, and the shape the rule is asking people to write. Only
        # the module level binding is state a manifest cannot describe.
        source = (
            "import numpy\n\n\ndef draw(seed):\n"
            "    generator = numpy.random.default_rng(seed)\n"
            "    return generator\n"
        )
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])

    def test_a_name_that_merely_starts_with_random_is_clean(self):
        source = "import randomiser\n"
        self.assertEqual(list(random_state_refusals(MODEL, parsed(source))), [])


class ThePlottingImportMustComeAfterTheBackendIsForced(unittest.TestCase):
    def test_importing_pyplot_with_nothing_forced_is_refused(self):
        source = "import matplotlib.pyplot as plt\n"
        found = list(plotting_refusals(MODEL, source, parsed(source)))
        self.assertEqual(
            rules(found), ["no-plotting-import-before-the-backend-is-forced"]
        )

    def test_forcing_the_backend_after_the_import_is_still_refused(self):
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

    def test_forcing_the_backend_first_is_clean(self):
        source = (
            "import matplotlib\n"
            "matplotlib.use('Agg')\n"
            "import matplotlib.pyplot as plt\n"
        )
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])

    def test_the_environment_variable_counts_as_forcing_it(self):
        source = (
            "import os\n"
            "os.environ['MPLBACKEND'] = 'Agg'\n"
            "import matplotlib.pyplot as plt\n"
        )
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])

    def test_importing_the_package_alone_is_clean(self):
        # Importing matplotlib does not select a backend. A rule that refused it
        # would refuse the first line of the only correct pattern there is.
        source = "import matplotlib\n"
        self.assertEqual(list(plotting_refusals(MODEL, source, parsed(source))), [])


THE_EXIT = Path("src/scheinbild_model/publish.py")


NETWORK_RULE = "no-network-capable-import-outside-the-one-exit"


class TheNetworkHasExactlyOneExit(unittest.TestCase):
    def test_importing_socket_anywhere_else_is_refused(self):
        found = list(network_refusals(MODEL, parsed("import socket\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_client_library_is_refused(self):
        found = list(network_refusals(MODEL, parsed("import requests\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_submodule_is_refused(self):
        source = "from urllib.request import urlopen\n"
        found = list(network_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_an_import_inside_a_function_is_refused_too(self):
        # The near miss somebody actually writes. Moving the import into the
        # function that uses it is the ordinary way to make a dependency look
        # optional, and a rule reading only the top of the file passes it.
        source = "def fetch():\n    import socket\n\n    return socket\n"
        found = list(network_refusals(MODEL, parsed(source)))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_the_one_exit_may_import_one(self):
        found = list(network_refusals(THE_EXIT, parsed("import socket\n")))
        self.assertEqual(found, [])

    def test_a_file_called_publish_somewhere_else_is_not_the_exit(self):
        # The exemption is on the path and not on the file name, so a module
        # called publish.py in another package does not inherit it.
        elsewhere = Path("src/scheinbild_analysis/publish.py")
        found = list(network_refusals(elsewhere, parsed("import socket\n")))
        self.assertEqual(rules(found), [NETWORK_RULE])

    def test_a_name_that_merely_starts_with_a_network_module_is_clean(self):
        found = list(network_refusals(MODEL, parsed("import sockets_r_us\n")))
        self.assertEqual(found, [])

    def test_an_ordinary_module_is_clean(self):
        source = "import json\nfrom pathlib import Path\n"
        self.assertEqual(list(network_refusals(MODEL, parsed(source))), [])


class AFileThatCannotBeReadIsNotAFileThatPassed(unittest.TestCase):
    def test_unparsable_source_is_refused_rather_than_skipped(self):
        unreadable = Path(__file__).with_name("no-such-file-exists.py")
        found = list(refusals_for(unreadable))
        self.assertEqual(rules(found), ["source-could-not-be-read"])

    def test_that_refusal_is_not_one_of_the_declared_rules(self):
        # It is the tool saying it could not judge, which is a different thing
        # from a rule being broken, and the run list is what a reader compares
        # a report against.
        self.assertNotIn("source-could-not-be-read", RULES)


if __name__ == "__main__":
    unittest.main()
