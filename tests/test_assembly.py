"""The assembly is a sum, the run names its lines, and a short scan is refused.

The first two properties are the ones a two line special case would quietly
break.

That the assembled spectrogram is the sum of the single line traces is asserted
as an exact array equality rather than as a closeness. It is what makes the
satellite set in milestone 5 an addition of data instead of a change to the
model, and the determinism decision rules out comparing the before and after
with a tolerance, so the property has to be exact here before anything can rely
on it there.

Where the lines sit and how strong they are against each other is the part that
comes from outside this package. The binding energies and the cross sections are
in the atomic data file with their sources, so the cases below read the file
rather than repeating the numbers, and a run whose lines moved would move away
from what the file says rather than away from a number a test author chose.

Which lines a run assembles comes out of its manifest, and the case that decides
whether that was worth doing is the two line run reproducing the two line
caller's output byte for byte rather than closely. The near miss for the list
itself is a name written twice, which sums one trace into the picture at twice
its strength and looks like a strong line rather than like a mistake.

A scan too short to separate an amplitude from a phase is refused, and the near
miss is one delay step: the scan that just covers the minimum is accepted and
the same scan one step shorter is not.
"""

import unittest

import numpy as np
from numpy.typing import NDArray

from scheinbild_model.assembly import (
    DELAY_FIRST,
    DELAY_POINTS,
    DELAY_STEP,
    ENERGY_FIRST,
    ENERGY_POINTS,
    ENERGY_STEP,
    LINE_NAMES,
    LINE_SOURCES,
    MINIMUM_CYCLES,
    NEON_MAIN_LINE_NAMES,
    AssemblyRefused,
    assemble,
    delay_axis_attosecond,
    energy_axis_electronvolt,
    entries_for,
    line_names,
    line_sources,
    lines_of,
    merge,
    named_lines_spectrogram,
    neon_main_lines_spectrogram,
    relative_strengths,
    streaking_period_attosecond,
)
from scheinbild_model.atomic_data import (
    NEON_2P_SHAKE_UP_SATELLITES,
    NEON_MAIN_LINES,
    AtomicDataRefused,
    neon_2p_shake_up_satellites,
    neon_main_lines,
    relative_cross_section,
)
from scheinbild_model.manifest import Manifest
from scheinbild_model.pulse import CENTRAL_ENERGY, CHIRP, TIME_GRID_HALF_WIDTH
from scheinbild_model.pulse import DURATION as PULSE_DURATION
from scheinbild_model.spectrogram import Spectrogram
from scheinbild_model.streaking_field import (
    CARRIER_ENVELOPE_PHASE,
    PEAK_INTENSITY,
    PHOTON_ENERGY,
    StreakingField,
)
from scheinbild_model.streaking_field import DURATION as FIELD_DURATION
from scheinbild_model.streaking_map import (
    BIRTH_TIME_POINTS,
    INTRINSIC_DELAY,
    parameter_name,
    trace,
)

# A case to compute against, not a frozen parameter set. The photon energy is
# above 80 eV because that is where the 2s column of the shipped cross section
# table starts, and the file refuses a photon energy below its first row rather
# than extrapolating one.
_PHOTON_ELECTRONVOLT = 90.0
_IONISING_DURATION_ATTOSECOND = 150.0
_IONISING_HALF_WIDTH_ATTOSECOND = 400.0
_CARRIER_ELECTRONVOLT = 1.55
_STREAKING_DURATION_ATTOSECOND = 5000.0
_STREAKING_INTENSITY = 1e12
_BIRTH_TIME_POINTS = 201

# The delay scan. Two cycles of a 1.55 eV carrier is about 5336 as, and 61 steps
# of 90 as covers 5400, so the scan clears the minimum by less than one step and
# the near miss below is one step.
_MINIMUM_CYCLES = 2.0
_DELAY_FIRST_ATTOSECOND = -2700.0
_DELAY_STEP_ATTOSECOND = 90.0
_DELAY_POINTS = 61

