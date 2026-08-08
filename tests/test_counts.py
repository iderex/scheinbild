"""What the draw refuses, what it spends, and what it leaves unmodifiable.

Every refusal below is paired with the neighbouring input that is accepted,
usually one value away, so that a passing refusal test says the module refused
for the reason it names rather than that it can raise at all.

Two of these are statistical and their tolerances are derived rather than
chosen. The derivation is written beside each one, with the size of the mistake
it is able to see, because a tolerance picked until the test went green would
make the test a description of this implementation instead of a check on it.

The grid is three energy bins by four delay steps. The two dimensions differ, so
a transposed result is a length mismatch rather than a shape that happens to fit.
"""

import unittest

import numpy as np

from scheinbild_model.counts import (
    AS_MODELLED,
    COUNT_BUDGET,
    COUNT_BUDGET_DIVISION,
    COUNTING_STATISTICS_SEED,
    DIVISIONS,
    EVEN,
    CountsRefused,
    DrawnCounts,
    draw,
    expected_counts,
)
from scheinbild_model.manifest import Manifest, ParameterNotInManifest
from scheinbild_model.spectrogram import Spectrogram

ENERGIES = 3
DELAYS = 4
BUDGET = 12000
SEED = 20260808

# The budget over the number of bins a uniform model spreads it across. Both
# divisions give this, because a uniform model has nothing for them to disagree
# about, which is what makes it the right shape for the statistical cases.
PER_BIN = BUDGET / (ENERGIES * DELAYS)


def a_manifest(overrides=None, seeds=None):
    parameters = {COUNT_BUDGET: BUDGET, COUNT_BUDGET_DIVISION: EVEN}
    parameters.update(overrides or {})
    return Manifest.of(
        parameters=parameters,
        seeds={COUNTING_STATISTICS_SEED: SEED} if seeds is None else seeds,
        code_version="0.0.0",
    )


def a_spectrogram(model=None, manifest=None):
    return Spectrogram.of(
        counts=np.ones((ENERGIES, DELAYS)) if model is None else model,
        energy_axis_electronvolt=np.linspace(90.0, 110.0, ENERGIES),
        delay_axis_attosecond=np.linspace(-200.0, 200.0, DELAYS),
        manifest=a_manifest() if manifest is None else manifest,
    )


class TheValidCaseIsValid(unittest.TestCase):
    """Everything below is a departure from this, so this one comes first."""

    def test_a_draw_returns_counts_on_the_same_grid(self):
        drawn = draw(a_spectrogram())
        self.assertEqual(drawn.counts.shape, (ENERGIES, DELAYS))
        self.assertEqual(drawn.energy_axis_electronvolt.size, ENERGIES)
        self.assertEqual(drawn.delay_axis_attosecond.size, DELAYS)

    def test_the_axes_and_the_manifest_travel_with_the_counts(self):
        spectrogram = a_spectrogram()
        drawn = draw(spectrogram)
        self.assertEqual(drawn.manifest, spectrogram.manifest)
        np.testing.assert_array_equal(
            drawn.energy_axis_electronvolt, spectrogram.energy_axis_electronvolt
        )
        np.testing.assert_array_equal(
            drawn.delay_axis_attosecond, spectrogram.delay_axis_attosecond
        )

    def test_the_draw_is_not_a_spectrogram(self):
        # The wall the order rests on. A function written against expected
        # counts cannot be handed a realisation of them without the type
        # checker saying so, and this is that statement at runtime.
        drawn = draw(a_spectrogram())
        self.assertIsInstance(drawn, DrawnCounts)
        self.assertNotIsInstance(drawn, Spectrogram)


