"""The spectrometer's finite energy resolution, and why applying it is not a convolution.

The response is applied to the expected count spectrogram and the counts are
drawn afterwards. That order is fixed in ../../docs/decisions/detection-model.md
and it is not an implementation detail: the other order makes a smoothed noise
field, which correlates neighbouring energy bins that the analysis then fits a
centre of energy across, so the reported uncertainty comes out smaller than the
measurement it is imitating has, silently.

## The trap this module exists to avoid

The width of a time of flight response depends on kinetic energy. A convolution
with one kernel runs, produces a plausible picture, and applies the wrong width
everywhere except at the one energy the kernel was built for. The whole
contamination argument of this board is about how badly two nearby lines blur
into each other, so a width wrong by a factor across the range would change the
answer without changing anything a reader can see.

So the response is built as an explicit mapping from true energy to measured
energy and applied as such. Column j of the mapping is the measured energy
distribution of electrons whose true energy is grid point j, and its width is the
width that belongs to that energy rather than to the grid as a whole.

`single_kernel_response` is the implementation this argues against, written on
purpose and kept, because the comparison between the two is the evidence for why
the mapping exists. It is the same builder handed one width instead of a width
per column, which is deliberate: the two then differ in the width and in nothing
else, so the comparison measures the mistake rather than two authors.

## The derivation, written out rather than asserted

The relation between a time resolution and an energy resolution is where a
factor of two goes missing, so it is derived here rather than quoted.

An electron of kinetic energy E crossing a flight path of length L
non-relativistically has speed v with E = m v squared over two, so

    t = L / v = L * sqrt(m / (2 E))

which is t proportional to E to the power minus one half, and therefore E
proportional to t to the power minus two. Differentiating that,

    dE / E = -2 * dt / t

so a relative uncertainty r in the arrival time gives a relative uncertainty of
2 r in the energy, and

    sigma_E(E) = 2 * r * E

The factor of two is the exponent in E proportional to t to the minus two and
nothing else. The flight length and the electron mass cancel, which is why the
parameter is a relative time resolution and there is no length in this module.

`r` is a standard deviation and so is `sigma_E`. A time resolution quoted as a
full width at half maximum is a different number by a factor of about 2.35, and
a run that mixed the two would blur by that factor without saying so, so the
parameter name carries which one it is.

## What normalising the mapping costs

Each column is sampled at the measured grid points and normalised to sum to one.
That is what conserves counts: every expected count at a true energy is spread
over measured bins whose weights sum to one, so the total is unchanged to the
accuracy of the summation rather than to within a tolerance somebody chose.

It has a cost at the ends of the energy axis, and it is stated here rather than
left in the arithmetic. A column near the end of the grid loses part of its
Gaussian off it, and normalising what is left puts that weight back onto the bins
that remain, which is a reflection nothing physical does. So the applied width at
the outermost columns is narrower than the derivation gives, and counts that
should have left the window stay inside it.

That is not refused here, and the reason is that it cannot be. The first and last
columns of any grid sit on its boundary, so a rule about weight lost off the end
refuses every grid there is. What it means in practice is that the energy window
has to be wide enough that the lines' wings are inside it, which is a property of
the grid a spectrogram was assembled on rather than of this stage, and it belongs
to whoever chooses that grid.

What is refused here is a grid too coarse to carry the response at all.
"""

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest
from scheinbild_model.spectrogram import Spectrogram

# Which of the two forms in the decision record this run uses. There is no
# default: the two blur differently and a run that did not say which it used
# cannot be read afterwards.
RESPONSE_FORM = "spectrometer_response_form"

# The standard deviation of the measured arrival time as a fraction of the
# arrival time itself. The energy width follows from it by the derivation above
# and is not a second parameter that could disagree with the first.
RELATIVE_TIME_RESOLUTION = "spectrometer_relative_time_resolution"

# The one width of the constant width form, in electronvolts, as a standard
# deviation.
ENERGY_WIDTH = "spectrometer_energy_width_electronvolt"

