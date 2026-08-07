# Pre-registration

Decided in issue #10.

The failure mode this board is built against is precise. A model with many free
choices, tuned until it produces the expected factor of two, has proved only
that it can be tuned. The defence is fixing the choices before the analysis is
run over the output, and a defence that lives only in an intention is not a
defence.

What follows is a mechanism, not an intention, and the part of the problem it
does not reach is stated below rather than left to look covered.

## The frozen file

The model choices that could carry the effect are written into one file in the
repository. It holds parameter values and nothing else: no code, no derived
quantity, nothing whose value depends on when it is read.

## The hash

The content of that file is hashed. The hash is over the parsed content rather
than over the bytes, so that it does not move for a reformatting reason, in the
same way and for the same reason as the manifest hash it will be compared
against.

## The freeze record

A freeze record is a committed file carrying:

The hash of the frozen file.

The date it was frozen.

The reasoning for each frozen value, written at the moment of freezing.

The reasoning is the load bearing part and it is a record rather than a
mechanism. Nothing can check whether a value came from physics or from a
preferred outcome, so what stands in that place is a written argument a reader
can disagree with.

## The check

The analysis pipeline writes the manifest hash of the spectrogram it consumed
into its own output. A check refuses a published result whose manifest hash does
not appear in a freeze record.

## What this catches

A parameter changed after the analysis has been seen. The changed file hashes
differently, the new hash is not in any freeze record, and the result produced
under it is refused.

## What this does not catch

A parameter set that was tuned before the freeze.

No mechanism in a repository could catch it. Nothing in a tree distinguishes a
value chosen from physics from a value chosen because it produces a preferred
outcome, and no reading of the tree ever will. The hash proves that the values
did not move after the freeze. It says nothing at all about how they got there.

That half is carried by the reasoning written next to each frozen value, which
is a record and not a mechanism, and by whoever reads it. This sentence exists
so that the hash check is not read as covering more than it does.

## Amendment

Amendment has to be possible, and it has to be expensive.

A frozen value that turns out to be wrong is amended by adding a new freeze
record. The old record is never edited and never deleted. The amendment carries
what was wrong and how it was found.

A result produced under a superseded freeze stays published under the freeze it
was produced under. It is not retroactively reattributed to the newer one, and
it is not withdrawn because a later freeze disagrees with it. The record of what
was believed at the time it was produced is the thing being protected, and
editing it would remove exactly what the mechanism is for.
