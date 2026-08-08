# The test area

The fourth top level area of the tree, alongside the forward model, the
standard analysis and the documents that record decisions. Tests live here and
not beside the code they exercise, so that the two importable units stay
importable on their own and a test can never be the thing that drags one
package into the other.

The rule every test in the default suite meets is in
[../docs/decisions/test-environment.md](../docs/decisions/test-environment.md):
no display attached, no elevated privileges, on Linux, macOS and Windows. A
test that cannot meet it goes in a separate harness whose name states the
requirement it imposes.

## The runner

`unittest` from the standard library, and the command that runs the suite is in
the README.

Chosen against this board rather than out of habit. The suite has to be
runnable by whoever wants to check a published number, on a clone, on three
operating systems, and the graph an operator installs is the one `uv.lock`
pins. A runner in that graph is a package that has to be resolved, locked and
installed before a single test can run, and it would be the first third party
package this repository carries. A runner in the standard library costs none of
that, so the suite runs on a bare clone and the lockfile stays a statement about
the model's own dependencies.

What that choice gives up is worth naming. The parametrised fixtures and the
assertion rewriting of the usual third party runner are things this suite will
have to write out by hand, and `subTest` is the substitute for the first of
them. The moment that trade stops being worth it is the moment a numerical
suite needs comparisons the standard library cannot express, and changing it
then is a change of one command line in the README and one paragraph here.

## What the harness refuses

`__init__.py` in this directory is the policy, and it is installed by being
imported, which discovery does before it imports any test module. It forces the
plotting backend to a non interactive one, and it refuses a network connection
rather than skipping it, because a skipped network test and a passing one are
the same line in a summary.

Warnings are errors, and that part cannot be installed from inside the suite.
The runner applies its own warning filter around every test unless the process
was started with a `-W` option, so the option is on the command line in the
README and a test in `test_harness_policy.py` fails when it is missing. The
suite refuses the weaker mode rather than running quietly in it.

Each of those rules has a test beside it that fails when the rule is removed,
which is what issue #15 asked for and where the evidence for it is recorded.
