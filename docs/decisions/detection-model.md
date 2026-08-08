# The detection model: energy resolution and counting statistics

Decided in issue #7.

The instrument this board models has excellent time resolution and limited energy
resolution. Limited how, and in what shape, is a modelling choice the result
depends on, so it is decided in the open rather than absorbed into whatever was
convenient to implement.

## Two response forms, selected by parameter

The model carries both of these and neither is hard coded:

A time of flight response. The width in energy follows from a stated relative
time resolution, so the energy width grows with kinetic energy rather than
staying flat. The relative time resolution is the parameter; the energy width at
a given kinetic energy is derived from it and is not a second parameter that
could disagree with the first.

A constant width Gaussian in energy. One width, applied everywhere.

## The default is the time of flight form, and why

A time of flight spectrometer measures arrival time with roughly constant
relative precision, and kinetic energy is not linear in arrival time. Its energy
resolution therefore degrades as kinetic energy rises. A constant width Gaussian
is the easier assumption and it is the one that most likely understates the
blurring at the energies where these lines sit.

That direction is the reason for the default. Understated blurring means less
overlap between the 2s main line and the satellites below the 2p line, and less
overlap weakens the contamination this board exists to study. Choosing the
easier assumption would therefore bias the board towards its own conclusion being
smaller, which is the one direction of error nobody would question. The default is
the form that does not do the board that favour.

The constant width Gaussian stays available because it is the assumption most
published analyses are written against, and a run under it is how this board can
say what changes when that assumption is the only thing that moved.

## Counting statistics

A spectrogram with no noise gives a bias with no error bar, and a bias with no
error bar cannot be compared against a published value that carries one. A
comparison of a bare number against a number plus minus an uncertainty is not a
comparison.

So counts are drawn. The model draws Poisson counts against a stated total count
budget for the whole scan. The budget is one parameter of the run, applying to
the scan as a whole rather than per delay step, so that the statistical quality
of the simulated measurement is a stated property of the run rather than an
accident of grid size.

The uncertainty on the extracted delay is then measured by repeating the run
under different seeds, not propagated by hand through the analysis. Every seed the
run consumes is in the manifest, which is the rule in
[determinism-and-seeding.md](determinism-and-seeding.md), so a repeat under a new
seed is a new manifest and not an unrecorded rerun.

The intensity value in a spectrogram is expected counts, which is fixed in
[spectrogram-type.md](spectrogram-type.md). This document depends on that: a
normalised array has already discarded the number the Poisson draw needs.

## The order of the two operations

The response is applied to the expected count spectrogram. The counts are drawn
afterwards.

That order is part of this decision rather than an implementation detail, because
the other order produces something that looks reasonable and is wrong. Drawing
first and blurring afterwards makes a smoothed noise field, which no detector
produces. Worse than being unphysical, it correlates the noise between
neighbouring energy bins, and the analysis fits a centre of energy across those
bins. Correlated neighbours make that centre steadier than the counts justify, so
the analysis would report a smaller uncertainty than the measurement it is
imitating has, and it would do it silently.

The forward order has the property the analysis needs: each energy bin's count is
an independent draw about its own expected value, and the expected value is what
the instrument would actually have blurred.

## What this does not settle

The numbers. What relative time resolution, what Gaussian width, and what count
budget a published run uses are values, and values are frozen under
[pre-registration.md](pre-registration.md) before the analysis is run over the
output. This document fixes the forms, the default, the parameters and the order,
and it is satisfied whatever those values turn out to be.
