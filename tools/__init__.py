"""Tools the gate runs, and nothing an operator installs.

This directory is not in the wheel: `pyproject.toml` packages the forward model
and the standard analysis and nothing else, so what is here cannot be imported
out of an installed copy and cannot become something the model depends on.

It is importable from the repository root, which is how the test suite reaches
it. The suite runs with the repository root as its top level directory, so
`import tools.invariants` works from a clone with nothing installed.
"""
