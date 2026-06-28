# Intent

Implement `wildcard_match(pattern: str, text: str) -> bool` in `wildcard.py`.

It returns True iff `text` matches `pattern`, where the pattern language supports two
wildcards: `*` matches any sequence of characters (including the empty sequence) and `?`
matches exactly one character. All other characters are literals. The match is against the
ENTIRE text (anchored, not a substring search).

This is the only input to the planner. The eval measures how complete a plan the real
Athena pipeline derives from this one-line intent.
