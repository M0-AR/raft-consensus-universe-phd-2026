"""Raft store: deterministic state machine replays log in order.

Commands (tuples):
  ("set", key, value)  -> store[key] = value
  ("add", key, delta)  -> store[key] = store.get(key, 0) + delta

If two servers have identical logs in identical order, they must
arrive at identical stores. Order is everything (see test_order_matters).
"""

from __future__ import annotations


def apply(store: dict, cmd) -> None:
    op = cmd[0]
    if op == "set":
        _, k, v = cmd
        store[k] = v
    elif op == "add":
        _, k, d = cmd
        store[k] = store.get(k, 0) + d
    elif op == "noop":
        pass
    else:
        raise ValueError(f"unknown command {cmd!r}")


def replay(log: list) -> dict:
    """log: list of (term, cmd). Returns resulting store."""
    store: dict = {}
    for _term, cmd in log:
        apply(store, cmd)
    return store
