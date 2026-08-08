"""The counting statistics, and the fact that they are the last thing to happen.

A spectrogram with no noise gives a bias with no error bar, and a bias with no
error bar cannot be compared against a published value that carries one. So
counts are drawn, Poisson, against a stated budget for the whole scan. The
decision is in ../../docs/decisions/detection-model.md and this module is where
its order becomes true in code rather than remaining a sentence.

## Two operations, in this order, and no way to write them the other way round

The expected counts are scaled to the budget first, and the draw comes second.
`draw` does both, so the budget cannot be skipped by calling the draw on its
own, and `expected_counts` is public only because a test that asks whether many
draws converge needs the thing they are converging to.

Nothing runs after the draw. Anything applied to drawn counts, a smoothing most
of all, correlates neighbouring energy bins in a way no detector does, and the
analysis fits a centre of energy across exactly those bins. The centre then
looks steadier than the counts justify and the reported uncertainty is smaller
than the measurement it is imitating has, silently.

Three things stand against that here, and their limits are worth as much as
their reach:

The draw returns a `DrawnCounts` and not a `Spectrogram`. A function written
against the expected count spectrogram cannot be handed drawn counts without the
type checker saying so, which is the check named `Type check` in CONTRIBUTING.md.

The counts a `DrawnCounts` holds are whole numbers. Every operation this
document is worried about leaves fractional values behind, so a test asking
whether the output is integral asks whether anything continuous touched it
afterwards.

The arrays are read only, so an in-place modification raises rather than
succeeding quietly.

What none of them catches is a caller who reads the counts out, builds a new
array from them and blurs that. Refusing it would need a pipeline to refuse it
in, and the stage before this one is not written yet.

## The budget, and the two ways of dividing it

The budget is a property of the whole scan, because that is the quantity an
experimenter has, and dividing it across the delay steps is then a stated choice
rather than an unstated one.

`even` gives every delay step the same expected total. `as_modelled` scales the
whole scan by one factor, so the relative brightness the model produced between
one delay step and another survives. Neither is a default: a manifest naming
neither is refused, because the two give different pictures and a run that did
not say which it used cannot be read.

## The seed, and why it is not read through the manifest's own accessor

`manifest.seeds[...]` here, rather than `manifest.seed(...)`, which is the method
written for it. The `no-global-random-state` rule in `tools/invariants.py`
refuses any call whose name ends in `.seed`, and the manifest's accessor is such
a call, so the sanctioned way to read a seed is refused inside `src`. The
refusal is real and it is reproduced in issue #64. The subscript is the way past
it that does not weaken the rule, and the check that would have named a missing
seed is written out below instead of being inherited.
"""

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.manifest import Manifest
from scheinbild_model.spectrogram import Spectrogram

# The total number of counts the whole scan is worth, across every delay step
# and every energy bin.
COUNT_BUDGET = "count_budget_for_the_scan"

# How that budget is spread over the delay steps.
COUNT_BUDGET_DIVISION = "count_budget_division"

# The seed the draw consumes. In the manifest, like every other seed, so that a
# repeat under a new seed is a new manifest rather than an unrecorded rerun.
COUNTING_STATISTICS_SEED = "counting_statistics"

# Every delay step receives the same expected total, whatever the model made of
# it. This is the scan whose acquisition at each step ran until a fixed number
# of counts had arrived.
EVEN = "even"

# One factor over the whole scan. The relative weight of one delay step against
# another is whatever the model produced, which is the scan whose acquisition
# spent the same time at every step.
AS_MODELLED = "as_modelled"

DIVISIONS = (EVEN, AS_MODELLED)


class CountsRefused(ValueError):
    """A draw was asked for against a budget or a seed that could not describe one."""


def _budget(manifest: Manifest) -> int:
    """The count budget for the scan, refusing what a budget may not be.

    A whole number, and a float is refused rather than rounded. Counts are
    counted, so a budget that arrived as a float arrived through arithmetic
    somebody did on the way in, and rounding it here would hide which direction
    that arithmetic went.
    """
    value = manifest.parameter(COUNT_BUDGET)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CountsRefused(
            f"The parameter {COUNT_BUDGET!r} is {value!r}. A count budget is a "
            "whole number of counts. A float here is a number that reached the "
            "manifest through arithmetic, and rounding it in this module would "
            "settle which way that arithmetic went without saying so."
        )
    if value <= 0:
        raise CountsRefused(
            f"The count budget for the scan is {value}. A scan that collects no "
            "counts produces a spectrogram of zeros, which the analysis reads as "
            "a measurement with no signal rather than as a run that was never "
            "worth making."
        )
    return value


def _division(manifest: Manifest) -> str:
    """How the budget is spread across the delay steps, or a refusal naming both ways."""
    value = manifest.parameter(COUNT_BUDGET_DIVISION)
    if not isinstance(value, str):
        raise CountsRefused(
            f"The parameter {COUNT_BUDGET_DIVISION!r} is {value!r}, which is not "
            f"a name. It is one of {list(DIVISIONS)}."
        )
    if value not in DIVISIONS:
        raise CountsRefused(
            f"The count budget division is {value!r} and it is one of "
            f"{list(DIVISIONS)}. There is no default, because the two produce "
            f"different pictures: {EVEN!r} gives every delay step the same "
            f"expected total, and {AS_MODELLED!r} keeps the relative brightness "
            "the model produced between one step and the next. A run that did "
            "not say which it used cannot be read afterwards."
        )
    return value


