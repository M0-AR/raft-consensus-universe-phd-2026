"""Global safety invariants — checked live while the monkey runs.

P1 election safety:  at most one leader per term.
P2 state-machine safety: if any server applied cmd at index i, no server
   ever applies a different cmd at i (Figure 3 of the Raft paper).

Violation raises AssertionError and stops the run with an error,
exactly like the video's network alarm.
"""

from __future__ import annotations


def check(servers, terms_seen: dict | None = None) -> dict:
    # P1
    leaders_by_term: dict[int, list[int]] = {}
    for s in servers:
        if s.role == "leader":
            leaders_by_term.setdefault(s.current_term, []).append(s.id)
    for t, ls in leaders_by_term.items():
        assert len(ls) <= 1, f"P1 VIOLATION: two leaders in term {t}: {ls}"
    # P2
    applied: dict[int, tuple] = {}
    for s in servers:
        for idx, cmd in s.applied_at.items():
            if idx in applied:
                assert applied[idx] == cmd, (
                    f"P2 VIOLATION: index {idx}: {applied[idx]!r} vs {cmd!r}"
                )
            else:
                applied[idx] = cmd
    return {"leaders": leaders_by_term, "applied": len(applied)}
