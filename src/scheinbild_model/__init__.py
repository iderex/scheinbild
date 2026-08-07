"""The forward model.

This package builds a simulated streaking spectrogram from a run manifest: the
ionising pulse, the streaking field, the emission lines with their intrinsic
delays, the spectrometer response and the counting statistics.

It knows the true delay, because the operator put it in the manifest. That is
the whole point of it, and it is why this package and the standard analysis are
separate importable units rather than two directories inside one. The analysis
is meant to be kept blind to what is in here, and a wall that exists only as a
directory boundary is a wall nothing can refuse a crossing of.

Nothing in this package may import scheinbild_analysis.
"""
