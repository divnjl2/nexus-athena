# Plan: CAS Account Onboarding — Real MTProto Pipeline (§4-5, as shipped)

## Overview
Turn the account pipeline from mock/DRY into a real one: a Python `opentele` sidecar converts a
`tdata` folder to a validated Telethon StringSession (proxy bound before connect), a Fernet vault
hands that session to the TS runtime, the GramJS transport binds each account's SOCKS5 proxy and
refuses to connect without one, and outreach flips to live under `CAS_LIVE=1`. Shipped on cas-mvp
master (86f0256). The live `tdata → session → send` conversion is gated on operator creds and proven
manually, not by an automated test.

## Out of Scope
- Automated verification of the live tdata→session conversion (needs a real tdata + proxy + api creds).
- Voice/document funnel nodes, add/remove/reorder step editing, TTS, billing, assigned_leads.

## Phase 1: Proxy-first & session vault
**Goal:** The survival-critical proxy-first binding and the encrypted, cross-language session vault.
**Depends on:** none
### Tasks
- [ ] T1.1 [P] socks5 parser (fail-loud) in the Python sidecar
  - success_check: `python -m pytest -q services/onboarding`
  - files: `services/onboarding/proxy.py, services/onboarding/test_onboarding.py`
  - verifies: S1.1
  - autonomy: high
- [ ] T1.2 Fernet session vault (encrypted, path-safe, key-required)
  - success_check: `python -m pytest -q services/onboarding`
  - files: `services/onboarding/vault.py, services/onboarding/test_onboarding.py`
  - verifies: S2.1
- [ ] T1.3 Proxy-first GramJS transport — parse acc.proxy + refuse an account with no proxy
  - success_check: `npx vitest run packages/accounts/test/gramjs_proxy.test.mjs`
  - files: `packages/accounts/src/gramjs_channel.mjs, packages/accounts/test/gramjs_proxy.test.mjs`
  - verifies: S1.2
- [ ] T1.4 [P] TS runtime reads the Python-written Fernet session (cross-language)
  - success_check: `npx vitest run packages/accounts/test/vault_interop.test.mjs`
  - files: `packages/accounts/src/vault.mjs, packages/accounts/test/vault_interop.test.mjs`
  - verifies: S2.2

## Phase 2: tdata → session sidecar
**Goal:** opentele conversion reusing the current auth, proxy-first, login-validated (live/manual).
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 onboard.py — tdata → validated StringSession via opentele (proxy bound before connect)
  - success_check: `python -c "import sys; sys.path.insert(0,'services/onboarding'); import onboard"`
  - files: `services/onboarding/onboard.py`
- [ ] T2.2 cli.py entrypoint + optional DB warming→ok promotion
  - success_check: `python -c "import sys; sys.path.insert(0,'services/onboarding'); import cli"`
  - files: `services/onboarding/cli.py, services/onboarding/requirements.txt, services/onboarding/README.md`

## Phase 3: Live cutover
**Goal:** Flip outreach to the real transport under a flag; wire the sidecar tests into CI.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 CAS_LIVE outreach cutover (lazy-load GramJS) in the bot
  - success_check: `node --check apps/manager-bot/run.mjs`
  - files: `apps/manager-bot/run.mjs`
  - verifies: S4.1
- [ ] T3.2 CI runs the onboarding sidecar tests (+ cryptography)
  - success_check: `python -m pytest -q services/onboarding`
  - files: `.github/workflows/ci.yml`
  - verifies: S1.1

## Manual Verification (gated — needs operator creds)
- Provide `CAS_VAULT_KEY`, a real `tdata`, a SOCKS5 proxy, `CAS_TG_API_ID/HASH` (2040 for the
  onboarded session). Run `services/onboarding/cli.py --tdata ... --proxy ... --ref acc_01` → expect
  `{"ok":true,...}` and `~/.cas-vault/acc_01.token`. Then in the bot with `CAS_LIVE=1`, run
  🎛 Центр управления → 📥 Лиды → 🚀 Аутрич → the opening message is sent through the account's proxy.
