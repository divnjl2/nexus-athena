# Intent

Implement `eval_rpn(expr: str) -> float` in `rpn.py`.

It evaluates a Reverse Polish Notation (postfix) arithmetic expression given as a
space-separated string of numbers and operators, returning the numeric result.

This is the ONLY input to the planner. The eval measures how good a plan (spec +
scenarios + tasks) Athena derives from this one-line intent, and whether code built
to that plan passes an independent ground-truth gate.
