# scheinbild

Since 2010 the best-known measurement in the field has stood at about 20 as for the 2s-2p relative delay in neon while theory finds much less, with even the elaborate RMT calculation giving 10.2 plus-minus 1.3 as at 105.2 eV, a factor of two below. The suspicion points at the analysis rather than the physics: limited energy resolution lets the 2s main line overlap shake-up emission accompanying the 2p line, which can distort the observed delay. This board builds an open forward model including satellite lines and finite resolution, puts in a known true delay, and runs the standard analysis over the simulated spectrogram to see what it returns. The choices in the model are fixed and recorded before that analysis runs, because a model tuned until it yields the expected factor has proved only that it can be tuned.

Planning happens on the issue tracker first. Every decision that shapes
the architecture is written down there with its reasons before the code
that depends on it exists.

See [NOTICE.md](NOTICE.md) for the intended-use notice.

## Install

You need the interpreter version pinned under `requires-python` in
[pyproject.toml](pyproject.toml). That field is the only place in the tree
where the number is written, so read it there rather than from a document that
would drift against it. An install run on any other interpreter is refused
before anything is built.

No step below needs elevated privileges, and none of them opens a window.

On Linux and macOS:

    python -m venv .venv
    .venv/bin/python -m pip install --editable .

On Windows:

    python -m venv .venv
    .venv\Scripts\python -m pip install --editable .

## Install the exact graph the gate installed

The commands above resolve dependencies fresh, which is what you want while
reading the code and not what you want while reproducing a number. `uv.lock`
holds the graph the gate is green about, and installing from it resolves
nothing:

    uv sync --locked

It fails rather than quietly updating the lockfile, so an install that succeeds
is an install of the committed graph and not of some later one. The gate holds
the same two properties under the check named `Locked dependencies`.

## Check the install

The tree holds two importable units, the forward model and the standard
analysis, kept separate on purpose. Importing both is what says the install
worked.

On Linux and macOS:

    .venv/bin/python -c "import scheinbild_model, scheinbild_analysis"

On Windows:

    .venv\Scripts\python -c "import scheinbild_model, scheinbild_analysis"

The command prints nothing and exits zero when both packages import.

## The tree

    src/scheinbild_model/       the forward model
    src/scheinbild_analysis/    the standard analysis
    tests/                      the test suite
    docs/decisions/             the decisions the rest of the board rests on
