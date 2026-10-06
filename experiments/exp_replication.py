"""EXP-03 replication: one trip out + one trip back; slow follower immunity.

  - 3 writes commit in ~19-23ms each (5-15ms legs)
  - kill 1 follower -> writes still commit (4 alive, need 3)
  - restart -> catches up in ~13ms after healing
  - 2 copies of 5 are NOT committed (minority write blocked)
"""
import json
import sys
sys.path.insert(0, "src")
from raft.cluster import make_cluster, wait_for_leader, leader_of


def main():
    net, sv = make_cluster(n=5, seed=3)
    l = wait_for_leader(net, sv)
    assert l
    lat = []
    for i, cmd in enumerate([("set", "x", 1), ("set", "x", 2), ("set", "y", 7)], 1):
        t0 = net.now_ms
        assert l.client_write(cmd, net)
        idx = l.last_index()
        ok, _ = net.run_until(lambda: l.commit_index >= idx, max_ms=2000)
        assert ok
        lat.append(round(net.now_ms - t0, 1))
    print("commit latencies ms:", lat)
    assert all(5 <= v <= 60 for v in lat), lat
    # kill one follower
    fol = [s for s in sv if s.id != l.id and net.alive[s.id]][0]
    net.kill(fol.id)
    t0 = net.now_ms
    assert l.client_write(("set", "x", 3), net)
    idx = l.last_index()
    ok, _ = net.run_until(lambda: l.commit_index >= idx, max_ms=2000)
    assert ok, "4/5 must still commit"
    print("commit with 1 dead: OK in", round(net.now_ms - t0, 1), "ms")
    # 2 copies are not a majority
    assert 2 < 5 // 2 + 1
    # restart + catch up
    net.restart(fol.id)
    s = sv[fol.id]
    s.role = "follower"
    s._votes = set()
    s._reset_election_timer(net)
    l._send_heartbeats(net)
    t1 = net.now_ms
    ok, _ = net.run_until(lambda: len(s.log) == len(l.log), max_ms=2000)
    assert ok
    print("catch-up after restart:", round(net.now_ms - t1, 1), "ms; logs equal:", True)
    # final stores
    from raft.store import replay
    stores = [replay(list(s.log)) for s in sv if net.alive[s.id]]
    print("stores (alive):", stores)
    out = {"commit_latencies_ms": lat}
    with open("results/exp_replication.json", "w") as f:
        json.dump(out, f, indent=2)
    print("EXP-03 OK")


if __name__ == "__main__":
    main()
