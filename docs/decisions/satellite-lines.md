# How satellite lines enter the model

Decided in issue #6.

The contamination this board exists to study is shake up emission accompanying
2p ionisation. It lands in kinetic energy below the 2s main line, close enough
that the streaking field moves it into the window the 2s line gets fitted in.

The single number that most decides the outcome is how strong that satellite
emission is relative to the 2s main line. If that number is a constant compiled
into the model core, then a reader who disagrees with it cannot test the
disagreement without editing the source, and the board's central claim rests on
a value nobody can see.

## A satellite is an ordinary emission line

A satellite is not a special case in the code. It is an emission line like any
other, and it enters the model through the same input path as the 2s and 2p main
lines.

An emission line has three parameters and no others:

Binding energy.

Relative intensity, referred to the same normalisation as the main lines.

Intrinsic delay, its own emission time relative to the ionising pulse.

The model does not know which of its lines are satellites, because nothing in
the description tells it. That is the point rather than an omission. A model
that could tell would be a model that could be made to treat them differently by
a change nobody reviewed.

## The default set is data, not code

The default satellite set lives in a data file in the repository, one row per
line, with a source recorded for every number. It is loaded like any other input
and it is not compiled into any module.

Every number in that file is a run parameter. A reader who holds a different
value for a shake up intensity changes the row, re-runs, and sees what the
result does. That is the only form in which a disagreement about this number is
testable.

Whether the values themselves ship in the repository or only their references do
is entry 6 in issue #1 and is not settled here. Either shape fits the
arrangement above, because what this decision fixes is that the set is data with
a source per number, not where the bytes of the number come from.

## The null case this shape makes expressible

Giving each satellite its own intrinsic delay is what makes the null case
expressible: a run in which every satellite carries exactly the 2p intrinsic
delay.

That run has no delay difference anywhere in the satellite set, so any bias in
the delay the standard analysis extracts from it comes from the spectral overlap
alone and from nothing else. Without a per line delay there is no way to
construct it, and the overlap effect could not be separated from an assumption
about satellite timing.

## The second consequence

Treating satellites as ordinary lines means the same machinery covers 2s shake
up satellites if they ever matter, and any other line somebody wants to add,
without a second code path that would need its own tests and would be the place
the two paths drift apart.