# The energy grid, wide enough to hold both lines with their excursions. The 2s
# line sits near 41.5 eV and the 2p line near 68.4 eV at this photon energy, and
# each swings a few electronvolts either way.
_ENERGY_FIRST_ELECTRONVOLT = 35.0
_ENERGY_STEP_ELECTRONVOLT = 0.02
_ENERGY_POINTS = 2051

# What a ratio of counts may differ from a ratio of cross sections by. Both are
# the same number arrived at by different arithmetic, so this is the summation
# over the grid and nothing else.
_RATIO_TOLERANCE = 1e-12

# What the potential may be at a quarter of a period from its crest, as a
# fraction of its peak. A cosine is zero there in exact arithmetic, so this is
# the envelope having moved a little and the cosine of a number near pi over two
# not being exactly zero, and nothing else.
_QUARTER_TOLERANCE = 1e-12

# What a window's total may leave outside it. Nothing, to the last places of the
# summation: the deposition conserves each line's whole strength and the windows
# below are built to hold the whole excursion.
_WINDOW_TOLERANCE = 1e-12


def _parameters(**overrides: object) -> dict[str, object]:
    parameters: dict[str, object] = {
        CENTRAL_ENERGY: _PHOTON_ELECTRONVOLT,
        PULSE_DURATION: _IONISING_DURATION_ATTOSECOND,
        CHIRP: 0.0,
        TIME_GRID_HALF_WIDTH: _IONISING_HALF_WIDTH_ATTOSECOND,
        PHOTON_ENERGY: _CARRIER_ELECTRONVOLT,
        FIELD_DURATION: _STREAKING_DURATION_ATTOSECOND,
        CARRIER_ENVELOPE_PHASE: 0.0,
        PEAK_INTENSITY: _STREAKING_INTENSITY,
        BIRTH_TIME_POINTS: _BIRTH_TIME_POINTS,
        DELAY_FIRST: _DELAY_FIRST_ATTOSECOND,
        DELAY_STEP: _DELAY_STEP_ATTOSECOND,
        DELAY_POINTS: _DELAY_POINTS,
        ENERGY_FIRST: _ENERGY_FIRST_ELECTRONVOLT,
        ENERGY_STEP: _ENERGY_STEP_ELECTRONVOLT,
        ENERGY_POINTS: _ENERGY_POINTS,
        MINIMUM_CYCLES: _MINIMUM_CYCLES,
        LINE_SOURCES: NEON_MAIN_LINES,
        LINE_NAMES: " ".join(NEON_MAIN_LINE_NAMES),
        parameter_name("2p", INTRINSIC_DELAY): 0.0,
        parameter_name("2s", INTRINSIC_DELAY): 21.0,
    }
    parameters.update(overrides)
    return parameters


def _manifest(**overrides: object) -> Manifest:
    # The overrides are of whatever type the case wants, because a value of the
    # wrong type is one of the things the assembler refuses. The suppression is
    # on the construction and names one code.
    return Manifest.of(
        parameters=_parameters(**overrides),  # type: ignore[arg-type]
        seeds={},
        code_version="a version for this test",
    )


def _window_total(spectrogram: Spectrogram, low: float, high: float) -> float:
    """Every count between two energies, over the whole scan."""
    return float(spectrogram.counts[spectrogram.energy_window(low, high), :].sum())


def _excursion_electronvolt(manifest: Manifest, unstreaked: float) -> float:
    """How far either way the field moves a line of this kinetic energy.

    Read off the field at the crest of the carrier and half a cycle later, which
    at a carrier envelope phase of zero are where the potential reaches its two
    extremes. The larger of the two is taken, because the shift is not symmetric
    about the unstreaked energy: the term that goes as the square of the
    potential adds on both sides.
    """
    field = StreakingField(manifest)
    half_cycle = 0.5 * streaking_period_attosecond(field)
    return max(
        abs(field.energy_shift_electronvolt(unstreaked, 0.0)),
        abs(field.energy_shift_electronvolt(unstreaked, half_cycle)),
    )


