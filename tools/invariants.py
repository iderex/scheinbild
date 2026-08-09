"""Refuse the rules of this board that are properties of its source text.

Some of this board's rules are not about behaviour. They are about what the
source says, and a rule of that shape can be decided by reading the source
rather than by running it. The ones decided here are named below, and the run
prints them rather than leaving a reader to count the headings.

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

`no-bare-numeric-literal-outside-the-constant-table`. Every number that carries
physics lives in one table with its unit and its source, per
docs/decisions/units-and-constants.md, so a number written straight into the code
is a number whose provenance nothing records. Zero and one are allowed
everywhere, because a loop bound and an array index are not constants of the
model. Everything else outside the table is refused unless the register below
carries it.

`the-literal-register-says-only-what-is-true`. The register is the other half of
that rule and it fails closed in both directions: an entry naming a file that is
not there, or waiving a literal the named definition no longer holds, is refused
as loudly as an unwaived literal is.

## The register, and why the rule needs one

What separates a physics number from a Gaussian's twos is where the number came
from, and no reading of the source sees that: `4.0 * log(2.0)` and `48.47` are
the same shape to a parser. Every narrowing that gets the tree green opens a hole
the size of the rule's own target. Allowing the small coefficients lets a cross
section of `0.5` through. Allowing any literal bound to a module level name lets
a binding energy through under a name. A rule that admits the value it exists to
refuse is worse than none, because it reads as coverage.

So the literal stays refused everywhere and a site that has to carry one is
entered in `literals-outside-the-table.toml` beside this file, with the value and
the reason it is not a physics number. The provenance the parser cannot see is
supplied by a person, once, in a file a reviewer reads.

An entry names a path, a definition, the values waived inside it and the reason.
The key is the definition rather than the line, and that is a choice with a cost
on both sides. A line number moves under every edit above it, so a register keyed
on one reddens on changes it is not about and gets deleted; a register keyed on
the definition does not notice a waived literal moving to another line of the
same function. What it does notice is a value appearing that was not waived,
which is the case the rule is for.

Two bounds, stated rather than left to be found. The values are compared as a
set, so a definition waived for `2.0` that grows a second `2.0` is unchanged to
the register, which is why the entries carry the reason and not a count. And a
waived definition is waived for the values written down and for no others, so
`48.47` appearing inside one is refused exactly as it would be anywhere else.

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
caught here. A bare numeric literal in a test is not judged either, and a test is
where a number is most often written down to compare against.

This directory is not read. A scanner has to hold the patterns it refuses, so a
scanner inside its own scope refuses itself. The same is true of the fixtures in
the suite that prove these rules bite, which is the second reason the suite is
out of scope.

The register is judged only where the run can see the files it names. An entry
whose path lies outside the roots this run was given is neither confirmed nor
refused, and the run prints how many entries it judged, so a run over a narrower
root cannot be read as one that cleared the whole register.

There is no waiver for the other three rules. A wall crossing that has to exist
is a decision to be argued in the issue that wants it and not a comment in a
file, and the same goes for a seed the manifest does not describe. The literal
register is the one exception and it exists because that rule is about
provenance, which a parser cannot read, rather than about a shape it can.
"""

import ast
import sys
import tomllib
from collections.abc import Iterable, Iterator
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

# The constant table, as a path tail for the same reason as the one exit. Every
# number that carries physics belongs in it, so it is the one file a numeric
# literal is at home in.
THE_CONSTANT_TABLE = ("scheinbild_model", "constants.py")

# Allowed wherever they appear. A loop bound, an array index and a count of one
# are not constants of the model, which is what
# docs/decisions/units-and-constants.md says the rule is not aimed at. The tuple
# holds no float form, because 0.0 and 1.0 compare equal to these.
LITERALS_THAT_CARRY_NOTHING = (0, 1)

# Where a literal sits when it is not inside any definition or bound to any
# module level name. An import guard or a bare expression at the top of a file.
NOT_IN_A_DEFINITION = "<module>"

# The register of literals that are not physics numbers, beside this file so
# that the rule and the exemptions to it are read together.
LITERAL_REGISTER = Path(__file__).with_name("literals-outside-the-table.toml")


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


