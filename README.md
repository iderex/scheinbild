# scheinbild

Since 2010 the best-known measurement in the field has stood at about 20 as for the 2s-2p relative delay in neon while theory finds much less, with even the elaborate RMT calculation giving 10.2 plus-minus 1.3 as at 105.2 eV, a factor of two below. The suspicion points at the analysis rather than the physics: limited energy resolution lets the 2s main line overlap shake-up emission accompanying the 2p line, which can distort the observed delay. This board builds an open forward model including satellite lines and finite resolution, puts in a known true delay, and runs the standard analysis over the simulated spectrogram to see what it returns. The choices in the model are fixed and recorded before that analysis runs, because a model tuned until it yields the expected factor has proved only that it can be tuned.

Planning happens on the issue tracker first. Every decision that shapes
the architecture is written down there with its reasons before the code
that depends on it exists.

See [NOTICE.md](NOTICE.md) for the intended-use notice.
