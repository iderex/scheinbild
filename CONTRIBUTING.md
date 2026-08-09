# Contributing

This board builds a forward model of streaking and runs the standard analysis
over its output, to find out what that analysis returns when a known true delay
goes in. If you arrived because you want to check that result, this file is what
the repository expects of you.

## What the project promises you first

Everything in the default test suite runs with no display attached and with no
elevated privileges, on Linux, macOS and Windows. Your machine needs nothing
special, nothing will open a window while the suite runs, and nothing will ask
you to approve a privileged operation. That is a promise to you, not an internal
policy, and the reasoning behind it is in
[docs/decisions/test-environment.md](docs/decisions/test-environment.md).

A test that cannot meet that promise does not go in the default suite. It goes
in a separate harness whose name states the requirement it imposes.

## Install

The interpreter version is pinned under `requires-python` in
[pyproject.toml](pyproject.toml), and that field is the only place in the tree
where the number is written. Read it there. An install on any other interpreter
is refused before anything is built.

On Linux and macOS:

    python -m venv .venv
    .venv/bin/python -m pip install --editable .

On Windows:

    python -m venv .venv
    .venv\Scripts\python -m pip install --editable .

That resolves dependencies fresh, which is what you want while reading the code.
To install the exact graph the gate is green about, which is what you want while
reproducing a number:

    uv sync --locked

It fails rather than quietly updating the lockfile.

## Run the suite

On Linux and macOS:

    .venv/bin/python -W error -m unittest discover --start-directory tests --top-level-directory .

On Windows:

    .venv\Scripts\python -W error -m unittest discover --start-directory tests --top-level-directory .

The runner is `unittest` from the standard library, so the suite needs no
package the install above did not already give you. It does need the install
itself: the suite has tests that import `scheinbild_model`, and on a clone where
nothing has been installed those fail to import rather than fail an assertion.
The reasoning behind the runner is in [tests/README.md](tests/README.md).

Three parts of that command line are load bearing. A run without them passes and
means less, and the summary line looks the same either way.

`-W error` makes a warning fail the run. It has to be on the command line and
cannot be set from inside the suite, because the runner applies its own warning
filter around every test and discards one set at import time. The suite carries
a test that fails when the option is missing, so a run in the weaker mode says
so rather than passing quietly.

`--start-directory tests` is the whole of the default suite. A test that needs
something this project promises you will not need, a display or an elevated
privilege, goes in a separate directory whose name states that requirement, and
discovery started here cannot reach it.

`--top-level-directory .` is what lets the runner import the `tests` package, and
importing that package is what installs the policy the suite runs under: the
plotting backend forced to a non interactive one, and a network connection
refused rather than skipped. Each part of that policy has a test beside it that
fails when the part is removed.

Run it yourself before you push. A pull request also runs it on all three
platforms, under the check names in the next section, but the run that saves you
a round trip is the one on your own machine.

## What the gate checks

The workflows in [.github/workflows/](.github/workflows/) are the authority for
what runs. What follows is what each check means, so that a red one tells you
something.

`DCO sign-off`. Every non-merge commit in the pull request carries a
`Signed-off-by:` trailer matching its own author. Red means at least one commit
does not. `git commit -s` writes the trailer; `git rebase --signoff <base>` adds
it to commits that already exist.

`Install and import (ubuntu-latest)`, `Install and import (macos-latest)` and
`Install and import (windows-latest)`. On each platform, a clean checkout runs
the install commands this file gives you for that platform and then imports both
packages. Red means a fresh clone does not install, or installs and does not
import, on that operating system. It is the check most likely to be red for a
reason that has nothing to do with what you changed, because it is the one that
notices when a path or an interpreter assumption holds on two platforms and not
on the third. The job derives the interpreter version out of `requires-python`
rather than restating it, so a change to the shape of that line stops the job
instead of testing some other interpreter.

`Test suite (ubuntu-latest)`, `Test suite (macos-latest)` and `Test suite
(windows-latest)`. On each platform, the suite runs under the command this file
gives you above, with `--verbose` added so the log names the tests rather than
printing dots. Red means a test failed, or a warning was raised, on that
operating system. Three names rather than one, because the promise at the top of
this file is about three platforms and a suite run on one of them says nothing
about the other two.

That job installs from `uv.lock` rather than resolving fresh, which is the one
place it differs from `Install and import`. So a green suite is a statement about
the locked graph, the one you get from `uv sync --locked` while reproducing a
number, and a green install is a statement about a fresh resolve, the one you
get from the install commands above while reading the code. Both are worth
having and neither implies the other.

`Lint and format`. Two legs under one name. The linter runs the rule set under
`[tool.ruff.lint]` in `pyproject.toml`, and the formatter is asked whether the
tree differs from what it would produce. Red means one of the two has something
to say, and the failure prints the command that repairs it. Neither leg rewrites
your branch: a gate that formats the code it is judging has changed the thing it
was judging. Run both yourself first:

    uv sync --locked --group check
    uv run --group check ruff check .
    uv run --group check ruff format .

`Type check`. The checker runs strict over the paths named by `files` under
`[tool.mypy]` in `pyproject.toml`, which are the forward model, the standard
analysis and the tools the gate runs. The test suite is not among them and does
not type check today; issue #56 carries the count and the work. So a green row
here is a statement about what that line names, and not about the suite.
Reproduce it with `uv run --group check mypy`.

`Docs format`. Four properties of tracked Markdown: LF line endings in the
stored bytes, no line ending in whitespace, a final newline, and no hard tab.
Red means one of them is broken, and the failure names the file, the line and
the rule. Three of the four are repaired by `python -m tools.docs_format --fix`;
a hard tab is not, because what replaces one depends on what it was standing in
for.