class WaivedSite(NamedTuple):
    """One entry of the literal register: where, which values, and why."""

    path: str
    definition: str
    literals: tuple[float | int, ...]
    reason: str


class RegisterUnreadable(ValueError):
    """The register could not be read, which is not the same as it being empty."""


def _is_a_number(value: object) -> bool:
    # `True` is an `int` to `isinstance`, and a flag is not a numeric literal.
    return isinstance(value, (int, float, complex)) and not isinstance(value, bool)


def numeric_literals(tree: ast.Module) -> Iterator[tuple[str, object, int]]:
    """Every numeric literal in a file, with the definition it sits inside.

    The definition is a dotted name, so two methods called `__init__` in one
    module are two sites. A literal in a module level assignment takes the name
    it is assigned to, which is what makes a register entry readable.
    """

    def walk(node: ast.AST, prefix: str) -> Iterator[tuple[str, object, int]]:
        for child in ast.iter_child_nodes(node):
            here = prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                here = f"{prefix}.{child.name}" if prefix else child.name
            elif not prefix and isinstance(child, ast.Assign):
                names = [t.id for t in child.targets if isinstance(t, ast.Name)]
                if names:
                    here = names[0]
            elif (
                not prefix
                and isinstance(child, ast.AnnAssign)
                and isinstance(child.target, ast.Name)
            ):
                here = child.target.id
            if isinstance(child, ast.Constant) and _is_a_number(child.value):
                yield here or NOT_IN_A_DEFINITION, child.value, child.lineno
            yield from walk(child, here)

    yield from walk(tree, "")


