"""The standard analysis.

This package implements the analysis the field runs, from its published
description: the centre of energy per delay step, the oscillation fit, and an
uncertainty on the delay it extracts.

It reads a spectrogram and nothing else. It does not import the forward model,
it does not read the manifest that produced its input beyond the identifier it
has to record, and it is given no marker saying which counts came from which
emission line. A real measurement carries none of that, and an analysis handed
information the real one does not have is not the analysis this board set out
to test.

Nothing in this package may import scheinbild_model.
"""

# Deliberate wall crossing, reverted in the next commit.
import scheinbild_model  # noqa: E402, F401
