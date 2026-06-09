# Plan: Cycle
## Overview
A depends on B and B depends on A — a dependency cycle the compiler misses but seam.ast_wellformed catches.

## Out of Scope
- nothing

## Phase 1: A
**Goal:** a
**Depends on:** Phase 2
### Tasks
- [ ] T1.1 do a
  - success_check: `true`

## Phase 2: B
**Goal:** b
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 do b
  - success_check: `true`