# The default of the decision record. The energy width grows with kinetic
# energy, which is what a time of flight spectrometer does.
TIME_OF_FLIGHT = "time_of_flight"

# One width everywhere. The assumption most published analyses are written
# against, kept so a run under it says what changes when only that moved.
CONSTANT_WIDTH = "constant_width"

FORMS = (TIME_OF_FLIGHT, CONSTANT_WIDTH)

# The exponent in E proportional to t to the minus two, which is what turns a
# relative time resolution into a relative energy resolution. Derived in this
# module's own docstring, so it is a coefficient of the algebra rather than a
# measured quantity and it is not a row of the constant table.
TIME_TO_ENERGY_EXPONENT = 2.0

# The fewest grid points that may fall inside one standard deviation of the
# narrowest column. A modelling threshold rather than a physical value, and it
# is measured rather than chosen. A Gaussian sampled more coarsely than about
# one point per standard deviation is not that Gaussian on the grid it is
# applied to: the column that gets applied is narrower than the one the
# derivation gives, so the run blurs by less than it says it does and nothing in
# the output shows it. Sampling a unit Gaussian and comparing the column's own
# width against the width it was built from gives a relative difference of
# 7.3e-02 at half a point per standard deviation, 1.1e-07 at one, and nothing
# above the last place of a float at one and a half or more. Two is that cliff
# with a factor of two of room, and the command that produced those numbers is
# in the pull request that landed this module.
MINIMUM_POINTS_PER_WIDTH = 2.0


class ResponseRefused(ValueError):
    """A response was asked for against parameters or a grid that cannot carry one."""


