# Scenarios: CAS Bot-Shell — Shared Multi-Tenant Platform Bot (as shipped)

> One Given-When-Then per EARS criterion. Stable IDs `S<req>.<index>` map to the EARS list in
> `spec.md`. Each `run_cmd` is the REAL test that proves it, run in the `cas-mvp` repo
> (`C:\Users\пк\Repos\cas-mvp`); all are green on `feat/bot-shell-multitenant` (merged to master).

---

## R1 — Identity & tenancy

### S1.1 — Resolve role+tenant from user_id, creator precedence
- **verifies:** R1.1, R1.2
- **run_cmd:** `npx vitest run packages/manager-core/test/identity.test.mjs`
- **Given** a creator in `platform_admins` and owner/handler rows in `user_directory`
- **When** `resolveIdentity` runs before any tenant scope is set
- **Then** each resolves to the right `{role, tenant}`, and a user who is both admin and member resolves as creator.

### S1.2 — One-tenant-per-user enforced
- **verifies:** R1.3
- **run_cmd:** `npx vitest run packages/manager-core/test/identity.test.mjs`
- **Given** a user already a member of tenant A
- **When** they are added to tenant B
- **Then** the call throws and A's roster + routing rows are unchanged.

### S1.3 — createTenant is atomic (no orphan)
- **verifies:** R1.4
- **run_cmd:** `npx vitest run packages/manager-core/test/identity.test.mjs`
- **Given** an owner who already belongs to another tenant
- **When** createTenant is called with them as owner
- **Then** it throws and no orphaned `tenants` row remains.

## R2 — RBAC

### S2.1 — Matrix differentiates roles; admin is creator-only
- **verifies:** R2.1, R2.2
- **run_cmd:** `npx vitest run packages/manager-core/test/identity.test.mjs`
- **Given** the permission matrix (defaults and the DB `role_permissions`)
- **When** `can(role, action)` is evaluated
- **Then** owner has billing/mint-teamlead where teamlead does not, and `menu.admin`/`admin.*` are false for every non-creator even if a custom matrix sets them true.

## R3 — Five-section menu

### S3.1 — Main menu is role-filtered
- **verifies:** R3.1
- **run_cmd:** `npx vitest run apps/manager-bot/test/menu.test.mjs`
- **Given** each role
- **When** the main menu is built
- **Then** creator sees Profile/Support/Admin only; owner/teamlead see Accounts+Control; handler has no Accounts.

### S3.2 — Control center gates by role
- **verifies:** R3.2
- **run_cmd:** `npx vitest run apps/manager-bot/test/menu.test.mjs`
- **Given** the Control Center submenu
- **When** built for a handler vs owner/teamlead
- **Then** the handler sees only dialogs; owner/teamlead additionally get pause/workflow/stats/team.

## R4 — Isolation & migration safety

### S4.1 — support_tickets isolated; platform catalogs excluded
- **verifies:** R4.1, R4.2
- **run_cmd:** `python -m pytest -q tests/test_python_suites.py`
- **Given** the schema built fresh with two tenants
- **When** the RLS isolation + coverage guards run
- **Then** `support_tickets` reads are tenant-scoped and the four platform catalogs carry no `tenant_id`.

### S4.2 — Upgrade migration closes the RLS hole and guards duplicates
- **verifies:** R4.3
- **run_cmd:** `python packages/db/migration_test.py`
- **Given** a pre-change DB with old-vocab managers
- **When** `002_bot_shell.sql` is applied
- **Then** `support_tickets` gains functioning RLS, roles/columns/backfill land, applying twice is a no-op, and a user in two tenants fails the migration loudly.

## R5 — AI pause & take-over

### S5.1 — Paused/human inbound does not advance the funnel
- **verifies:** R5.1, R5.3
- **run_cmd:** `npx vitest run packages/channel/test/runtime_gate.test.mjs`
- **Given** a lead whose tenant or account is paused
- **When** an inbound arrives
- **Then** it is persisted but the funnel cursor does not advance and no reply is sent.

### S5.2 — Take-over is not clobbered
- **verifies:** R5.2
- **run_cmd:** `npx vitest run packages/channel/test/runtime_gate.test.mjs`
- **Given** a lead session with status `human`
- **When** the next inbound arrives
- **Then** the cursor and `human` status are preserved and the bot does not reply over the human.

### S5.3 — Paused account is excluded from outreach
- **verifies:** R5.3
- **run_cmd:** `node packages/accounts/test/pause_test.mjs`
- **Given** a tenant with one healthy account and one `ai_paused` account (both past warm-up)
- **When** AccountPool selects sendable accounts
- **Then** the paused account is excluded (`healthyIds`/`canSend`), and un-pausing makes it sendable again.

## R6 — Sections

### S6.1 — Profile/Support/Admin builders render correctly
- **verifies:** R6.1
- **run_cmd:** `npx vitest run apps/manager-bot/test/sections.test.mjs`
- **Given** a seeded tenant and a filed ticket
- **When** the section builders run
- **Then** Profile shows tenant/plan/limits, member support offers ticket filing while creator gets the inbox, and Admin lists tenants + the role matrix.

## R7 — Per-tenant funnel

### S7.1 — Each tenant gets a distinct funnel id
- **verifies:** R7.1
- **run_cmd:** `npx vitest run apps/manager-bot/test/tenant_funnel.test.mjs`
- **Given** two tenants seeded from the same funnel preset
- **When** `ensureTenantFunnel` runs for each
- **Then** they receive distinct funnel ids (not the preset id) and re-running is idempotent per tenant.
