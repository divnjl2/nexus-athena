# Spec: CAS Bot-Shell — Shared Multi-Tenant Platform Bot (as shipped)

EARS requirements for the **shipped** iteration (feat/bot-shell-multitenant, merged to
cas-mvp master): the product-shell refactor turning the single-tenant control bot into ONE
shared platform bot with 4-role RBAC, the spec's 5-section menu, the new Profile/Support/
Admin sections, per-tenant/-account AI pause, and the take-over correctness fix. Continues
`CAS_TG_Bot_MVP_Spec.md` (§1-3, §6-9) and the multitenant-isolation arch doc (rev 2).

Out of scope this iteration (deferred, not claimed): real MTProto/tdata onboarding
(§4-5 opentele sidecar, proxy-before-connect, live send), voice/document funnel nodes,
add/remove/reorder step editing, TTS, billing enforcement, assigned_leads granularity.

---

## R1 — Identity & tenancy (shared bot, resolved per user_id)

- R1.1 — The system SHALL resolve each Telegram user to exactly one `{role, tenant}` from the
  unscoped platform tables (`platform_admins`, `user_directory`) BEFORE any tenant-scoped query,
  so a teamlead/handler resolves even though `managers` is FORCE-RLS.
- R1.2 — WHEN a user is both a platform admin and a tenant member, the system SHALL resolve them
  as `creator` (platform_admins wins).
- R1.3 — The system SHALL enforce one-tenant-per-user: adding a user who already belongs to a
  different tenant SHALL fail loudly and leave both the roster and routing tables unchanged.
- R1.4 — Creating a tenant with its owner SHALL be atomic — a failed owner registration SHALL
  leave no orphaned tenant row.

## R2 — RBAC (4 roles)

- R2.1 — The system SHALL model roles creator / owner / teamlead / handler with a permission
  matrix; owner and teamlead SHALL differ (owner sees billing and may mint teamleads).
- R2.2 — Admin-panel actions SHALL be creator-exclusive and SHALL NOT be grantable to any tenant
  role, even via a customized `role_permissions` row.

## R3 — Five-section menu (§3), role-filtered

- R3.1 — The main menu SHALL render exactly the sections each role may use: creator →
  Profile/Support/Admin; owner/teamlead → Accounts/Control/Profile/Support; handler →
  Control/Profile/Support (no Accounts).
- R3.2 — In the Control Center a handler SHALL see only dialogs; owner/teamlead SHALL additionally
  see pause, workflow editor, stats, team, leads/outreach.

## R4 — Tenant isolation & migration safety

- R4.1 — `support_tickets` SHALL be tenant-isolated by RLS; a session scoped to tenant A SHALL NOT
  read tenant B's tickets.
- R4.2 — The platform catalogs (`tenants`, `platform_admins`, `role_permissions`, `user_directory`)
  SHALL carry no `tenant_id` column, so the RLS coverage guard neither flags nor is relaxed for them.
- R4.3 — The idempotent upgrade migration SHALL re-issue ENABLE/FORCE RLS + policy for
  `support_tickets` (a fresh CREATE TABLE has RLS off) and SHALL fail loudly if any Telegram user is
  a manager in more than one tenant.

## R5 — AI pause & take-over (§6, §8)

- R5.1 — WHEN the AI is paused (tenant-wide or on the lead's account) OR a human has taken the lead,
  the system SHALL persist the inbound but SHALL NOT advance the funnel.
- R5.2 — A human take-over SHALL NOT be overwritten by a subsequent inbound (the funnel cursor and
  the `human` status SHALL be preserved).
- R5.3 — A paused account SHALL also be excluded from outreach sending, not only inbound replies.

## R6 — Sections (§7-9)

- R6.1 — Profile SHALL show the user's role, tenant, plan, limits and team size; Support SHALL offer
  FAQ plus ticket filing for members and a cross-tenant ticket inbox for the creator; Admin SHALL
  list/create tenants and show the role matrix.

## R7 — Per-tenant funnel

- R7.1 — Each tenant SHALL own a distinct funnel (a fresh id, not the shared preset id) so seeding a
  second tenant cannot collide on the funnel primary key; seeding SHALL be idempotent per tenant.
