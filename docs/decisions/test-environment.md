# The headless and no-elevation rule for the test suite

Decided in issue #12.

Settled at the start rather than repaired later. A suite that has quietly grown a
display dependency is a suite only its author can run, and by the time anyone
notices, the dependency is load bearing.

## The rule

Every test in the default suite runs with no display attached and with no
elevated privileges, on Linux, macOS and Windows.

A test that cannot meet that does not go in the default suite.

This is a promise to anyone who clones the repository, not an internal policy.
It is the reason their machine will not need anything special to check this
work.

## The display bound path

For this board the display bound path is figure generation, and it is not
hypothetical. A plotting library that picks an interactive backend when one is
available will try to open a window in a suite that never asked for one, and it
will do it on the one platform the author does not use.

Two requirements follow.

The plotting backend is forced to a non interactive one before anything imports
the plotting library. Before, not after: an import that has already selected a
backend does not reselect.

Figure tests assert on the data going into the figure, never on rendered pixels.
Pixel comparison is fragile across font and library versions in a way that
produces failures nobody can act on, and a test nobody can act on gets disabled.

## Elevation

Nothing planned needs elevation.

That is stated anyway, because this is the kind of requirement that arrives with
one convenient change and is then written up as a prerequisite instead of being
treated as the defect it is. A test that asks for elevation is a defect in the
test until somebody argues otherwise in writing.

If a future path genuinely needs a privileged operation, a display, or specific
hardware, then it goes in a separate harness, the harness name states the
requirement it imposes, it is out of the default suite by default, and the
reason is written where the person running it will see it.

## The separate harnesses, and the two reasons for separation

There are two reasons a test may sit outside the default suite, and they are not
interchangeable.

Separation for an environment reason. The test needs something the default suite
promises not to need: a display, elevation, or particular hardware. A harness
separated for this reason names the requirement in its own name, so that nobody
runs it expecting the promise above to hold.

Separation for a time reason. The test needs nothing the default suite does not
have, and is separated only because it is slow. The long running full grid end
to end run is the case this board already expects. It needs no display and no
elevation, so it stays runnable everywhere, and it is out of the default suite
on time cost alone.

The distinction is written down so that nobody later uses a time cost to smuggle
in an environment requirement. A harness that started as slow and became
privileged has changed category, and it is renamed when that happens.
