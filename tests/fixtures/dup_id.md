# Plan: Dup Id
## Overview
Two tasks share the id T1.1. Must be rejected at parse time.

## Out of Scope
- nothing

## Phase 1: A
**Goal:** first
**Depends on:** none
### Tasks
- [ ] T1.1 first
  - success_check: `true`

## Phase 2: B
**Goal:** second
**Depends on:** Phase 1
### Tasks
- [ ] T1.1 duplicate id
  - success_check: `true`
