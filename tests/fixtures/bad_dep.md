# Plan: Bad Dep
## Overview
A phase depends on a non-existent phase. Parses fine, must fail at compile time.

## Out of Scope
- nothing

## Phase 1: Only
**Goal:** the only phase
**Depends on:** Phase 2
### Tasks
- [ ] T1.1 something
  - success_check: `true`
