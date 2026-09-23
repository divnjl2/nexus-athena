# The core layer, contracting itself

This folder is the contract for the top of the pyramid: the semantic core, the origin of
each clause, the rerun of lessons, the way into the repository, the Stop gate and the fast
spec lane. It was written before the code that satisfies it, and the verdict at the bottom
is how you know whether it still holds.

| File | Written by | Answers |
|---|---|---|
| `contract.md` | a human | what is guaranteed |
| `scenarios.md` | a human; `pins:` by the tool | how each clause is proved |
| `plan.md` | a human | what work carries which spec |
| `spec_ledger.json` | `athena spec run` | which specs were green, and when |
| `clause_map.json` | `athena contract map` | which lines of which files each clause owns |

```bash
python athena.py check features/core-layer/contract.md --front features/core-layer/plan.md \
    --ledger features/core-layer/spec_ledger.json --map features/core-layer/clause_map.json --text
python athena.py contract sources features/core-layer/contract.md --text
python athena.py lessons rerun features/core-layer/contract.md --text
python athena.py gate --text
```
