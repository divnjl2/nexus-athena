# Intent

Implement `compare_semver(a: str, b: str) -> int` in `semver.py`.

It compares two semantic-version strings of the form `MAJOR.MINOR.PATCH` (optionally with a
`-prerelease` suffix, e.g. `1.2.3-rc1`) and returns -1 if a < b, 0 if equal, 1 if a > b.

This is the only input to the planner. The eval measures how complete a plan the real
Athena pipeline derives from this one-line intent.