class TheBudgetIsSpentAcrossTheWholeScan(unittest.TestCase):
    def test_an_even_division_spends_the_budget(self):
        expected = expected_counts(a_spectrogram())
        self.assertAlmostEqual(expected.total_counts(), BUDGET)

    def test_an_even_division_gives_every_delay_step_the_same_total(self):
        # The model is brighter at later delays and the division flattens that.
        model = np.ones((ENERGIES, DELAYS)) * np.arange(1.0, DELAYS + 1.0)
        expected = expected_counts(
            a_spectrogram(
                model=model, manifest=a_manifest({COUNT_BUDGET_DIVISION: EVEN})
            )
        )
        per_step = expected.counts.sum(axis=0)
        np.testing.assert_allclose(per_step, np.full(DELAYS, BUDGET / DELAYS))

    def test_as_modelled_spends_the_budget_and_keeps_the_shape(self):
        # The same model, the same budget, the one parameter that moved. The
        # steps are in the ratio 1:2:3:4 going in and still are coming out,
        # which is the property the previous case destroys on purpose.
        model = np.ones((ENERGIES, DELAYS)) * np.arange(1.0, DELAYS + 1.0)
        expected = expected_counts(
            a_spectrogram(
                model=model, manifest=a_manifest({COUNT_BUDGET_DIVISION: AS_MODELLED})
            )
        )
        self.assertAlmostEqual(expected.total_counts(), BUDGET)
        per_step = expected.counts.sum(axis=0)
        np.testing.assert_allclose(per_step / per_step[0], np.arange(1.0, DELAYS + 1.0))

    def test_the_draw_spends_the_budget_without_being_asked_to(self):
        # The budget is applied inside the draw rather than by the caller, so a
        # draw that ignored it is not a call anybody can write. Five standard
        # deviations of the total, which for a Poisson sum is its own square
        # root, so this sees a budget that was not applied at all and nothing
        # smaller than a few per cent.
        drawn = draw(a_spectrogram())
        self.assertLess(abs(drawn.total_counts() - BUDGET), 5.0 * np.sqrt(BUDGET))


class WhatACountBudgetMayNotBe(unittest.TestCase):
    def test_a_missing_budget_comes_out_of_the_manifest(self):
        manifest = Manifest.of(
            parameters={COUNT_BUDGET_DIVISION: EVEN},
            seeds={COUNTING_STATISTICS_SEED: SEED},
            code_version="0.0.0",
        )
        with self.assertRaises(ParameterNotInManifest):
            draw(a_spectrogram(manifest=manifest))

    def test_a_float_budget_is_refused(self):
        with self.assertRaises(CountsRefused) as refusal:
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET: float(BUDGET)})))
        self.assertIn("whole number", str(refusal.exception))

    def test_the_same_budget_as_a_whole_number_is_accepted(self):
        self.assertEqual(expected_counts(a_spectrogram()).total_counts(), BUDGET)

    def test_a_budget_of_zero_is_refused(self):
        with self.assertRaises(CountsRefused) as refusal:
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET: 0})))
        self.assertIn("collects no counts", str(refusal.exception))

    def test_a_negative_budget_is_refused(self):
        with self.assertRaises(CountsRefused):
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET: -1})))

    def test_the_smallest_budget_above_zero_is_accepted(self):
        # The near miss for both of the two above.
        self.assertEqual(
            expected_counts(
                a_spectrogram(manifest=a_manifest({COUNT_BUDGET: 1}))
            ).total_counts(),
            1,
        )

    def test_a_budget_that_is_a_boolean_is_refused(self):
        # True is an integer to Python and is not a number of counts.
        with self.assertRaises(CountsRefused) as refusal:
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET: True})))
        self.assertIn("whole number", str(refusal.exception))


