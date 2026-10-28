# Running repository tests

Use a dedicated virtual environment and install the direct test dependencies with
`python -m pip install -r requirements-test.txt`. The dependency list records the
versions used by the local Python 3.13 publication lane; it is not a lock for every
transitive dependency or an assertion that every Python version is supported.

For controlled plugin discovery, set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and run
`python -m pytest -p pytest_benchmark.plugin tests`. The explicit plugin supplies the
benchmark fixture even with autoload disabled. Do not omit performance or telemetry
tests to obtain a green result. Git authorization is required by the operator's
AGENTS.md before running tests that create temporary repositories or collect Git
metadata. Tests which require bd remain subject to their declared integration setup.

The complete native verification lane also puts `bd`, `vale` and `conftest` on PATH.
The verified Windows release versions and archive checksums are recorded in
`tests/tool-versions.json`. Verify official release checksums before extraction; use
the corresponding platform release on other operating systems. Missing CLIs cause
explicit skips in repository pytest and do not establish their contract obligations.
The native lane executes the real bd graph integration, Vale's positive/negative
style control, and Conftest's accepting and rejecting policy inputs.

Temporary filesystem fixtures must use pytest's `tmp_path` rather than assuming a
drive letter or an operator-specific directory. The clause-map no-coverage test keeps
its injected runner and unsafe-command rejection assertions with a portable workdir.
