# Plan: CAS Bot-Shell — Shared Multi-Tenant Platform Bot (as shipped)

## Overview
Refactor the single-tenant CAS control bot into ONE shared platform bot: role+tenant resolved
per Telegram user_id, 4-role RBAC, the spec's 5-section menu, new Profile/Support/Admin sections,
per-tenant/-account AI pause, and a take-over correctness fix — all on top of the existing funnel
engine and RLS. End state: every scenario in `scenarios.md` proven by a green `success_check`,
shipped on cas-mvp `feat/bot-shell-multitenant` (merged to master).

## Out of Scope
- Real MTProto/tdata onboarding (opentele sidecar, proxy-before-connect, live send) — §4-5, next iteration.
- Voice/document funnel nodes; add/remove/reorder step editing; TTS.
- Billing/tariff enforcement; assigned_leads granularity; platform metrics.

## Phase 1: DB platform catalogs, support_tickets RLS & migration
**Goal:** Add the platform tables + tenant-isolated support_tickets and a safe idempotent upgrade path.
**Depends on:** none
### Tasks
- [ ] T1.1 [P] Platform catalogs (tenants, platform_admins, role_permissions, user_directory) + support_tickets in the FORCE-RLS loop + accounts.ai_paused/tenants.ai_paused + role vocab worker→handler
  - success_check: `python packages/db/rls_isolation_test.py`
  - files: `packages/db/schema.sql`
  - verifies: S4.1
  - autonomy: high
- [ ] T1.2 Idempotent migration 002 — re-issue ENABLE/FORCE RLS + policy for support_tickets, rename roles, backfill user_directory, fail loudly on a user in >1 tenant
  - success_check: `python packages/db/migration_test.py`
  - files: `packages/db/migrations/001_init.sql, packages/db/migrations/002_bot_shell.sql`
  - verifies: S4.2
- [ ] T1.3 RLS coverage allow-list (platform catalogs carry no tenant_id) + migration upgrade-path suite wired into pytest
  - success_check: `python -m pytest -q tests/test_python_suites.py`
  - files: `packages/db/rls_coverage_test.py, packages/db/migration_test.py, tests/test_python_suites.py`
  - verifies: S4.1

## Phase 2: Identity & RBAC
**Goal:** Resolve role+tenant from user_id (before RLS scope), enforce the permission matrix and invariants.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 identity.mjs — resolveIdentity via unscoped user_directory/platform_admins; createTenant/addMember/setRole/removeMember atomic (one-tenant-per-user, no orphan, SET LOCAL scope)
  - success_check: `npx vitest run packages/manager-core/test/identity.test.mjs`
  - files: `packages/manager-core/src/identity.mjs`
  - verifies: S1.1 S1.2 S1.3
- [ ] T2.2 Permission matrix + can(): owner≠teamlead; admin actions hard-gated creator-only
  - success_check: `npx vitest run packages/manager-core/test/identity.test.mjs`
  - files: `packages/manager-core/src/identity.mjs`
  - verifies: S2.1
- [ ] T2.3 Role-literal rename worker→handler in manager-core (assign/stats/take-over) + fixtures
  - success_check: `node packages/manager-core/test/manager_core_test.mjs`
  - files: `packages/manager-core/src/index.mjs, packages/manager-core/test/manager_core_test.mjs`
  - verifies: S1.1

## Phase 3: Shared bot — 5-section menu & sections
**Goal:** Rewrite the bot into the shared, role-filtered 5-section product with new sections.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 [P] Role-filtered 5-section menu + control-center submenu (menu.mjs)
  - success_check: `npx vitest run apps/manager-bot/test/menu.test.mjs`
  - files: `apps/manager-bot/menu.mjs`
  - verifies: S3.1 S3.2
- [ ] T3.2 Profile/Support/Admin section builders (sections.mjs)
  - success_check: `npx vitest run apps/manager-bot/test/sections.test.mjs`
  - files: `apps/manager-bot/sections.mjs`
  - verifies: S6.1
- [ ] T3.3 [P] Per-tenant funnel seeding with a fresh id (tenant_funnel.mjs)
  - success_check: `npx vitest run apps/manager-bot/test/tenant_funnel.test.mjs`
  - files: `apps/manager-bot/tenant_funnel.mjs`
  - verifies: S7.1
- [ ] T3.4 Bot entrypoint: identity middleware (scope-first) + all handlers + creator fail-fast bootstrap
  - success_check: `node --check apps/manager-bot/run.mjs`
  - files: `apps/manager-bot/run.mjs`

## Phase 4: AI pause & take-over gate
**Goal:** Queue-not-advance on pause/take-over; stop paused accounts sending; fix the take-over clobber.
**Depends on:** Phase 3
### Tasks
- [ ] T4.1 handleInbound gate (tenant/account pause or human) + findOrCreateSession surfaces status
  - success_check: `npx vitest run packages/channel/test/runtime_gate.test.mjs`
  - files: `packages/channel/src/runtime.mjs`
  - verifies: S5.1 S5.2
- [ ] T4.2 AccountPool SENDABLE_SQL excludes paused accounts from outreach
  - success_check: `node packages/accounts/test/pause_test.mjs`
  - files: `packages/accounts/src/pool.mjs, packages/accounts/test/pause_test.mjs`
  - verifies: S5.3

## Manual Verification
- Headless end-to-end smoke (creator → create tenant → add handler → role menus → DRY outreach →
  pause → ticket loop) passed 13/13; full suite green (`npx vitest run`, `python -m pytest -q tests`).