class WhatADivisionMayNotBe(unittest.TestCase):
    def test_a_missing_division_comes_out_of_the_manifest(self):
        manifest = Manifest.of(
            parameters={COUNT_BUDGET: BUDGET},
            seeds={COUNTING_STATISTICS_SEED: SEED},
            code_version="0.0.0",
        )
        with self.assertRaises(ParameterNotInManifest):
            draw(a_spectrogram(manifest=manifest))

    def test_an_unknown_division_is_refused_and_names_both(self):
        with self.assertRaises(CountsRefused) as refusal:
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET_DIVISION: "uniform"})))
        message = str(refusal.exception)
        self.assertIn(EVEN, message)
        self.assertIn(AS_MODELLED, message)

    def test_a_division_that_is_not_a_name_is_refused(self):
        with self.assertRaises(CountsRefused):
            draw(a_spectrogram(manifest=a_manifest({COUNT_BUDGET_DIVISION: 0})))

    def test_both_of_the_two_names_are_accepted(self):
        # The near miss for the two above, and the statement that the tuple the
        # refusal message quotes is the tuple the module acts on.
        for division in DIVISIONS:
            with self.subTest(division=division):
                expected = expected_counts(
                    a_spectrogram(
                        manifest=a_manifest({COUNT_BUDGET_DIVISION: division})
                    )
                )
                self.assertAlmostEqual(expected.total_counts(), BUDGET)


class AModelWithNothingInItIsRefusedRatherThanScaled(unittest.TestCase):
    def a_model_with_an_empty_delay_step(self, value=0.0):
        model = np.ones((ENERGIES, DELAYS))
        model[:, 2] = value
        return model

    def test_an_empty_delay_step_is_refused_under_an_even_division(self):
        with self.assertRaises(CountsRefused) as refusal:
            expected_counts(
                a_spectrogram(model=self.a_model_with_an_empty_delay_step())
            )
        message = str(refusal.exception)
        self.assertIn("Delay step 2", message)
        self.assertIn(AS_MODELLED, message)

    def test_the_same_step_with_one_count_in_it_is_accepted(self):
        # One element away from the case above, and the whole grid is otherwise
        # identical.
        model = self.a_model_with_an_empty_delay_step()
        model[0, 2] = 1.0
        expected = expected_counts(a_spectrogram(model=model))
        np.testing.assert_allclose(
            expected.counts.sum(axis=0), np.full(DELAYS, BUDGET / DELAYS)
        )

    def test_an_empty_model_is_refused_under_as_modelled(self):
        with self.assertRaises(CountsRefused) as refusal:
            expected_counts(
                a_spectrogram(
                    model=np.zeros((ENERGIES, DELAYS)),
                    manifest=a_manifest({COUNT_BUDGET_DIVISION: AS_MODELLED}),
                )
            )
        self.assertIn("no expected counts at all", str(refusal.exception))

    def test_one_count_anywhere_is_enough_for_as_modelled(self):
        model = np.zeros((ENERGIES, DELAYS))
        model[1, 1] = 1.0
        expected = expected_counts(
            a_spectrogram(
                model=model, manifest=a_manifest({COUNT_BUDGET_DIVISION: AS_MODELLED})
            )
        )
        self.assertAlmostEqual(expected.total_counts(), BUDGET)


class TheSeedComesFromTheManifestAndNowhereElse(unittest.TestCase):
    def test_a_manifest_with_no_seed_is_refused(self):
        with self.assertRaises(CountsRefused) as refusal:
            draw(a_spectrogram(manifest=a_manifest(seeds={})))
        self.assertIn(COUNTING_STATISTICS_SEED, str(refusal.exception))

    def test_a_manifest_carrying_that_seed_draws(self):
        self.assertEqual(draw(a_spectrogram()).counts.shape, (ENERGIES, DELAYS))

    def test_one_manifest_drawn_twice_gives_the_same_bytes(self):
        # Byte for byte rather than close, which is the rule in
        # docs/decisions/determinism-and-seeding.md. The dtype is compared as
        # well, because two arrays of different widths can hold the same bytes.
        first = draw(a_spectrogram())
        second = draw(a_spectrogram())
        self.assertEqual(first.counts.dtype, second.counts.dtype)
        self.assertEqual(first.counts.tobytes(), second.counts.tobytes())

    def test_a_different_seed_gives_different_counts(self):
        # The near miss for the case above: everything else in the manifest is
        # the same, so a draw ignoring the seed would pass that test and fail
        # this one.
        other = a_manifest(seeds={COUNTING_STATISTICS_SEED: SEED + 1})
        self.assertNotEqual(
            draw(a_spectrogram()).counts.tobytes(),
            draw(a_spectrogram(manifest=other)).counts.tobytes(),
        )


