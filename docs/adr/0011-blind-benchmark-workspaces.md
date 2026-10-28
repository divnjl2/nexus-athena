# ADR-0011: Benchmark generation receives base archives, not task images

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Cited by: features/tdd-benchmark C-4.1 and C-4.4

## Context
TDD task images clone repositories. Their Git history can expose later code, even when
the working tree is reset to the issue's base revision. Keeping sealed data in another
directory is also insufficient when a generator can access the host filesystem or Docker.

## Decision
Export public issue data and the requested base-revision HTTP archive into a fresh
workspace. Keep fingerprints of issue bytes, archive bytes and source files. Do not run
Git or export repository history. Reject unsupported or unsafe archives explicitly.

Run untrusted code tools in an offline, non-root container with a read-only root and
public input mount, an empty separate output mount, and no Docker socket. Reuse only the
tool-only controller image, without evaluator or harness mounts; never reuse task images.
Model calls belong to the trusted orchestrator, which must expose only public tool data.

## Consequences
The download URL identifies the requested revision; this does not independently verify
a Git tree hash. Tool isolation does not establish model blindness if the orchestrator
adds other context. No model-quality result follows from a successful boundary smoke test.
The three-mode generator, budgets and actual Athena/trust execution still require their
own implementation and evaluation.
