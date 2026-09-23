# ADR-0002: Decisions live in docs/adr, owned by a human

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/team-layer C-2.*

## Context

The pyramid is core, then decisions and requirements, then specs, then code. The CRISP
design step wrote its Design Decisions to `thoughts/qrspi/<id>/design.md`, and `thoughts/`
is ignored by git. Decisions were lost between sessions; the `see:` mechanism with
fingerprints existed but had nothing to point at except CORE.md.

## Decision

Decision records live in `docs/adr/NNNN-slug.md` in a short MADR shape: a title with an id,
Status, Date, Context, Decision, Consequences. A clause cites the record it rests on with
`see: ../../docs/adr/NNNN-slug.md@<fingerprint>`; a record nobody cites is reported
unlinked. The CRISP design step writes its decisions there as well as into the working
notes. `CORE.md`, every `contract.md` and `docs/adr/` are owned by a human in CODEOWNERS:
an agent proposes, the owner's merge is the record of approval.

## Consequences

- A change to a decision makes the citing clauses suspect until somebody re-reads them.
- Design notes in `thoughts/` remain scratch; anything that must outlive the session is an
  ADR.
- `athena adr lint` and `athena adr unlinked` are cheap and run in the gate lane.
