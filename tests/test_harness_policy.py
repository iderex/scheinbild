"""The suite's tests of its own policy.

A harness that has never refused anything is an unmeasured harness. These tests
are what make the policy in tests/__init__.py a property of the suite rather
than a paragraph about it: each one fails if its rule is removed, and each one
fails for the rule it names.

They import nothing from this repository's packages. That is deliberate. The
suite has to be runnable on a clone where nothing is installed yet, so a broken
install cannot make the harness look broken.
"""

import os
import socket
import sys
import unittest
import warnings

from tests import NetworkAccessRefused


class WarningsAreErrors(unittest.TestCase):
    """Warnings are errors, and this is the only place that can hold it.

    The policy module cannot install this one. unittest's own runner wraps every
    test in warnings.catch_warnings() and applies its own filter, which is
    "default" unless the process was started with a -W option, so a filter set
    at import time is discarded for the duration of the run. The one thing that
    survives is a -W on the command line, because unittest leaves the filters
    alone when sys.warnoptions is not empty.

    So this test is the enforcement. Run the suite without warnings as errors
    and it fails, which is the suite refusing the weaker mode rather than
    quietly running in it. The command that satisfies it is in the README.
    """

    def test_a_warning_is_an_error(self):
        with self.assertRaises(UserWarning):
            warnings.warn("The suite must be run with warnings as errors.")

    def test_the_run_carries_the_option_that_makes_that_true(self):
        # Named separately from the test above so that a failure says which of
        # the two facts is missing: the mode, or the reason the mode holds.
        self.assertTrue(
            sys.warnoptions,
            "The suite was started without a -W option, so unittest applies its "
            "own warning filter and a warning is not an error. See the command "
            "in the README.",
        )


class TheNetworkIsRefused(unittest.TestCase):
    """A test that reaches for the network fails, and is not skipped.

    The address below is the discard port on the loopback interface. Nothing
    listens there and nothing is sent to it: the refusal is raised in place of
    the connection, so this test proves the guard without a packet leaving the
    machine.
    """

    address = ("127.0.0.1", 9)

    def test_connect_is_refused(self):
        with socket.socket() as sock, self.assertRaises(NetworkAccessRefused):
            sock.connect(self.address)

    def test_connect_ex_is_refused(self):
        with socket.socket() as sock, self.assertRaises(NetworkAccessRefused):
            sock.connect_ex(self.address)

    def test_the_refusal_says_which_rule_it_is(self):
        with socket.socket() as sock, self.assertRaises(NetworkAccessRefused) as caught:
            sock.connect(self.address)
        message = str(caught.exception)
        self.assertIn("default test suite may not use the network", message)
        self.assertIn("skipped network test", message)

    def test_the_standard_library_reaches_the_same_refusal(self):
        # create_connection is the path urllib and everything above it take, so
        # this is the case that says the two patched methods cover more than a
        # test calling connect directly.
        with self.assertRaises(NetworkAccessRefused):
            socket.create_connection(self.address, timeout=1)


class ThePlottingBackendIsForced(unittest.TestCase):
    """The backend is chosen before anything can import a plotting library.

    No plotting library is installed and none is imported here. The property
    that matters is the one a library would read on import, so that is what is
    asserted. A test that imported the library to ask it would be a test that
    could only run once the dependency exists, and the failure it guards
    against happens before that.
    """

    def test_the_backend_is_non_interactive(self):
        self.assertEqual(os.environ.get("MPLBACKEND"), "Agg")


if __name__ == "__main__":
    unittest.main()
