# Which checks main is meant to require

Written for issue #21.

A gate that runs and a gate that blocks are different things, and the difference
is invisible from a green pull request. Both look like a list of ticks. This
document is the record of which of those ticks were meant to be able to stop a
merge, so that whoever configures the protection has a list to configure from, and
so that a later reader can compare what is required against what was meant to be.

Nothing here changes any repository setting. This document has no force.

## What is configured today

Nothing requires any check. That is the state of the repository, not a
simplification of it:

    gh api repos/iderex/scheinbild/rulesets --jq '.[] | "\(.id) \(.name) \(.target) \(.enforcement)"'
    20529585 gate branch active

    gh api repos/iderex/scheinbild/rulesets/20529585 --jq '{bypass: .bypass_actors, rules: [.rules[].type]}'
    {"bypass":[],"rules":["deletion","non_fast_forward","pull_request"]}

One ruleset, active on the default branch, with no bypass actors. It refuses a
deletion of the branch, refuses a non fast forward push, and requires changes to
arrive as a pull request. There is no `required_status_checks` rule in it, so
every check name below can be red at the moment a merge button is pressed and
nothing in the repository objects.

The pull request rule it does carry requires zero approving reviews, so it
enforces the shape of the change and not that anybody read it.

## The checks published today

Derived from the workflow files rather than remembered:

    git grep -n '^    name:' HEAD -- .github/workflows
    HEAD:.github/workflows/checks.yml:46:    name: Lint and format
    HEAD:.github/workflows/checks.yml:86:    name: Type check
    HEAD:.github/workflows/checks.yml:118:    name: Docs format
    HEAD:.github/workflows/dco.yml:30:    name: DCO sign-off
    HEAD:.github/workflows/install.yml:42:    name: Install and import (${{ matrix.os }})
    HEAD:.github/workflows/locked-dependencies.yml:43:    name: Locked dependencies
    HEAD:.github/workflows/scorecard.yml:50:    name: Scorecard analysis
    HEAD:.github/workflows/test.yml:51:    name: Test suite (${{ matrix.os }})
    HEAD:.github/workflows/unicode-guard.yml:27:    name: Reject Trojan Source Unicode
    HEAD:.github/workflows/zizmor.yml:44:    name: Audit workflows (zizmor)

The reference is `HEAD` rather than `origin/main` because the branch this
paragraph is on is where the list last changed, and quoting the mainline there
would be a claim about a tree that does not yet carry the file.

That command finds ten lines and the published set is larger, in two ways it
cannot show.

Two jobs carry a matrix, so each of those names expands into one check run per
platform: `Install and import (ubuntu-latest)`, `Install and import
(macos-latest)`, `Install and import (windows-latest)`, `Test suite
(ubuntu-latest)`, `Test suite (macos-latest)` and `Test suite
(windows-latest)`.

One job has no display name at all, deliberately, so no line of the output above
belongs to it:

    git grep -n 'name:' HEAD -- .github/workflows/dependency-review.yml
    HEAD:.github/workflows/dependency-review.yml:1:name: Dependency review
    HEAD:.github/workflows/dependency-review.yml:16:  # This job carries no `name:` on purpose, and the reason is what an edit here
    HEAD:.github/workflows/dependency-review.yml:36:      - name: Dependency review

The reference is `HEAD` for the same reason it is `HEAD` above: the branch
carrying this paragraph is also the branch that rewrote that comment, and
quoting the mainline would be a claim about a tree that does not yet carry the
edit.

Its check run takes the job id, so the name a configuration would have to match
is `dependency-review`, in lower case with a hyphen, and it is the one name in the
list that does not look like the others.

## Each name, its intended level, and what that level costs

`DCO sign-off`. Intended to block. Without it a commit with no sign-off reaches
the mainline and the trailer cannot be added afterwards without rewriting
history, so this is the one check whose failure gets more expensive with time.
Cost of blocking: none worth stating.

`Install and import (ubuntu-latest)`, `Install and import (macos-latest)`,
`Install and import (windows-latest)`. All three intended to block, as three
separate requirements rather than one. Requiring only one of them would leave the
promise in `CONTRIBUTING.md` untested on the other two platforms, and the whole
reason the matrix has three legs is that a path assumption holds on two of them
and not on the third. Cost of blocking: this is the check most likely to be red
for a reason unrelated to the change, because it is the one that notices a
platform difference, so blocking on it will occasionally stop work that is
correct. That cost is accepted. The alternative is a green pull request that
means less than it appears to.

`Test suite (ubuntu-latest)`, `Test suite (macos-latest)`, `Test suite
(windows-latest)`. All three intended to block, as three separate requirements
for the same reason the install legs are three. The headless and no elevation
promise is a claim about three platforms, and Windows is where a suite quietly
starts wanting a privilege it was promised not to need, so a configuration
requiring only the Linux leg would leave that promise untested exactly where it
is most likely to break. Cost of blocking: every red test stops every merge,
including a merge that would have fixed something else. That cost is the point.

`Lint and format`. Intended to block. Both legs are cheap and both catch the
class of defect that is otherwise argued about in review instead of decided.
Cost of blocking: a formatter upgrade can move the tree under a branch that did
not touch it, which is why the version is pinned exactly rather than by range,
and an upgrade is then a change with a diff somebody chose to make.

`Type check`. Intended to block. The argument for it on this board is the axis
order defect, which produces a plausible wrong picture rather than a crash. Cost
of blocking: it covers what `files` under `[tool.mypy]` names and not the test
suite, so requiring it protects the model and leaves the suite where issue #56
found it, and a reader who takes the green row for whole-tree coverage has read
more into it than it says.

