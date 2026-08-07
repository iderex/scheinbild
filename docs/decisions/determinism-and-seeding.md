# Determinism and seeding

Decided in issue #8.

A published number from this board has to be re-derivable by someone who was not
there. That is a stronger requirement than the run producing similar output
twice, and it is the requirement this document fixes.

## The rule

A run is fully described by its manifest.

The manifest carries every seed the run consumes.

Two runs of the same code against the same manifest produce byte identical
output.

No part of the model reads a clock, a process identifier, an environment
variable, or a global random state.

## Byte identical rather than approximately equal

Chosen deliberately. An equality with a tolerance is a place a real change can
hide, and the tolerance that would have to be chosen is exactly as arbitrary as
the model choices this board exists to pin down. A board whose argument is that
undeclared choices bias a result cannot make an undeclared choice about how much
its own output is allowed to move.

## The two costs

Random draws come from an explicit generator threaded through the code rather
than from a module level default. This is more typing at every call site that
needs randomness. It removes the failure where a test that passed becomes a test
that passes usually, which is the failure that is hardest to notice and hardest
to explain afterwards.

Linear algebra runs single threaded in any run whose output is published.
Threaded reductions sum in an order that depends on scheduling, and that is
enough to move the last digits. The cost is wall clock time on the runs that
matter most.

The single threaded requirement applies to a run that produces a published
number and to the reproducibility check that compares two such runs. It does not
apply to exploratory sweeps, which are not published and are not compared byte
for byte. A sweep that turns into a published number is re-run under the
published rule first.

## Where the seeds live

In the manifest, and nowhere else. A seed that a run consumes and the manifest
does not carry is a value that changes the output and is not described by the
description of the run, which makes the manifest wrong. The arrangement that
makes this true rather than intended is that the model takes its parameters from
the manifest and from no other source, so a seed the manifest does not hold is a
seed the model cannot read.

## The check that will refuse a violation

Named here so that the rule is not left as prose forever:

    Reproducibility

It runs a manifest twice in one job and compares the two outputs byte for byte,
failing if they differ and naming the first differing byte offset. It is red for
a run that reads a clock, for a run that draws from a global generator, and for
a run whose linear algebra was left threaded, because all three move at least
one byte.

Until that check exists this section describes an obligation and not a
mechanism. Nothing in the tree today refuses a run that violates the rule above,
and a run that violated it would leave the same trace as one that did not.