def _unstreaked_from_the_file(name: str) -> float:
    """Where a line sits with the field off, from the data file and nothing else."""
    binding = neon_main_lines()[name].binding_energy.electronvolt
    return _PHOTON_ELECTRONVOLT - binding


class TheAssemblyIsTheSumOfItsLines(unittest.TestCase):
    def test_the_two_traces_added_by_hand_are_the_assembled_spectrogram(self) -> None:
        # Exact, not close. This is the property that lets milestone 5 add rows
        # to a data file instead of changing the model, and the determinism
        # decision rules out comparing the two with a tolerance.
        manifest = _manifest()
        lines = lines_of(manifest, neon_main_lines(), NEON_MAIN_LINE_NAMES)
        energies = energy_axis_electronvolt(manifest)
        delays = delay_axis_attosecond(manifest)

        by_hand = np.zeros((energies.size, delays.size), dtype=np.float64)
        for line in lines:
            by_hand += trace(manifest, line, energies, delays).counts

        self.assertTrue(
            np.array_equal(assemble(manifest, lines).counts, by_hand),
            "The assembled spectrogram is not the sum of the single line traces.",
        )

    def test_one_line_assembles_to_its_own_trace(self) -> None:
        # Without this the case above would also pass against an assembler that
        # summed the same trace twice, or that ignored the sequence it was given
        # and always assembled both.
        manifest = _manifest()
        lines = lines_of(manifest, neon_main_lines(), ("2p",))
        alone = assemble(manifest, lines)
        by_hand = trace(
            manifest,
            lines[0],
            energy_axis_electronvolt(manifest),
            delay_axis_attosecond(manifest),
        )
        self.assertTrue(np.array_equal(alone.counts, by_hand.counts))
        self.assertLess(
            alone.total_counts(), neon_main_lines_spectrogram(manifest).total_counts()
        )

    def test_an_empty_set_of_lines_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            assemble(_manifest(), ())