This leg is not a Markdown formatter and does not judge heading style, list
markers, link form, the width prose wraps at, or whether a code block is
indented or fenced. Why it stops there is written at the top of
`tools/docs_format.py`. It reads the bytes git stores rather than your working
copy, which is what keeps a checkout with different line endings from reporting
every document in the tree as broken.

`Enforce greppable invariants`. The rules that are properties of the source text
rather than of its behaviour: the import boundary between the forward model and
the standard analysis, global random state, the plotting import against the
backend being forced, the one exit the network has, and the numeric literal that
belongs in the constant table. Red means one of them was broken, and the message
names the rule and what failure it prevents rather than the pattern it matched.
Reproduce with `python -m tools.invariants src`. That run prints the rules it
applied, which is what a reader should compare a report against rather than the
sentence above, because a list in a document drifts against the tool that
decides it.

The scope is `src`. The suite is not read, and neither is `tools/`, for reasons
written at the top of `tools/invariants.py`.

The literal rule has a register beside the checker,
`tools/literals-outside-the-table.toml`, holding every number in `src` that is
not a physics number, with the reason it is not. Provenance is what separates
`4.0 * log(2.0)` from a binding energy and a parser cannot see it, so a person
writes it down once. The register fails closed in both directions: a value not
written there is refused wherever it appears, including inside a definition that
is waived for its other values, and a value written there that the definition no
longer holds is refused as a waiver that has outlived its site. Adding a physics
number to the code and an entry here rather than a row to the table is a thing a
reviewer refuses, not a thing the checker can.

`Analyze (python)`. The standard code scanning analysis. On a numerical board
its findings will mostly be about file handling and deserialisation rather than
about the physics, so a quiet report is not a statement about the model.

`Locked dependencies`. Two properties. The lockfile agrees with the dependencies
declared in `pyproject.toml`, and installation in the gate resolves nothing and
installs exactly what the lockfile says. Red means one of the two is false, and
the failure message names `uv.lock` and the command that regenerates it. The
check never regenerates or commits anything, because the drifted file is the
evidence for what caused the drift.

`dependency-review`. Any known vulnerability, at low severity or above, in a
dependency this pull request introduces or upgrades. Red means the advisory
database has something to say about a package you are adding.

`Reject Trojan Source Unicode`. Bidirectional and invisible Unicode control
characters in tracked text. These make source render differently from how it
executes, which hides logic from whoever reads the diff. Red means such a
character is in the tree. This name arrives twice on a pull request opened from a
branch in this repository, once for the push and once for the pull request, so
two rows carry it and reading the first one is not reading the check.

`Audit workflows (zizmor)`. Static analysis of the workflow files themselves.
Red means a workflow you touched has an actionable security finding: an unpinned
action, an over-broad permission, a template injection. Keep actions pinned to a
commit SHA with the version in a comment, keep checkout on
`persist-credentials: false`, and grant write permissions per job rather than at
the workflow level.

Results also appear in the code scanning tab. Those are findings to triage, not
a gate. Code scanning also publishes its own row, named `zizmor`, beside the
job's row; the job is what fails the pull request.

One workflow is deliberately absent from this list. `Scorecard analysis` runs on
`main`, on a schedule and when the ruleset changes, and has no pull request
trigger, so your pull request will not show it. What this section covers is what
your own pull request publishes.

None of the names above stops a merge. The ruleset on the default branch
carries no required status check, so a red row and a green one are the same row
to the merge button. Which of them were meant to block, and what the setting
would be, is written down in
[docs/required-checks.md](docs/required-checks.md).

## What a change to a frozen parameter costs

Milestone 7 freezes the model choices before the analysis is run over the output.
Once that has landed, a change to a frozen value is not a normal patch and it is
not made by editing the frozen file and moving on.

It is made by adding a new freeze record. The old record is never edited and
never deleted. The new one carries what was wrong and how it was found. A result
already published under the superseded freeze stays published under the freeze
it was produced under, and is not retroactively reattributed to the new one.

That is expensive on purpose. The whole argument of this board is that a model
tuned until it produces the expected answer has proved only that it can be
tuned, and a freeze that could be quietly amended would prove nothing at all.
The mechanism, and the plain statement of what it does not catch, is in
[docs/decisions/pre-registration.md](docs/decisions/pre-registration.md).

Until milestone 7 lands there is no frozen file, so this section describes a
cost nothing charges yet.

## Opening a pull request

The template asks for three things and one question. What changed. What failure
it prevents. The command that produced any number in the body, run at the commit
you are pushing rather than in your working tree. And whether the change touches
a frozen parameter, because that is the one class of change whose cost is not
visible in the diff.

A number without its command is a claim. Write it as a claim, or run the command
and paste what it printed.

Keep one topic per pull request. A change carrying two unrelated things has a
description of one of them.

## Sign-off

Every commit needs a `Signed-off-by:` trailer matching its author. `git commit -s`
writes it. The `DCO sign-off` check refuses a pull request where any commit
lacks one, so this is enforced rather than requested.

Whether this repository accepts changes from outside it at all, and under what
terms, is entry 4 in issue #1 and is not answered. This section does not guess.
It describes the sign-off the gate already enforces on every commit that reaches
a pull request here, and it gets the rest of its content when that entry is
answered.

One part of that entry is worth knowing before you start work. A contribution
that changes a model parameter after the freeze is not a normal patch, and what
happens to such a change is part of what is still open.

The [DCO](DCO) text the trailer refers to speaks of the open source licence
indicated in the file. That licence is AGPL-3.0 and its text is in
[LICENSE](LICENSE), so the clause points at something. Until entry 1 of issue #1
was answered it pointed at nothing, and this paragraph said so. The DCO text
itself is reproduced verbatim because it is a standard document and editing it
would make it something else.
