# The boundary between the forward model and the standard analysis

Decided in issue #9.

The result of this board is what a standard analysis returns when it is given a
contaminated spectrogram. That is only the result if the analysis is genuinely
blind in the way the real analysis is blind. An analysis that can reach into the
generator, even accidentally, even through a shared helper three imports away, is
not the analysis the field runs, and any number it produces is about this
repository rather than about the field.

## The boundary

The analysis is a separate importable unit. It is `scheinbild_analysis`, the model
is `scheinbild_model`, and they are two packages rather than two directories
inside one, which is already the layout `pyproject.toml` declares and the reason
it declares it that way.

The analysis may not import the model. It may not import the satellite table, the
constant table, the manifest type, or any module that imports one of those. The
transitive case is the one that matters: a helper that looks neutral and imports
the manifest type carries the whole generator behind it.

## What the analysis is allowed to see

Its input is a spectrogram and its axes, and nothing else:

The intensity array.

The kinetic energy axis.

The delay axis.

It is not given the injected delay. It is not given the satellite energies or
intensities. It is not given the count budget, the response width, the field
strength, or the number of channels that went in. It is not given the manifest,
even though a spectrogram carries a reference to one, so the analysis reads the
three things above out of the object and does not follow that reference.

## What that costs on purpose

The analysis has to find the lines in the spectrogram itself, choose its own
energy windows, and cope with an overlap nobody told it about. It has to decide
what is one line and what is two.

That is the whole experiment. Every convenience that would remove one of those
steps removes the experiment with it, and each would arrive looking like a
reasonable simplification: passing the known line positions to save a peak
search, sharing a window helper with the generator, letting the analysis read the
manifest for the energy grid it already has on the axis.

## Where the comparison is allowed to happen

The comparison between what was injected and what was extracted needs to see
both, so it happens in a third place that is neither package.

That place is a third importable unit, `scheinbild_experiment`, which does not
exist yet. It is created by milestone 8, where the extracted delay is first
reported against the injected one, and it is the only unit permitted to import
both the model and the analysis. When it is created, it is added to the wheel
package list in `pyproject.toml` beside the other two, because a third unit that
is not packaged is a third unit an operator cannot run.

Naming it here rather than at milestone 8 is the point of writing this down. The
comparison has to live somewhere, and the somewhere it will otherwise live is
inside the analysis, where the injected value is one import away from the code
that is supposed to be blind to it.

## The check that refuses a forbidden import

This is written as a boundary rather than as an instruction because a machine can
refuse it. A check reading the analysis package's imports either finds a forbidden
edge or does not, and there is no judgement in between.

The check is one of the greppable invariants in issue #19, which names this rule
already: an import from the model inside the analysis package is refused, and the
failure message names the rule rather than the pattern. It lands there as a text
rule over the source, and issue #19 says plainly that a text rule can be replaced
later by an import graph check if it proves too coarse.

A text rule and an import graph check differ in exactly the case this document
worries about most. Text catches a direct import. It does not catch a neutral
looking third module that imports the manifest type and is then imported by the
analysis, because no forbidden name appears in the analysis file at all. So the
text rule is the floor and not the property, and the property is not enforced
until the graph check exists.

Until issue #19 lands, nothing refuses any of this and the boundary is held by
whoever is reading the diff.
