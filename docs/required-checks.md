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

    git grep -n '^    name:' origin/main -- .github/workflows
    origin/main:.github/workflows/dco.yml:30:    name: DCO sign-off
    origin/main:.github/workflows/install.yml:40:    name: Install and import (${{ matrix.os }})
    origin/main:.github/workflows/locked-dependencies.yml:43:    name: Locked dependencies
    origin/main:.github/workflows/scorecard.yml:50:    name: Scorecard analysis
    origin/main:.github/workflows/unicode-guard.yml:27:    name: Reject Trojan Source Unicode
    origin/main:.github/workflows/zizmor.yml:44:    name: Audit workflows (zizmor)

That command finds six lines and the published set is larger, in two ways it
cannot show.

The install job carries a matrix, so its one name expands into one check run per
platform: `Install and import (ubuntu-latest)`, `Install and import
(macos-latest)` and `Install and import (windows-latest)`.

One job has no display name at all, deliberately, so no line of the output above
belongs to it:

    git grep -n 'name:' origin/main -- .github/workflows/dependency-review.yml
    origin/main:.github/workflows/dependency-review.yml:1:name: Dependency review
    origin/main:.github/workflows/dependency-review.yml:16:  # No `name:` on this job: the "Protect main" ruleset's required status check
    origin/main:.github/workflows/dependency-review.yml:18:  # ("dependency-review") when no `name:` is set. Overriding it here would
    origin/main:.github/workflows/dependency-review.yml:27:      - name: Dependency review

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

Listed here because a configuration written today would not find them, and
because the names are already fixed by the issues that own them. Each of these is
a name the board intends to publish and does not:

`Test suite`, or whatever issue #16 lands as. Intended to block once it exists.

`Lint and format`, `Type check` and `Docs format`, from issue #17. All three
intended to block.

`Analyze (python)` and `Enforce greppable invariants`, from issue #19. Both
intended to block. The second one is where several of this board's own rules are
refused, including the import boundary in
[decisions/model-analysis-boundary.md](decisions/model-analysis-boundary.md), so a
merge possible while it is red is a merge possible while those rules are off.

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

## One disagreement between this document and the tree

The comment quoted above says the check run name is matched by the "Protect main"
ruleset's required status check. There is no ruleset of that name here, the one
ruleset is named `gate`, and it carries no required status check for that name or
any other. The comment describes a configuration this repository does not have.

The reason for not repairing it here is that this document changes no workflow
file and no setting, which is issue #21's own boundary. The repair is issue #47.
The comment's technical point is correct and is the reason that job still has no
display name: the check run name defaults to the job id, so a name added there
would change the string a future configuration has to match.
