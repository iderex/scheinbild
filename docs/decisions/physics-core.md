# The physics core, and what it deliberately leaves out

Decided in issue #5.

This is the decision the whole experiment rests on, and getting it wrong in the
appealing direction would waste the work.

## The delay is an input, never an output

The tempting choice is the most accurate model available: solve the time
dependent problem properly and let the photoemission delay come out of the
calculation.

That choice destroys the experiment. The experiment requires a known true delay
to be put in, so that what the analysis returns can be compared against it. A
delay that emerges from a calculation is not known, it is calculated, and
comparing one calculation against another answers a different question than the
one being asked. There would be no true value in the comparison, only two
estimates, and no way to say which one the disagreement belongs to.

So the delay of each emission channel is a parameter of the run. It is read from
the manifest, it is written into the output provenance, and nothing in the core
computes it.

## The approximations

The core is deliberately the simplest model that can carry an injected delay:

The strong field approximation.

A single active electron.

The dipole approximation.

The classical momentum shift of the outgoing electron by the vector potential of
the streaking field at the moment of ionisation.

No rescattering.

Each emission channel is an independent source of electrons, at a stated kinetic
energy, with a stated relative strength and a stated delay. Channels do not
interfere and do not exchange anything. A satellite line is such a channel and
not a special case, which is fixed in
[satellite-lines.md](satellite-lines.md).

This is not an approximation the board is apologising for. The hypothesis under
test is about the analysis, not about the ionisation dynamics. A model whose only
job is to produce a trace with a known truth inside it should contain nothing that
could be mistaken for the truth it is testing, and every mechanism added to the
core is another candidate explanation for whatever the analysis returns.

## The vector potential is written down, and the field is derived from it

Decided in issue #27, and recorded here because it is a statement about what the
core computes rather than about how a module is written.

Differentiating a chosen vector potential to get the field, and integrating a
chosen field to get the potential, are not the same model. A field written down
directly does not in general integrate to a potential that returns to zero after
the pulse has passed, and a residual potential at late times says the pulse left
a constant momentum behind it. In a delay scan that appears as a drift along the
delay axis, which is the axis the extracted delay is read off, so it arrives
looking like a systematic effect of the measurement.

So the potential is the primitive. It is an envelope times a carrier, which goes
to zero at both ends of time by construction, and the field is its derivative in
closed form. The other direction is not reachable: no module in this package
returns a potential built by integrating a field.

The cost is that the duration a run states is the width of the envelope the
POTENTIAL carries, and the field's own envelope differs from it by the term that
comes off differentiating the envelope. That difference is of the order of one
over the carrier frequency times the duration, so it is small for a pulse of many
cycles and is not small for a pulse of one or two.

### The sign

An electron has charge minus one in atomic units. With the field written as minus
the time derivative of the potential, the electron's equation of motion
integrates from the moment of ionisation to long after the pulse to give

    final momentum = momentum at ionisation - potential at ionisation

In words: an electron born while the vector potential is positive comes out
slower along the polarisation direction, and one born while it is negative comes
out faster.

This is written twice on purpose, here and at the top of the module that applies
it, because a sign error here inverts the direction of every extracted delay and
produces a result that is internally consistent and backwards. One function
applies the sign and nothing else in the model writes it again.

## What is left out, and what leaving it out could hide

Each of these is absent from the core. What matters is not that they are absent,
which is a modelling choice, but whether the absence could move the extracted
delay in the same direction as the contamination being studied. Where it could,
the result is weaker than it looks, and that has to be written down before the
result exists rather than after.

Everything in this section is a statement about the direction of a plausible
effect, taken from what is written about these effects in the literature. None of
it is a measurement made on this board, and no run has been made to check any of
it. Where a sentence below says an effect could move the extracted delay, read
that as could, not does.

Rescattering. The electron is treated as leaving without returning to the ion.
Rescattering redistributes electrons in energy, and a redistribution that fills
in the region between the 2s line and the 2p satellites would add intensity to
exactly the window whose contamination is the subject here. It could therefore
plausibly act in the same direction as the effect being studied, which makes it
the omission this board should be least comfortable with. It is left out anyway,
because putting it in means giving the core a mechanism whose own parameters
would then need freezing, and the argument for leaving it out is that a clean
overlap of known strength is what the analysis is being tested against.

The Coulomb laser coupling correction. The outgoing electron feels the ionic
potential and the streaking field together, and the correction for that is known
to shift an extracted streaking delay by an amount that depends on the final
kinetic energy. The 2s and 2p electrons leave with different kinetic energies, so
the correction does not cancel between the two channels, and what does not cancel
is a delay difference. That is the same observable this board is about, so yes, it
could plausibly move the extracted value in the same direction as the
contamination. Leaving it out is defensible only because the delay here is
injected rather than physical: whatever the core injects is what the analysis
should return, and a correction the core never applied cannot be one the analysis
was supposed to recover. It is not defensible as a statement about neon, and no
number this board produces is a statement about neon's true delay.

The intensity dependence of the streaking phase. The relation between the
momentum shift and the vector potential is treated as exact at the stated field
strength, with no dependence of the streaking phase on intensity and no averaging
over a focal volume. A real measurement averages over an intensity distribution.
That averaging blurs the streaking amplitude across the delay axis and could bias
a fitted oscillation phase, which is what the analysis extracts the delay from.
Whether it biases it in the same direction as the satellite contamination is not
established here and is not claimed in either direction.

## The honest summary

Two of the three omissions above could plausibly push the extracted delay the
same way the contamination does. That is written here, before any result exists,
because a result that appears after this document cannot be presented as though
the omissions had been neutral. What this board can claim is what its own
analysis returns on its own trace, against the value its own core injected.
Anything beyond that is a claim about neon, and this core is not the instrument
for one.
