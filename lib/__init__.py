"""Athena core library: deterministic plan.md -> bd compiler.

Modules:
  plan_parser  — strict plan.md -> dataclasses (no I/O).
  plan2beads   — pure compiler: Plan -> bd commands (no I/O, no time, no random).
  bd_client    — the ONLY subprocess/I/O boundary.
"""