class ARunCarriesTheLinesItNames(unittest.TestCase):
    """The set of lines comes out of the manifest, and the two line run is unmoved.

    The first case is the one the rest of milestone 5 rests on. The two line
    spectrogram assembled from the manifest has to be the same bytes as the one
    the two line caller produces, not the same to within a tolerance, because
    docs/decisions/determinism-and-seeding.md chose byte identical deliberately
    and a refactor compared with a tolerance is a refactor that moved the output
    by an amount nobody looked at.
    """

    def test_the_two_line_run_is_byte_for_byte_what_the_two_line_caller_makes(
        self,
    ) -> None:
        manifest = _manifest()
        named = named_lines_spectrogram(manifest)
        pair = neon_main_lines_spectrogram(manifest)
        self.assertTrue(
            np.array_equal(named.counts, pair.counts),
            "The run that names its lines does not reproduce the two line caller.",
        )
        self.assertTrue(
            np.array_equal(
                named.energy_axis_electronvolt, pair.energy_axis_electronvolt
            )
        )
        self.assertTrue(
            np.array_equal(named.delay_axis_attosecond, pair.delay_axis_attosecond)
        )
        # One manifest describes both, so the digest is the same digest rather
        # than an equal one. A run whose set of lines was not in its description
        # could not have said that.
        self.assertEqual(named.manifest.digest(), pair.manifest.digest())

    def test_the_order_the_names_are_written_in_is_the_order_they_are_summed(
        self,
    ) -> None:
        # Not decoration. The first name is the reference the strengths are
        # taken against, so the reversed run is a different picture rather than
        # the same one rearranged.
        reversed_names = " ".join(reversed(NEON_MAIN_LINE_NAMES))
        self.assertEqual(
            line_names(_manifest(**{LINE_NAMES: reversed_names})),
            tuple(reversed(NEON_MAIN_LINE_NAMES)),
        )
        self.assertFalse(
            np.array_equal(
                named_lines_spectrogram(
                    _manifest(**{LINE_NAMES: reversed_names})
                ).counts,
                named_lines_spectrogram(_manifest()).counts,
            )
        )

    def test_a_run_naming_one_line_assembles_that_line_alone(self) -> None:
        # Without this the case above would also pass against a caller that
        # ignored the manifest and assembled both lines whatever it was asked.
        manifest = _manifest(**{LINE_NAMES: "2p"})
        by_hand = assemble(manifest, lines_of(manifest, neon_main_lines(), ("2p",)))
        self.assertTrue(
            np.array_equal(named_lines_spectrogram(manifest).counts, by_hand.counts)
        )

    def test_stray_whitespace_describes_the_same_run(self) -> None:
        self.assertEqual(
            line_names(_manifest(**{LINE_NAMES: "  2p   2s  "})), ("2p", "2s")
        )

    def test_a_name_written_twice_is_refused(self) -> None:
        # The near miss that matters. A repeated name sums the same trace twice,
        # which is a line at twice its strength and looks like a strong line
        # rather than like a mistake.
        with self.assertRaises(AssemblyRefused):
            line_names(_manifest(**{LINE_NAMES: "2p 2s 2p"}))

    def test_a_run_naming_no_lines_is_refused(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaises(AssemblyRefused):
                    line_names(_manifest(**{LINE_NAMES: value}))

    def test_a_set_of_lines_that_is_not_a_string_is_refused(self) -> None:
        # A manifest holds numbers, strings and booleans, so a list arrives as a
        # string or it does not arrive, and a number here is somebody assuming
        # otherwise.
        with self.assertRaises(AssemblyRefused):
            line_names(_manifest(**{LINE_NAMES: 2}))

    def test_a_line_no_named_file_carries_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            named_lines_spectrogram(_manifest(**{LINE_NAMES: "2p 2d"}))


class ARunCarriesTheFilesItReads(unittest.TestCase):
    def test_the_files_come_out_of_the_manifest(self) -> None:
        self.assertEqual(line_sources(_manifest()), (NEON_MAIN_LINES,))

    def test_a_run_reading_both_shipped_files_sees_every_line_in_them(self) -> None:
        # The property the satellite work rests on. Reading another file is a
        # longer manifest value and nothing else, and the lines it carries are
        # then lines the run may name.
        both = f"{NEON_MAIN_LINES} {NEON_2P_SHAKE_UP_SATELLITES}"
        entries = entries_for(_manifest(**{LINE_SOURCES: both}))
        self.assertEqual(
            set(entries),
            set(neon_main_lines()) | set(neon_2p_shake_up_satellites()),
        )

    def test_nothing_in_the_merge_records_which_file_a_line_came_from(self) -> None:
        # The structural half of docs/decisions/satellite-lines.md. What comes
        # back is a mapping of lines, and an entry out of it is the same object
        # the file loaded, so there is nowhere for a marker to have been added.
        both = f"{NEON_MAIN_LINES} {NEON_2P_SHAKE_UP_SATELLITES}"
        entries = entries_for(_manifest(**{LINE_SOURCES: both}))
        for name, entry in neon_2p_shake_up_satellites().items():
            with self.subTest(line=name):
                self.assertEqual(entries[name], entry)

    def test_a_line_two_files_both_carry_is_refused(self) -> None:
        # The near miss, built here rather than out of the tree: the shipped
        # files share no name today, and a case built out of them would prove
        # the state of the tree rather than the guard.
        entries = neon_main_lines()
        with self.assertRaises(AssemblyRefused):
            merge([("first.toml", entries), ("second.toml", entries)])

    def test_a_file_the_package_does_not_ship_is_refused(self) -> None:
        for named in ("../../../etc/passwd", "neon-main-lines.toml.bak", "nothing"):
            with self.subTest(named=named):
                with self.assertRaises(AtomicDataRefused):
                    entries_for(_manifest(**{LINE_SOURCES: named}))

    def test_a_file_named_twice_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            line_sources(
                _manifest(**{LINE_SOURCES: f"{NEON_MAIN_LINES} {NEON_MAIN_LINES}"})
            )

    def test_a_run_reading_no_file_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            line_sources(_manifest(**{LINE_SOURCES: ""}))


class TheStrengthsAreTheCrossSectionRatio(unittest.TestCase):
    def test_the_first_line_is_the_reference_and_is_exactly_one(self) -> None:
        strengths = relative_strengths(
            neon_main_lines(), NEON_MAIN_LINE_NAMES, _PHOTON_ELECTRONVOLT
        )
        self.assertEqual(strengths[0], 1.0)

    def test_the_strengths_are_what_the_data_file_gives(self) -> None:
        entries = neon_main_lines()
        strengths = relative_strengths(
            entries, NEON_MAIN_LINE_NAMES, _PHOTON_ELECTRONVOLT
        )
        expected = relative_cross_section(
            entries["2s"], entries["2p"], _PHOTON_ELECTRONVOLT
        )
        self.assertEqual(strengths[1], expected)

    def test_the_counts_each_line_carries_are_in_that_ratio(self) -> None:
        # The heights compared as counts and not as peak bins. The peak of a
        # streaking trace is set by how fast the map is moving the line in
        # energy, which goes as the line's momentum, so two lines in exactly the
        # cross section ratio have peak bins that are not.
        manifest = _manifest()
        entries = neon_main_lines()
        assembled = neon_main_lines_spectrogram(manifest)
        totals = {}
        for name in NEON_MAIN_LINE_NAMES:
            unstreaked = _unstreaked_from_the_file(name)
            reach = _excursion_electronvolt(manifest, unstreaked) + (
                _ENERGY_STEP_ELECTRONVOLT
            )
            totals[name] = _window_total(
                assembled, unstreaked - reach, unstreaked + reach
            )
        self.assertAlmostEqual(
            totals["2s"] / totals["2p"],
            relative_cross_section(entries["2s"], entries["2p"], _PHOTON_ELECTRONVOLT),
            delta=_RATIO_TOLERANCE,
        )


class TheLinesSitWhereTheFilePutsThem(unittest.TestCase):
    def test_each_line_is_entirely_inside_the_window_the_file_predicts(self) -> None:
        # The window is built from the binding energy in the data file and the
        # excursion the field gives, and neither comes from the assembler. A
        # line placed at the wrong energy leaves this window rather than being
        # compared against a number that moved with it.
        manifest = _manifest()
        assembled = neon_main_lines_spectrogram(manifest)
        strengths = relative_strengths(
            neon_main_lines(), NEON_MAIN_LINE_NAMES, _PHOTON_ELECTRONVOLT
        )
        for name, strength in zip(NEON_MAIN_LINE_NAMES, strengths):
            with self.subTest(line=name):
                unstreaked = _unstreaked_from_the_file(name)
                reach = _excursion_electronvolt(manifest, unstreaked) + (
                    _ENERGY_STEP_ELECTRONVOLT
                )
                inside = _window_total(
                    assembled, unstreaked - reach, unstreaked + reach
                )
                self.assertAlmostEqual(
                    inside / (strength * _DELAY_POINTS), 1.0, delta=_WINDOW_TOLERANCE
                )

    def test_the_two_windows_hold_everything_there_is(self) -> None:
        # Without this the case above would pass against an assembler that put
        # half of a line somewhere else as well.
        manifest = _manifest()
        assembled = neon_main_lines_spectrogram(manifest)
        inside = 0.0
        for name in NEON_MAIN_LINE_NAMES:
            unstreaked = _unstreaked_from_the_file(name)
            reach = _excursion_electronvolt(manifest, unstreaked) + (
                _ENERGY_STEP_ELECTRONVOLT
            )
            inside += _window_total(assembled, unstreaked - reach, unstreaked + reach)
        self.assertAlmostEqual(
            inside / assembled.total_counts(), 1.0, delta=_WINDOW_TOLERANCE
        )

    def test_a_line_the_file_does_not_carry_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            lines_of(_manifest(), neon_main_lines(), ("2d",))


class AScanTooShortIsRefused(unittest.TestCase):
    def _cycles(self, points: int) -> float:
        manifest = _manifest(**{DELAY_POINTS: points})
        delays = delay_axis_attosecond(manifest)
        span = float(delays[-1]) - float(delays[0])
        return span / streaking_period_attosecond(StreakingField(manifest))

    def test_the_period_is_the_carrier_s_own_period(self) -> None:
        # The number the scan is judged against comes from the field, and this
        # says so as a property of the potential rather than by writing the
        # formula out a second time. At a carrier envelope phase of zero the
        # potential is at a crest at time zero, at zero a quarter of a period
        # later, and at a trough half a period later. Only a period that is the
        # carrier's does that.
        field = StreakingField(_manifest())
        period = streaking_period_attosecond(field)
        peak = field.peak_vector_potential
        self.assertGreater(field.vector_potential(0.0), 0.0)
        self.assertLess(
            abs(field.vector_potential(0.25 * period)), _QUARTER_TOLERANCE * peak
        )
        self.assertLess(field.vector_potential(0.5 * period), 0.0)

    def test_a_scan_that_covers_the_minimum_is_assembled(self) -> None:
        self.assertGreaterEqual(self._cycles(_DELAY_POINTS), _MINIMUM_CYCLES)
        manifest = _manifest()
        self.assertGreater(neon_main_lines_spectrogram(manifest).total_counts(), 0.0)

    def test_the_same_scan_one_step_shorter_is_refused(self) -> None:
        # The near miss, and it is one delay step. The scan above clears the
        # minimum by less than a step, so this is the smallest change that puts
        # it under.
        self.assertLess(self._cycles(_DELAY_POINTS - 1), _MINIMUM_CYCLES)
        with self.assertRaises(AssemblyRefused):
            neon_main_lines_spectrogram(_manifest(**{DELAY_POINTS: _DELAY_POINTS - 1}))

    def test_the_refusal_names_the_number_of_cycles(self) -> None:
        manifest = _manifest(**{DELAY_POINTS: _DELAY_POINTS - 1})
        with self.assertRaises(AssemblyRefused) as refused:
            neon_main_lines_spectrogram(manifest)
        message = str(refused.exception)
        self.assertIn(str(self._cycles(_DELAY_POINTS - 1)), message)
        self.assertIn(str(_MINIMUM_CYCLES), message)

    def test_asking_for_more_cycles_refuses_the_scan_that_passed(self) -> None:
        # The other direction. The minimum is a parameter of the run, so a run
        # asking for more of the oscillation refuses a scan that a run asking
        # for less accepted, and nothing in the assembler decides which.
        with self.assertRaises(AssemblyRefused):
            neon_main_lines_spectrogram(_manifest(**{MINIMUM_CYCLES: 4.0}))


class TheGridsAreRefusedWhereTheyCouldNotBeGrids(unittest.TestCase):
    def test_a_delay_step_of_zero_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            delay_axis_attosecond(_manifest(**{DELAY_STEP: 0.0}))

    def test_a_negative_energy_step_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            energy_axis_electronvolt(_manifest(**{ENERGY_STEP: -0.02}))

    def test_a_single_delay_step_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            delay_axis_attosecond(_manifest(**{DELAY_POINTS: 1}))

    def test_a_point_count_that_is_not_a_whole_number_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            energy_axis_electronvolt(_manifest(**{ENERGY_POINTS: 2051.0}))

    def test_a_grid_parameter_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            energy_axis_electronvolt(_manifest(**{ENERGY_FIRST: "35.0"}))

    def test_a_scan_start_that_is_not_a_number_is_refused(self) -> None:
        with self.assertRaises(AssemblyRefused):
            delay_axis_attosecond(_manifest(**{DELAY_FIRST: "-2700.0"}))

    def test_a_scan_may_start_either_side_of_the_field(self) -> None:
        # Deliberate. The scan runs through the streaking pulse, so its first
        # delay is negative in every run this board makes.
        axis: NDArray[np.float64] = delay_axis_attosecond(_manifest())
        self.assertLess(float(axis[0]), 0.0)
        self.assertGreater(float(axis[-1]), 0.0)


if __name__ == "__main__":
    unittest.main()