def _positive(manifest: Manifest, name: str) -> float:
    """One parameter, as a positive finite float, refusing what a width may not be."""
    value = manifest.parameter(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResponseRefused(
            f"The parameter {name!r} is {value!r}, which is not a number. A "
            "resolution is a width and a width is a number."
        )
    number = float(value)
    if not number > 0.0:
        raise ResponseRefused(
            f"The parameter {name!r} is {number}. A resolution of zero or less "
            "is not a sharper instrument, it is a response with no width for a "
            "count to be spread over. A run that wants no blurring at all does "
            "not apply a response."
        )
    return number


def form_of(manifest: Manifest) -> str:
    """Which response form this run uses, or a refusal naming both."""
    value = manifest.parameter(RESPONSE_FORM)
    if not isinstance(value, str) or value not in FORMS:
        raise ResponseRefused(
            f"The response form is {value!r} and it is one of {list(FORMS)}. "
            f"There is no default, because {TIME_OF_FLIGHT!r} blurs more at high "
            f"kinetic energy and {CONSTANT_WIDTH!r} blurs the same everywhere, "
            "so the two leave different overlap between neighbouring lines. That "
            "overlap is what this board measures, and a run that did not say "
            "which form produced it cannot be read. See "
            "docs/decisions/detection-model.md."
        )
    return value


def widths_electronvolt(
    manifest: Manifest, energy_axis_electronvolt: NDArray[np.float64]
) -> NDArray[np.float64]:
    """The response standard deviation at each energy on the axis.

    Public because it is what the derivation predicts, and a test comparing the
    applied width against the predicted one has to take the prediction from
    where the model takes it rather than from a second copy of the formula.
    """
    if form_of(manifest) == TIME_OF_FLIGHT:
        relative = _positive(manifest, RELATIVE_TIME_RESOLUTION)
        widths: NDArray[np.float64] = (
            TIME_TO_ENERGY_EXPONENT * relative * energy_axis_electronvolt
        )
        return widths
    return np.full(
        energy_axis_electronvolt.shape,
        _positive(manifest, ENERGY_WIDTH),
        dtype=np.float64,
    )


def _refuse_a_grid_too_coarse_for_the_response(
    energy_axis_electronvolt: NDArray[np.float64], widths: NDArray[np.float64]
) -> None:
    """Refuse an energy grid that cannot carry the narrowest column on it.

    The narrowest column is the one to judge, because a grid fine enough for it
    is fine enough for every wider one, and under the time of flight form the
    narrowest sits at the low energy end of the axis.
    """
    spacing = float(np.min(np.diff(energy_axis_electronvolt)))
    narrowest = float(np.min(widths))
    points = narrowest / spacing
    if points < MINIMUM_POINTS_PER_WIDTH:
        raise ResponseRefused(
            f"The energy grid has a spacing of {spacing} eV and the narrowest "
            f"response on it is {narrowest} eV wide, which is {points} grid "
            "points per width. It has to be at least "
            f"{MINIMUM_POINTS_PER_WIDTH}. A Gaussian sampled more coarsely than "
            "that is not that Gaussian on this grid: the column that gets "
            "applied is narrower than the one the derivation gives, so the run "
            "blurs by less than it says it does and nothing in the output shows "
            f"it. A spacing of {narrowest / MINIMUM_POINTS_PER_WIDTH} eV or "
            "finer carries this response, and so does a wider resolution."
        )


def _columns(
    energy_axis_electronvolt: NDArray[np.float64], widths: NDArray[np.float64]
) -> NDArray[np.float64]:
    """One normalised Gaussian column per true energy, at the width given for it.

    The only place a kernel is built. Handing it one width per column is the
    mapping; handing it the same width in every column is a convolution, and
    that is the whole difference between the two functions below.
    """
    measured = energy_axis_electronvolt[:, np.newaxis]
    true = energy_axis_electronvolt[np.newaxis, :]
    offset = (measured - true) / widths[np.newaxis, :]
    columns: NDArray[np.float64] = np.exp(-offset * offset / 2.0)
    columns /= columns.sum(axis=0, keepdims=True)
    return columns


def response_matrix(
    manifest: Manifest, energy_axis_electronvolt: NDArray[np.float64]
) -> NDArray[np.float64]:
    """The mapping from true energy to measured energy, one column per true energy."""
    widths = widths_electronvolt(manifest, energy_axis_electronvolt)
    _refuse_a_grid_too_coarse_for_the_response(energy_axis_electronvolt, widths)
    return _columns(energy_axis_electronvolt, widths)


def _blurred(spectrogram: Spectrogram, matrix: NDArray[np.float64]) -> Spectrogram:
    return Spectrogram.of(
        counts=matrix @ spectrogram.counts,
        energy_axis_electronvolt=spectrogram.energy_axis_electronvolt,
        delay_axis_attosecond=spectrogram.delay_axis_attosecond,
        manifest=spectrogram.manifest,
    )


def apply_response(spectrogram: Spectrogram) -> Spectrogram:
    """The same spectrogram, blurred by the instrument this run describes.

    Still expected counts, so still a `Spectrogram`. The manifest comes off the
    spectrogram rather than being passed beside it, so a run cannot be blurred
    under a description other than the one that produced it.
    """
    matrix = response_matrix(spectrogram.manifest, spectrogram.energy_axis_electronvolt)
    return _blurred(spectrogram, matrix)


def single_kernel_response(
    spectrogram: Spectrogram, at_electronvolt: float
) -> Spectrogram:
    """The implementation this module argues against, kept so it can be compared.

    One kernel, built from the width at one energy and applied everywhere, which
    is what a convolution computes. Written as the same builder handed one width
    rather than through a transform, so the comparison does not also depend on
    the transform.

    Not part of the model. Nothing else in this package calls it. It lives here
    rather than in the suite because a wrong implementation kept beside its own
    test is a wrong implementation somebody edits until the test passes.
    """
    energy = spectrogram.energy_axis_electronvolt
    widths = widths_electronvolt(spectrogram.manifest, energy)
    one_width = float(widths[spectrogram.energy_index(at_electronvolt)])
    everywhere = np.full(energy.shape, one_width, dtype=np.float64)
    _refuse_a_grid_too_coarse_for_the_response(energy, everywhere)
    return _blurred(spectrogram, _columns(energy, everywhere))
