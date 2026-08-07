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

The harness itself, and the proof that it can refuse a property rather than
merely observe one, is issue #15. This file marks the area and states what it
is for; it does not choose the runner.
