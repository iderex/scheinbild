"""Refuse the rules of this board that are properties of its source text.

Some of this board's rules are not about behaviour. They are about what the
source says, and a rule of that shape can be decided by reading the source
rather than by running it. Four of them are decided here.

`no-crossing-the-model-analysis-wall`. The standard analysis may not import the
forward model, and the forward model may not import the analysis. This is the
invariant the boundary in docs/decisions/model-analysis-boundary.md depends on.

`no-global-random-state`. A run is fully described by its manifest, including
every seed it consumes, per docs/decisions/determinism-and-seeding.md. Global
random state is state no manifest describes.

That rule has to tell two calls apart that a name alone cannot. `generator.seed(7)`
reseeds a generator, which is the thing being refused. `manifest.seed("draw")`
reads a recorded seed out of the description of the run, which is the thing being
required, and refusing it left the one sanctioned way to read a seed unwritable
inside `src`. What separates them is not the name at the end of the chain but
what the call is for: a reseed is made for its effect and its result is dropped,
an accessor is made for its result and the result is used. So a `.seed(...)` call
whose value is discarded is refused, and one whose value is assigned, returned or
passed on is not. The names that reseed global state outright are refused either
way, because `_ = numpy.random.seed(7)` uses a value and is still the thing the
rule exists for.

The bound on that, stated rather than left to be found: a reseed written so that
its `None` is consumed walks through, `[g.seed(7) for g in generators]` being the
shape that does it. What is caught is every reseed written the way anybody writes
one, and the rule is a floor here as it is for the network.

`no-plotting-import-before-the-backend-is-forced`. A plotting library that picks
an interactive backend opens a window in a suite that never asked for one, per
docs/decisions/test-environment.md. A library that has already chosen a backend
does not choose again, so the choice has to come first in the file.

`no-network-capable-import-outside-the-one-exit`. No code path a normal run
reaches makes a network call, and publishing off the host is a separate command,
per docs/decisions/what-leaves-the-host.md. The exit is
`scheinbild_model/publish.py` and every other module is refused a network capable
import.

That rule is a floor and its limit is stated where it is decided rather than left
for a reader to assume. It catches a direct import of a module that can open a
connection. It does not catch a call reached through something else: an import
inside a function body is caught, because the reading is of the whole file, but a
network call made by a dependency this tree imports for another reason is not,
and neither is one reached by name at runtime. What would go further is an import
graph over the installed packages, which is a different tool.

The one exit imports nothing from the list either, because it has no transport.
The exemption is on the file rather than on any import in it, so the day a
transport lands the exemption is already where it belongs and the rest of the
tree is unchanged.

## The fourth rule, and why it is not here

Issue #19 names a fourth: no bare numeric literal outside the constant table. It
is not decided here, and the reason is measured rather than preferred. A checker
refusing every literal outside that module refuses thirteen sites in `src`, and
every one of them is a coefficient of the model's own algebra or a modelling
threshold, which is exactly what docs/decisions/units-and-constants.md says the
rule is not aimed at.

The narrowings that get the tree green each open a hole the size of the rule's
own target. Allowing the small coefficients lets a cross section of `0.5`
through. Allowing any literal bound to a module level name lets a binding energy
through under a name. What separates a physics number from a Gaussian's twos is
where the number came from, and no reading of the source sees that: `4.0 *
log(2.0)` and `48.47` are the same shape to a parser.

So the rule is unenforced today and issue #58 holds it, with the thirteen sites,
the commands that found them, and what each of the workable answers costs. This
paragraph is the disclosure: a green run of this tool says nothing about a bare
numeric literal.

## What decides them, and why it is not grep

The rules are properties of the text, and they are read with `ast` from the
standard library rather than with a regular expression. The reason is false
positives. A grep for an import cannot tell one inside a docstring from one the
interpreter will execute, and a gate that reddens on a sentence somebody wrote
in a comment is a gate that gets switched off. The module is in the standard
library, so this costs the tree no dependency.

## The scope, and what is outside it

The scope is the paths given on the command line, and the gate gives it `src`.
So the two importable units are read and nothing else is.

That leaves three things out, named here rather than left to be discovered.

The test suite is not read. Its own policy module already forces the plotting
backend and refuses a network connection, and it holds those rules for itself in
a place a test can prove. A plotting import in a future test is therefore not
caught here.

This directory is not read. A scanner has to hold the patterns it refuses, so a
scanner inside its own scope refuses itself. The same is true of the fixtures in
the suite that prove these rules bite, which is the second reason the suite is
out of scope.

There is no waiver. A wall crossing that has to exist is a decision to be argued
in the issue that wants it and not a comment in a file, and the same goes for a
seed the manifest does not describe.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

# Importing one of these selects a backend. Importing `matplotlib` itself does
# not, which is why the bare package is absent from this tuple: the correct
# pattern is to import it, force the backend, and only then import the module
# that would have chosen one.
BACKEND_SELECTING_MODULES = ("matplotlib.pyplot", "pylab", "seaborn", "plotly")

# Either of these, earlier in the same file, is the backend being forced.
BACKEND_FORCING_MARKERS = ("matplotlib.use(", "MPLBACKEND")

# Each package may not import the other. Both directions, because the wall is
# not one sided even though only one direction is the experiment.
WALLS = {
    "scheinbild_analysis": "scheinbild_model",
    "scheinbild_model": "scheinbild_analysis",
}

RANDOM_STATE_FACTORIES = ("default_rng", "RandomState", "Random")

# Calls that reseed process wide random state, refused wherever they appear and
# whatever is done with what they return. Written as whole chains rather than as
# a tail, so that the discrimination below is what decides every other `.seed`.
GLOBAL_RESEEDERS = (
    "random.seed",
    "np.random.seed",
    "numpy.random.seed",
    "seed",
)

# Importing any of these puts a connection within reach of the module that did
# it. The list is what the standard library and the common third party clients
# offer, and it is a floor rather than a proof: a module reaching a network some
# other way is not caught, which the docstring above says in its own words.
NETWORK_CAPABLE_MODULES = (
    "socket",
    "ssl",
    "http",
    "urllib",
    "ftplib",
    "imaplib",
    "poplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
    "webbrowser",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
)

# The one module allowed to reach the network, as a path tail rather than as a
# module name, so a file somewhere else that happens to be called publish.py is
# not exempted with it.
THE_ONE_EXIT = ("scheinbild_model", "publish.py")


class Refusal(NamedTuple):
    """One refused subject. The rule is named; the pattern is not the message."""

    rule: str
    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def _package_of(path: Path) -> str | None:
    for part in path.parts:
        if part in WALLS:
            return part
    return None


def _imported_names(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Every module name this file imports, with the line it is imported on."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            # A relative import has no module name to compare against a wall,
            # and it cannot reach the other package either way.
            if node.module is not None and node.level == 0:
                yield node.module, node.lineno


def wall_refusals(path: Path, tree: ast.Module) -> Iterator[Refusal]:
    package = _package_of(path)
    if package is None:
        return
    forbidden = WALLS[package]
    for name, line in _imported_names(tree):
        if name == forbidden or name.startswith(forbidden + "."):
            yield Refusal(
                "no-crossing-the-model-analysis-wall",
                str(path),
                line,
                f"{package} may not import {forbidden}. The analysis is meant to "
                "be blind to the generator, and a number produced by an analysis "
                "that can see it is about this repository rather than about the "
                "field. See docs/decisions/model-analysis-boundary.md.",
            )


def _attribute_chain(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _calls_made_for_their_effect(tree: ast.Module) -> set[ast.Call]:
    """Every call in this file whose value is thrown away.

    A call standing alone as a statement was made for what it does and not for
    what it returns, which is what a reseed is and what an accessor is not.
    """
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    }


def random_state_refusals(path: Path, tree: ast.Module) -> Iterator[Refusal]:
    detail = (
        "a run is fully described by its manifest, and every seed it consumes is "
        "in there. Global random state is state no manifest describes, so two "
        "runs of one manifest stop being byte identical. Take a seeded generator "
        "as a parameter instead. See docs/decisions/determinism-and-seeding.md."
    )
    reading = (
        " Reading a seed out of a manifest is the other call this rule used to "
        "refuse with it, and it is refused no longer: an accessor is called for "
        "what it returns, so use the value rather than dropping it."
    )
    rule = "no-global-random-state"
    for name, line in _imported_names(tree):
        if name == "random" or name.startswith("random."):
            yield Refusal(rule, str(path), line, f"importing {name}: {detail}")
    for_their_effect = _calls_made_for_their_effect(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = _attribute_chain(node.func)
        if called in GLOBAL_RESEEDERS:
            yield Refusal(rule, str(path), node.lineno, f"calling {called}: {detail}")
        elif called.endswith(".seed") and node in for_their_effect:
            yield Refusal(
                rule,
                str(path),
                node.lineno,
                f"calling {called} and dropping what it returns: {detail}{reading}",
            )
    for node in tree.body:
        # Module level only. A generator built inside a function is a local one,
        # which is the shape this rule is asking for.
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                called = _attribute_chain(inner.func)
                if called.split(".")[-1] in RANDOM_STATE_FACTORIES:
                    yield Refusal(
                        rule,
                        str(path),
                        node.lineno,
                        f"a module level {called}: {detail}",
                    )


def _is_the_one_exit(path: Path) -> bool:
    return path.parts[-2:] == THE_ONE_EXIT


def network_refusals(path: Path, tree: ast.Module) -> Iterator[Refusal]:
    if _is_the_one_exit(path):
        return
    for name, line in _imported_names(tree):
        reaches = any(
            name == module or name.startswith(module + ".")
            for module in NETWORK_CAPABLE_MODULES
        )
        if not reaches:
            continue
        yield Refusal(
            "no-network-capable-import-outside-the-one-exit",
            str(path),
            line,
            f"importing {name} puts a connection within reach of a module a run "
            "can reach. The network has exactly one exit, "
            f"{'/'.join(THE_ONE_EXIT)}, which the operator invokes on purpose and "
            "which says what it is about to send before it sends it. See "
            "docs/decisions/what-leaves-the-host.md.",
        )


def plotting_refusals(path: Path, source: str, tree: ast.Module) -> Iterator[Refusal]:
    forced_on = None
    for number, text in enumerate(source.splitlines(), start=1):
        if any(marker in text for marker in BACKEND_FORCING_MARKERS):
            forced_on = number
            break
    for name, line in _imported_names(tree):
        selects = any(
            name == module or name.startswith(module + ".")
            for module in BACKEND_SELECTING_MODULES
        )
        if not selects:
            continue
        if forced_on is not None and forced_on < line:
            continue
        yield Refusal(
            "no-plotting-import-before-the-backend-is-forced",
            str(path),
            line,
            f"{name} selects a backend when it is imported, and nothing earlier "
            "in this file forces a non interactive one. A library that has "
            "already chosen does not choose again, so this opens a window on the "
            "machine that has one. See docs/decisions/test-environment.md.",
        )


def refusals_for(path: Path) -> Iterator[Refusal]:
    """Every refusal against one file, or the one that says it could not be read."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as unreadable:
        # Fail closed. A file this tool cannot read is not a file it has cleared.
        yield Refusal(
            "source-could-not-be-read",
            str(path),
            0,
            f"{unreadable}. A file that cannot be parsed has not been checked, "
            "and this run does not pass it by default.",
        )
        return
    yield from wall_refusals(path, tree)
    yield from random_state_refusals(path, tree)
    yield from plotting_refusals(path, source, tree)
    yield from network_refusals(path, tree)


RULES = (
    "no-crossing-the-model-analysis-wall",
    "no-global-random-state",
    "no-plotting-import-before-the-backend-is-forced",
    "no-network-capable-import-outside-the-one-exit",
)


def main(argv: list[str]) -> int:
    roots = [Path(argument) for argument in argv] or [Path("src")]
    files = sorted(
        {path for root in roots for path in root.rglob("*.py")},
        key=lambda path: path.as_posix(),
    )

    refusals = [refusal for path in files for refusal in refusals_for(path)]

    # Say what was examined. A run that read fewer files than the reader thinks
    # is a run whose silence means something else, so the count and the roots are
    # printed whether or not anything was refused.
    print(f"Examined {len(files)} file(s) under: {', '.join(str(r) for r in roots)}")
    for rule in RULES:
        print(f"  rule: {rule}")

    if not refusals:
        print("No refusals.")
        return 0

    for refusal in refusals:
        print(f"::error file={refusal.path},line={refusal.line}::{refusal}")
        print(str(refusal))
    print(f"{len(refusals)} refusal(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