# How many draws the two statistical cases average over. Both tolerances below
# are derived from this number, so it is written once.
REPLICATES = 2000


def replicates():
    """One draw per seed, over the same model and the same budget."""
    return np.stack(
        [
            draw(
                a_spectrogram(
                    manifest=a_manifest(seeds={COUNTING_STATISTICS_SEED: seed})
                )
            ).counts
            for seed in range(REPLICATES)
        ]
    )


class TheDrawIsPoissonAboutTheExpectedCounts(unittest.TestCase):
    def test_the_mean_of_many_draws_converges_on_the_expected_counts(self):
        # The mean of R draws of a Poisson with expectation L has standard
        # deviation sqrt(L / R). The tolerance is five of those, which a correct
        # implementation exceeds in one bin with probability about 6e-7, and
        # which a scale error of one per cent misses by fourteen of them:
        # 0.01 * L is 10 counts against a standard error of 0.71.
        drawn = replicates()
        tolerance = 5.0 * np.sqrt(PER_BIN / REPLICATES)
        np.testing.assert_allclose(
            drawn.mean(axis=0), np.full((ENERGIES, DELAYS), PER_BIN), atol=tolerance
        )

    def test_the_variance_matches_the_mean(self):
        # The property that separates a Poisson from any other draw with the
        # same mean. The sample variance of R draws has a relative standard
        # deviation of sqrt(2 / (R - 1)), which is 3.2 per cent here, and the
        # tolerance is five of those. It is loose because that is what two
        # thousand replicates buy; it still refuses a draw whose variance is
        # twice or half its mean, which is what a normal draw with the wrong
        # width or a doubled budget would give.
        drawn = replicates()
        relative = 5.0 * np.sqrt(2.0 / (REPLICATES - 1))
        np.testing.assert_allclose(drawn.var(axis=0), drawn.mean(axis=0), rtol=relative)


class NothingModifiesTheCountsAfterTheDraw(unittest.TestCase):
    def test_every_value_is_a_whole_number(self):
        # The draw is the last operation. Every operation the order rule is
        # about, a smoothing first among them, leaves fractional values behind,
        # so this asks whether anything continuous ran afterwards.
        drawn = draw(a_spectrogram())
        self.assertTrue(np.issubdtype(drawn.counts.dtype, np.integer))
        self.assertTrue(np.all(drawn.counts >= 0))

    def test_the_counts_refuse_to_be_written_to(self):
        drawn = draw(a_spectrogram())
        with self.assertRaises(ValueError):
            drawn.counts[0, 0] = 0

    def test_the_axes_refuse_to_be_written_to(self):
        drawn = draw(a_spectrogram())
        with self.assertRaises(ValueError):
            drawn.energy_axis_electronvolt[0] = 0.0
        with self.assertRaises(ValueError):
            drawn.delay_axis_attosecond[0] = 0.0

    def test_the_spectrogram_that_went_in_is_unchanged(self):
        spectrogram = a_spectrogram()
        before = spectrogram.counts.copy()
        draw(spectrogram)
        np.testing.assert_array_equal(spectrogram.counts, before)

    def test_writing_through_the_array_the_draw_was_given_does_not_reach_it(self):
        # The copy in the constructor rather than a shared view. A caller who
        # still holds the array cannot change what the drawn counts report.
        source = np.zeros((ENERGIES, DELAYS), dtype=np.int64)
        drawn = DrawnCounts(
            source,
            np.linspace(90.0, 110.0, ENERGIES),
            np.linspace(-200.0, 200.0, DELAYS),
            a_manifest(),
        )
        source[0, 0] = 7
        self.assertEqual(drawn.total_counts(), 0)