`Docs format`. Intended to block. It refuses four properties of the stored bytes
of tracked Markdown, each of which is invisible to the person who writes it and
visible to everyone who reads the next diff. Cost of blocking: it is the check
most likely to stop a change for a reason unrelated to it, because the defects
it names arrive from an editor's settings rather than from anything anybody
decided. It is also the narrowest of the three, and what it does not judge is
written at the top of `tools/docs_format.py` rather than left to be inferred
from a green row.

`Enforce greppable invariants`. Intended to block. This is where several of this
board's own rules are refused, including the import boundary in
[decisions/model-analysis-boundary.md](decisions/model-analysis-boundary.md), so a
merge possible while it is red is a merge possible while those rules are off.
Cost of blocking: it reads `src` and nothing else, and one of the four rules
issue #19 names is not enforced at all, which issue #58 holds. Requiring it buys
three rules over two packages and not the fourth, and a reader who takes the row
for all four has read more into it than it says.

`Analyze (python)`. Intended to block. Cost of blocking: its query pack moves on
its own, so it can turn red on a branch that changed nothing, and on this board
most of what it has to say is about file handling rather than about the model.

`Locked dependencies`. Intended to block. A merged change whose lockfile has
drifted makes the next clean clone install a graph nobody tested, and the drift
is cheap to fix at the moment it is noticed and awkward once it is on the
mainline. Cost of blocking: a legitimate dependency change needs the lockfile
regenerated in the same pull request, which is one extra command.

`dependency-review`. Intended to block. It only has anything to say when a change
adds or upgrades a dependency, so it is silent on almost every pull request here.
Cost of blocking: the advisory database is external and moves on its own, so this
is the check that can turn red on a branch that has not changed. That is the
correct behaviour and it is still a cost.

`Reject Trojan Source Unicode`. Intended to block. It refuses characters that
make source render differently from how it executes, which is the one defect
class a reader cannot catch by reading. Cost of blocking: this name arrives twice
on a pull request opened from a branch in this repository, once for the push event
and once for the pull request event. A configuration requiring the name is
satisfied by the runs that carry it, and a reader who checks only the first row
has not read the check.

`Audit workflows (zizmor)`. Intended to block. The workflow files decide what the
gate does, so a change to them is the change least safe to land unaudited. Cost
of blocking: it pins the audit tool's version, so an upgrade of that tool can
turn a finding on in a file nobody touched.

`Scorecard analysis`. Intended to run on a schedule, and cannot block. It has no
pull request trigger at all, which is deliberate: publishing its result is only
valid from the default branch. Cost of the schedule: between two runs there is a
window in which the supply chain hygiene of the mainline is unmeasured, and a
change that lowers it is invisible until the next run. That window is the price
of a check that cannot be published from a pull request, and the mitigation is
that its findings are triage material rather than a gate.

`zizmor`, published by code scanning. Intended to run without blocking, and it
appears beside the job's row under a name of its own. Cost: two rows carrying
similar names, one of which stops a merge and one of which does not, which is
exactly the confusion this document exists to remove. The job is the gate. The
code scanning row is a view of the same findings.

## Names that are planned and are not published yet

None today. This section held the names issue #17 and issue #19 had fixed and
not yet published, and both have landed, so every name the board has settled on
is in the list above. It is kept rather than deleted because the next issue that
fixes a name before publishing it belongs here, and a section that exists is
easier to add a line to than one somebody has to notice is missing.

A name being published is not the same as the rule behind it being enforced. One
rule issue #19 names has no check at all, which issue #58 holds and which the
`Enforce greppable invariants` entry above states in place of leaving the row to
imply otherwise.

## The assumption this list rests on

How much of the gate runs per pull request at all is entry 5 in issue #1 and is
open. The plan assumes the middle option there: the cheap legs run on every pull
request and the expensive ones on a schedule. Every intended level above is
written under that assumption and is not an answer to it. If the answer is that
everything runs on every pull request, the schedule row disappears and the
expensive legs join the blocking list. If the answer is that the expensive legs
run on demand, then a run that never happened leaves the same trace as one that
was green, and this document would have to say so about each of them.

## The setting a person would have to change

The `gate` ruleset on the default branch, id `20529585`, under Settings, Rules,
Rulesets. Adding the rule that requires status checks to pass, and listing the
names above that are marked as intended to block, is what would give this
document force. Until somebody does that, this file records an intention and the
merge button does not read it.

## A disagreement this document used to carry, and how it was settled

The comment on that job used to say the check run name was matched by the
"Protect main" ruleset's required status check. There is no ruleset of that name
here, the one ruleset is named `gate`, and it carries no required status check
for that name or any other, so the sentence described a configuration this
repository does not have. This document recorded the disagreement and left the
repair to issue #47, because issue #21's own boundary was that it changed no
workflow file and no setting.

Issue #47 rewrote the comment. What was correct in it survives, because the
technical point was never the wrong part: a check run takes the job id when no
display name is set, so a display name added to that job would change the string
a future configuration has to match, and that is still the reason the job carries
none. What the comment now says about the present is that nothing matches the
string, which is what the ruleset output at the top of this document shows.

The rest of that file was swept at the same time. The comment on
`fail-on-severity` said a vulnerable dependency blocks the pull request, which is
the same error one step smaller: the setting fails the job, and a failed job here
stops nothing.
