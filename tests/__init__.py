"""The default test suite, and the policy every test in it runs under.

Importing this package installs the policy. Test discovery starts here, so the
policy is in force before any test module is imported, which is the only moment
at which some of it can be installed at all.

The rules this file makes true, and the reason each one is here rather than in a
document:

The plotting backend is forced to a non interactive one. Forced, not defaulted:
a value inherited from the environment is exactly the interactive backend this
suite must not pick up. It happens at import of this package, before any test
module can import a plotting library, because a library that has already chosen
a backend does not choose again.

A network connection is refused. Refused rather than skipped: a skipped network
test and a passing one are the same line in a summary, so a test that reaches for
a socket fails and says why.

Warnings are errors. That one cannot be installed from here, and the test module
next to this file explains why and refuses a run that does not have it. An
invalid value or a division warning from numerical code is the signal this
project can least afford to let scroll past.

No display and no elevation are the rule in
../docs/decisions/test-environment.md. Nothing here needs either, and nothing
here checks that the machine has neither, because a check for the absence of a
display is a check this suite would have to acquire a display library to make.
"""

import os
import socket
from typing import Any, NoReturn

# Forced rather than defaulted. os.environ.setdefault here would honour an
# interactive backend that happened to be in the environment, which is the one
# value this suite exists to refuse.
os.environ["MPLBACKEND"] = "Agg"


class NetworkAccessRefused(RuntimeError):
    """A test reached for the network. The default suite may not need one.

    Raised in place of the connection rather than around it, so no packet
    leaves and no name is looked up. The rule is in
    ../docs/decisions/test-environment.md and in the suite's own README.
    """


_REFUSAL = (
    "The default test suite may not use the network. This connection was "
    "refused before it was attempted, by the policy in tests/__init__.py. A "
    "test that needs a network does not belong in the default suite, and a "
    "skipped network test is indistinguishable from a passing one."
)


def _refuse(sock: socket.socket, address: object) -> NoReturn:
    # The socket is closed before the refusal is raised. A refused socket is
    # unusable anyway, and a caller inside the standard library that was
    # expecting an OSError does not close it on the way out, which leaves a
    # ResourceWarning to surface later from a finaliser and be reported against
    # whichever test happened to be running at the time.
    sock.close()
    raise NetworkAccessRefused(f"{_REFUSAL} Address: {address!r}.")


# The address is `Any` rather than the union the standard library declares. What
# these two replace is reached with a host and port pair, a path, a tuple with a
# scope identifier in it and more besides, depending on the family the caller
# opened, and none of that is read here: the refusal happens before the address
# is used for anything except being printed back. A narrower annotation would be
# a claim about which callers are covered, and the point of patching the two
# methods rather than the callers is that it does not depend on knowing them.
def _refuse_connect(self: socket.socket, address: Any, /) -> NoReturn:
    _refuse(self, address)


def _refuse_connect_ex(self: socket.socket, address: Any, /) -> NoReturn:
    _refuse(self, address)


# socket.create_connection and everything in the standard library that opens an
# outbound connection, urllib included, reaches one of these two. Patching the
# two methods therefore covers the paths a test would realistically take,
# without this file having to enumerate them.
#
# What it does not cover is stated rather than left to be discovered: a name
# lookup on its own is not refused here, because socket.getaddrinfo is reached
# by code that is doing nothing of the kind, and a suite that cannot resolve a
# name fails in places that have no network in them at all.
#
# `method-assign` is suppressed rather than avoided, and the two lines are the
# whole mechanism of the refusal. Replacing a method on a class is what the
# checker is warning about in general, and here it is the point: the standard
# library builds `socket.socket` itself, so a subclass reaches nothing, and a
# wrapper around every caller is the enumeration the comment above says this
# arrangement exists not to need. The suppression names the two codes the
# replacement raises and no others, `method-assign` for replacing a method at
# all and `assignment` for the signature not matching the one being replaced, so
# anything else that goes wrong on these lines is still reported.
#
# `setattr` would silence the same error without a suppression and was not used
# for that reason. It performs the identical assignment and hides it from the
# checker instead of declaring it, which turns a suppression a reader can see
# into one nobody can.
socket.socket.connect = _refuse_connect  # type: ignore[method-assign,assignment]
socket.socket.connect_ex = _refuse_connect_ex  # type: ignore[method-assign,assignment]
