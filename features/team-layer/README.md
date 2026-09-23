# The team layer, contracting itself

Seven weaknesses named against modern AI-native and spec-driven practice, each closed as a
clause group written before the code. What each one is, and the decision it rests on:

| group | closes | decision |
|---|---|---|
| C-1 specs as data | specs were pytest internals; GWT was prose | [ADR-0001](../../docs/adr/0001-specs-as-data.md) |
| C-2 decisions kept | design decisions lived in an ignored folder | [ADR-0002](../../docs/adr/0002-decisions-live-in-docs-adr.md) |
| C-3 intake | `source: incident` had no path behind it | [ADR-0004](../../docs/adr/0004-intake-writes-draft-and-red-first.md) |
| C-4 id lanes | two branches allocate the same id | [ADR-0003](../../docs/adr/0003-clause-id-lanes.md) |
| C-5 harness | nobody told the agent the blast radius | [ADR-0005](../../docs/adr/0005-harness-hooks.md) |
| C-6 budgets, runs | no NFRs, no record of iterations | clauses only |
| C-7 properties | proofs were examples | clauses only |

```bash
python athena.py check features/team-layer/contract.md --front features/team-layer/plan.md \
    --ledger features/team-layer/spec_ledger.json --map features/team-layer/clause_map.json --text
python athena.py adr lint docs/adr --text && python athena.py adr unlinked docs/adr --text
python athena.py lint arch --text
python athena.py metrics features/team-layer/contract.md --text
```

`cases/` holds JSON specs run in-process (ADR-0001); they prove clauses of the other layers
a second time, as behaviour rather than as a pytest node.