def load_literal_register(path: Path) -> tuple[WaivedSite, ...]:
    """The register, or a refusal to guess at what a malformed one meant.

    Every field is required and none has a default. A register that loaded with
    a missing reason would be a register whose entries stop carrying the one
    thing a parser cannot supply.
    """
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as unreadable:
        raise RegisterUnreadable(
            f"{path}: {unreadable}. A register this tool cannot read is not a "
            "register with nothing in it, so the run stops here rather than "
            "clearing every literal in the tree."
        ) from None

    entries = document.get("site", [])
    if not isinstance(entries, list):
        raise RegisterUnreadable(f"{path}: 'site' is not a list of entries.")

    sites = []
    for position, entry in enumerate(entries):
        where = f"{path}: entry {position}"
        if not isinstance(entry, dict):
            raise RegisterUnreadable(f"{where} is not a table.")
        for field in ("path", "definition", "reason"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise RegisterUnreadable(f"{where} has no {field}.")
        literals = entry.get("literals")
        if not isinstance(literals, list) or not literals:
            raise RegisterUnreadable(
                f"{where} waives no literal. An entry that waives nothing is an "
                "entry that has outlived what it was for."
            )
        if not all(_is_a_number(value) for value in literals):
            raise RegisterUnreadable(f"{where} waives something that is not a number.")
        sites.append(
            WaivedSite(
                entry["path"], entry["definition"], tuple(literals), entry["reason"]
            )
        )
    return tuple(sites)


def _waives(site: WaivedSite, value: object) -> bool:
    # Compared by type as well as by value, because 2 and 2.0 are equal in
    # Python and are different things to write down: one is a count and the
    # other is a coefficient.
    return any(
        type(waived) is type(value) and waived == value for waived in site.literals
    )


def literal_refusals(
    path: Path, tree: ast.Module, register: Iterable[WaivedSite]
) -> Iterator[Refusal]:
    if path.parts[-2:] == THE_CONSTANT_TABLE:
        return
    here = [site for site in register if site.path == path.as_posix()]
    for definition, value, line in numeric_literals(tree):
        if value in LITERALS_THAT_CARRY_NOTHING and isinstance(value, (int, float)):
            continue
        if any(site.definition == definition and _waives(site, value) for site in here):
            continue
        yield Refusal(
            "no-bare-numeric-literal-outside-the-constant-table",
            str(path),
            line,
            f"the literal {value!r} in {definition}. Every number that carries "
            "physics lives in the constant table with its unit and its source, "
            "so a number written into the code is a number whose provenance "
            "nothing records. Where this one carries no physics, say so in "
            f"{LITERAL_REGISTER.name} against {path.as_posix()} and "
            f"{definition}. See docs/decisions/units-and-constants.md.",
        )


def _tagged(value: object) -> tuple[str, object]:
    """A literal with its type name, so that 2 and 2.0 stay two things.

    They are equal in Python and they hash alike, so a plain set of values would
    hold only whichever arrived first and the register would call the other one
    stale.
    """
    return type(value).__name__, value


def register_refusals(
    register: Iterable[WaivedSite],
    found: dict[tuple[str, str], set[tuple[str, object]]],
    seen: set[str],
) -> Iterator[Refusal]:
    """The register judged against what the run actually read.

    Only entries whose file this run examined are judged, so a run over a
    narrower root leaves the rest of the register alone rather than calling it
    dangling.
    """
    rule = "the-literal-register-says-only-what-is-true"
    for site in register:
        if site.path not in seen:
            continue
        present = found.get((site.path, site.definition), set())
        for value in site.literals:
            if _tagged(value) in present:
                continue
            yield Refusal(
                rule,
                site.path,
                0,
                f"the register waives the literal {value!r} in {site.definition}, "
                "and that definition does not hold it any more. A waiver that "
                "outlives the site it was written for is a reason nobody can "
                "check, so it is removed rather than kept in case it comes back.",
            )


def register_dangling_refusals(
    register: Iterable[WaivedSite], roots: Iterable[Path], seen: set[str]
) -> Iterator[Refusal]:
    """Entries naming a file that is inside the scope and is not there."""
    inside = [str(root.as_posix()) for root in roots]
    for site in register:
        if site.path in seen:
            continue
        if not any(
            site.path == root or site.path.startswith(root.rstrip("/") + "/")
            for root in inside
        ):
            continue
        yield Refusal(
            "the-literal-register-says-only-what-is-true",
            site.path,
            0,
            f"the register waives {site.definition} in a file this run did not "
            "find. An entry naming a path that is not there waives nothing and "
            "reads as though it does.",
        )


def refusals_for(path: Path, register: Iterable[WaivedSite] = ()) -> Iterator[Refusal]:
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
    yield from literal_refusals(path, tree, register)


RULES = (
    "no-crossing-the-model-analysis-wall",
    "no-global-random-state",
    "no-plotting-import-before-the-backend-is-forced",
    "no-network-capable-import-outside-the-one-exit",
    "no-bare-numeric-literal-outside-the-constant-table",
    "the-literal-register-says-only-what-is-true",
)


def main(argv: list[str]) -> int:
    roots = [Path(argument) for argument in argv] or [Path("src")]
    files = sorted(
        {path for root in roots for path in root.rglob("*.py")},
        key=lambda path: path.as_posix(),
    )

    try:
        register = load_literal_register(LITERAL_REGISTER)
    except RegisterUnreadable as unreadable:
        print(f"::error file={LITERAL_REGISTER}::{unreadable}")
        print(str(unreadable))
        return 1

    refusals = [refusal for path in files for refusal in refusals_for(path, register)]

    seen = {path.as_posix() for path in files}
    found: dict[tuple[str, str], set[tuple[str, object]]] = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            # Already refused above, and a file that would not parse says nothing
            # about the register either way.
            seen.discard(path.as_posix())
            continue
        for definition, value, _ in numeric_literals(tree):
            found.setdefault((path.as_posix(), definition), set()).add(_tagged(value))
    refusals.extend(register_refusals(register, found, seen))
    refusals.extend(register_dangling_refusals(register, roots, seen))

    # Say what was examined. A run that read fewer files than the reader thinks
    # is a run whose silence means something else, so the count and the roots are
    # printed whether or not anything was refused.
    print(f"Examined {len(files)} file(s) under: {', '.join(str(r) for r in roots)}")
    for rule in RULES:
        print(f"  rule: {rule}")
    judged = sum(1 for site in register if site.path in seen)
    print(
        f"  register: {len(register)} entr(y/ies) in {LITERAL_REGISTER.name}, "
        f"{judged} of them inside this run's roots"
    )

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