def _seed_value(manifest: Manifest) -> int:
    """The seed for the draw, out of the manifest and out of nowhere else.

    Read by subscript rather than through the manifest's own accessor, for the
    reason at the top of this module, so the refusal that accessor would have
    raised is written here.
    """
    if COUNTING_STATISTICS_SEED not in manifest.seeds:
        raise CountsRefused(
            f"The manifest carries no seed named {COUNTING_STATISTICS_SEED!r}. A "
            "seed taken from anywhere else makes two runs of one manifest "
            "differ, which is what docs/decisions/determinism-and-seeding.md "
            f"refuses. The manifest carries: {sorted(manifest.seeds)}."
        )
    return manifest.seeds[COUNTING_STATISTICS_SEED]


class DrawnCounts:
    """Whole counts over a kinetic energy axis and a pulse delay axis.

    The output of the model and not an intermediate of it. Deliberately not a
    `Spectrogram`: a spectrogram holds expected counts, these are a realisation
    of them, and a function written for the first should not silently accept the
    second.

    Read only in both arrays, frozen here rather than by the caller, so that
    every instance has the property whatever route made it.
    """

    __slots__ = (
        "counts",
        "delay_axis_attosecond",
        "energy_axis_electronvolt",
        "manifest",
    )

    def __init__(
        self,
        counts: NDArray[np.int64],
        energy_axis_electronvolt: NDArray[np.float64],
        delay_axis_attosecond: NDArray[np.float64],
        manifest: Manifest,
    ) -> None:
        self.counts = counts.copy()
        self.energy_axis_electronvolt = energy_axis_electronvolt.copy()
        self.delay_axis_attosecond = delay_axis_attosecond.copy()
        self.manifest = manifest
        # Copied first, so freezing an argument's flags is not done to an array
        # the caller still holds, and so a later write through the original
        # cannot reach what this object returns.
        self.counts.setflags(write=False)
        self.energy_axis_electronvolt.setflags(write=False)
        self.delay_axis_attosecond.setflags(write=False)

    def total_counts(self) -> int:
        """Every count in the scan, summed."""
        return int(self.counts.sum())


def expected_counts(spectrogram: Spectrogram) -> Spectrogram:
    """The same spectrogram, scaled so the scan is worth its budget.

    Still expected counts, so still a `Spectrogram`. The manifest comes off the
    spectrogram rather than being passed beside it, which is what stops a run
    from being drawn under a description other than the one that produced it.
    """
    manifest = spectrogram.manifest
    budget = _budget(manifest)
    division = _division(manifest)
    counts = spectrogram.counts

    scaled: NDArray[np.float64]
    if division == AS_MODELLED:
        total = float(counts.sum())
        if total <= 0.0:
            raise CountsRefused(
                "The spectrogram holds no expected counts at all, so there is "
                f"nothing for the {AS_MODELLED!r} division to scale: it "
                "multiplies by one factor and every factor times zero is zero. "
                "The run before this one produced an empty model rather than a "
                "faint one."
            )
        scaled = counts * (budget / total)
    else:
        per_step = budget / counts.shape[1]
        column_totals = counts.sum(axis=0)
        empty = np.flatnonzero(column_totals <= 0.0)
        if empty.size > 0:
            first = int(empty[0])
            raise CountsRefused(
                f"Delay step {first}, at "
                f"{spectrogram.delay_axis_attosecond[first]} as, holds no "
                f"expected counts, and the {EVEN!r} division gives every step "
                "the same expected total by scaling each one to it. A step with "
                "nothing in it has no factor that reaches that total, and "
                "filling it with zeros would hand the analysis a delay step the "
                f"model never produced. Either the model is wrong there or "
                f"{AS_MODELLED!r} is the division this run wants."
            )
        scaled = counts * (per_step / column_totals)

    return Spectrogram.of(
        counts=scaled,
        energy_axis_electronvolt=spectrogram.energy_axis_electronvolt,
        delay_axis_attosecond=spectrogram.delay_axis_attosecond,
        manifest=manifest,
    )


def draw(spectrogram: Spectrogram) -> DrawnCounts:
    """Draw the counts this run measures. The last operation of the model.

    The budget is applied here rather than by the caller, so a draw that ignored
    it is not a call anybody can write.

    The generator is built from the manifest's seed and from nothing else, and
    it is local to this call. Two runs of one manifest therefore produce the
    same counts, which is the rule in
    ../../docs/decisions/determinism-and-seeding.md. The stream belongs to the
    numpy version pinned in pyproject.toml; a different version is a different
    code version and a manifest carries that too.
    """
    expected = expected_counts(spectrogram)
    generator = np.random.default_rng(_seed_value(spectrogram.manifest))
    drawn: NDArray[np.int64] = generator.poisson(expected.counts)
    return DrawnCounts(
        drawn,
        expected.energy_axis_electronvolt,
        expected.delay_axis_attosecond,
        expected.manifest,
    )
