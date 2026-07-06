# Spec: CAS Account Onboarding — Real MTProto Pipeline (§4-5, as shipped)

EARS requirements for the shipped account-onboarding iteration on cas-mvp master (86f0256): the
Python `opentele` sidecar (tdata → validated StringSession), the Fernet session vault shared with the
TS runtime, proxy-first binding in the GramJS transport, and the live-outreach cutover. Continues
`CAS_TG_Bot_MVP_Spec.md` §4-5.

Gated / manual (needs operator creds, NOT automated): the live `tdata → session → send` conversion,
which requires a real tdata folder, a SOCKS5 proxy, `CAS_TG_API_ID/HASH`, and `CAS_VAULT_KEY`.

## R1 — Proxy-first (survival invariant)
- R1.1 — A `socks5://[user:pass@]host:port` proxy SHALL parse into a bound proxy, and any malformed
  proxy SHALL raise BEFORE any connect — never silently fall through to the platform's shared IP.
- R1.2 — The MTProto transport SHALL REFUSE to connect an account that has no proxy (no shared-IP
  first packet, which would cluster and burn the whole pool).

## R2 — Session vault
- R2.1 — Session strings SHALL be stored encrypted (Fernet) keyed by `session_ref`, never in a DB
  column; a ref SHALL NOT be able to escape the vault directory (path traversal), and a missing key
  SHALL fail loudly.
- R2.2 — The TS runtime SHALL decrypt a session token written by the Python sidecar under the same
  `CAS_VAULT_KEY` (cross-language Fernet).

## R3 — tdata → session (sidecar)
- R3.1 — The sidecar SHALL convert a Telegram Desktop `tdata` folder to a Telethon StringSession
  reusing the current authorization (no fresh login), with the proxy bound before connect, storing
  the session only after login is validated. (Live path — proven manually, not by an automated test.)

## R4 — Live cutover & rate accounting
- R4.1 — Outreach SHALL run through the real GramJS transport when `CAS_LIVE=1` and through the mock
  transport otherwise; the live transport SHALL refuse any account lacking a proxy + vault session.
- R4.2 — Per-account rate accounting (`sent_today`) SHALL be incremented exactly once per send
  (owned by AccountPool), never double-counted by the transport.
