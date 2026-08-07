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

There is no suite yet.

That is stated as a fact rather than left for you to discover. The test harness,
and the proof that it can refuse a property rather than merely observe one, is
issue #15, and until it lands there is no command here to give you. This section
gets the command when the harness does. Nothing in this file describes a suite
that does not exist.

## What the gate checks

The workflows in [.github/workflows/](.github/workflows/) are the authority for
what runs. What follows is what each check means, so that a red one tells you
something.

`DCO sign-off`. Every non-merge commit in the pull request carries a
`Signed-off-by:` trailer matching its own author. Red means at least one commit
does not. `git commit -s` writes the trailer; `git rebase --signoff <base>` adds
it to commits that already exist.

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
character is in the tree.

`Audit workflows (zizmor)`. Static analysis of the workflow files themselves.
Red means a workflow you touched has an actionable security finding: an unpinned
action, an over-broad permission, a template injection. Keep actions pinned to a
commit SHA with the version in a comment, keep checkout on
`persist-credentials: false`, and grant write permissions per job rather than at
the workflow level.

Results also appear in the code scanning tab. Those are findings to triage, not
a gate.

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
indicated in the file. This repository has no licence yet, which is entry 1 in
issue #1 and is also unanswered, so that clause currently points at nothing. The
text is reproduced verbatim because it is a standard document and editing it
would make it something else. This paragraph is the disclosure rather than a
repair.
