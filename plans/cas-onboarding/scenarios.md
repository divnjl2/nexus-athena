# Scenarios: CAS Account Onboarding (§4-5, as shipped)

> `run_cmd`s are real green tests in `cas-mvp` (C:\Users\пк\Repos\cas-mvp) on master (86f0256).
> The live tdata→session conversion (R3.1) has no automated test — see plan Manual Verification.

## R1 — Proxy-first
### S1.1 — socks5 parses; malformed fails loudly
- **verifies:** R1.1
- **run_cmd:** `python -m pytest -q services/onboarding`
- **Given** proxy urls valid (with/without auth) and malformed (bad scheme, no port, empty)
- **When** parse_socks5 runs
- **Then** valid ones yield host/port/creds and every malformed one raises before any connect.

### S1.2 — transport refuses an account with no proxy
- **verifies:** R1.2
- **run_cmd:** `npx vitest run packages/accounts/test/gramjs_proxy.test.mjs`
- **Given** an account row with a session but no proxy
- **When** the GramJS transport tries to open a client
- **Then** it throws "no proxy — refusing to connect on the shared IP" before any client is built.

## R2 — Session vault
### S2.1 — Fernet vault: roundtrip, encryption, path-safety
- **verifies:** R2.1
- **run_cmd:** `python -m pytest -q services/onboarding`
- **Given** a CAS_VAULT_KEY and a session string
- **When** it is put and read back
- **Then** it roundtrips, the file is ciphertext (not plaintext), a traversal ref is rejected, and a missing key raises.

### S2.2 — TS runtime decrypts a Python-written token
- **verifies:** R2.2
- **run_cmd:** `npx vitest run packages/accounts/test/vault_interop.test.mjs`
- **Given** a session token produced by Python's cryptography.fernet under a shared key
- **When** the node vault reads it
- **Then** it decrypts to the exact plaintext (cross-language Fernet holds).

## R4 — Live cutover & rate accounting
### S4.1 — live vs mock transport selection
- **verifies:** R4.1
- **run_cmd:** `node --check apps/manager-bot/run.mjs`
- **Given** the outreach runner
- **When** CAS_LIVE is set vs unset
- **Then** it selects the GramJS transport (lazy-loaded) vs the mock, and the bot module stays valid.

> R4.2 (single-owner rate accounting / no double-count) has NO honest automated test — it is a
> code-inspection change (sent_today removed from the transport; AccountPool.markSent is the sole
> owner). Deliberately NOT compiled as a scenario rather than mapped to a test that doesn't prove it.
