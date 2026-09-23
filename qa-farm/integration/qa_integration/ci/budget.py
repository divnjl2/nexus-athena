"""CI: wall-clock budget guard. On overrun it returns a first-class budget_breach result — it
never silently times out and never silently passes (R7.2 / EC-7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetResult:
    breached: bool
    elapsed_s: float
    budget_s: int


def check_budget(*, start: float, now: float, budget_s: int) -> BudgetResult:
    elapsed = now - start
    return BudgetResult(breached=elapsed > budget_s, elapsed_s=round(elapsed, 4), budget_s=budget_s)
