"""Unit tests: order matters, majority, election, replication, safety.

Run: python3 -m pytest tests/ -q  (stdlib only; pytest if available,
else python3 tests/run_all.py)
"""
import sys
sys.path.insert(0, "src")
from raft.store import replay
from raft.server import majority
from raft.cluster import make_cluster, wait_for_leader, leader_of


def test_order_matters():
    a = replay([(1, ("set", "x", 1)), (1, ("add", "x", 4))])
    b = replay([(1, ("add", "x", 4)), (1, ("set", "x", 1))])
    assert a["x"] == 5 and b["x"] == 1


def test_majority_table():
    assert majority(3) == 2 and majority(5) == 3 and majority(7) == 4


def test_election_and_commit():
    net, sv = make_cluster(n=5, seed=5)
    l = wait_for_leader(net, sv)
    assert l is not None
    assert l.client_write(("set", "x", 1), net)
    idx = l.last_index()
    ok, _ = net.run_until(lambda: l.commit_index >= idx, max_ms=2000)
    assert ok


def test_minority_cannot_elect():
    net, sv = make_cluster(n=5, seed=6)
    l = wait_for_leader(net, sv)
    assert l
    alive = [s.id for s in sv if s.id != l.id][:2]
    for s in sv:
        if s.id not in alive:
            net.kill(s.id)
    net.run_ms(3000)
    assert leader_of(sv, net) is None
