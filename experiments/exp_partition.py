"""EXP-04 partition: two leaders at once is fine; only one can commit.

Scenario (video Part 6 Attack 1):
  {2,3} | {0,1,4}. Old leader 2 keeps writing on minority side (2 copies,
  never committed, client never told yes). Majority side elects new leader,
  commits 3 writes. Heal -> old leader sees higher term, steps down,
  drops uncommitted conflict, converges (~61ms in video; sim similar).

Asserts P1/P2 throughout and final log identity.
"""
import json
import sys
sys.path.insert(0, "src")
from raft.cluster import make_cluster, wait_for_leader, leader_of
from raft import invariants as inv


def main():
    net, sv = make_cluster(n=5, seed=11)
    l0 = wait_for_leader(net, sv)
    assert l0
    # commit 2 baseline entries
    for cmd in [("set", "x", 1), ("set", "y", 1)]:
        assert l0.client_write(cmd, net)
        idx = l0.last_index()
        net.run_until(lambda: l0.commit_index >= idx, max_ms=2000)
    net.run_ms(100)
    print(f"baseline committed={l0.commit_index} leader={l0.id} term={l0.current_term}")
    # partition: force l0 onto minority side {l0, other} vs rest
    other = [s.id for s in sv if s.id != l0.id][0]
    minority = {l0.id, other}
    majority_side = set(range(5)) - minority
    net.set_partition([minority, majority_side])
    print(f"partition minority={sorted(minority)} majority={sorted(majority_side)}")
    # minority leader writes (never commits)
    l0.client_write(("set", "x", 100), net)
    l0.client_write(("set", "y", 200), net)
    net.run_ms(300)
    assert l0.commit_index == 2, f"minority must not advance commit: {l0.commit_index}"
    # majority side elects
    ok, _ = net.run_until(
        lambda: any(s.role == "leader" and s.id in majority_side for s in sv),
        max_ms=5000)
    assert ok, "majority side must elect"
    l1 = [s for s in sv if s.role == "leader" and s.id in majority_side][0]
    print(f"majority leader={l1.id} term={l1.current_term} (old={l0.id} term={l0.current_term})")
    # two leaders coexist briefly — allowed; check P1 per-term still holds
    inv.check(sv)
    # majority commits 3 writes
    for cmd in [("set", "a", 1), ("set", "b", 2), ("set", "c", 3)]:
        assert l1.client_write(cmd, net)
        idx = l1.last_index()
        net.run_until(lambda: l1.commit_index >= idx, max_ms=3000)
    net.run_ms(200)
    inv.check(sv)
    # heal
    t0 = net.now_ms
    net.set_partition(None)
    for s in sv:
        if s.role == "leader" and net.alive[s.id]:
            s._send_heartbeats(net)
    ok, _ = net.run_until(
        lambda: len({tuple(s.log) for s in sv}) == 1, max_ms=5000)
    assert ok, "logs must converge after heal"
    dt = round(net.now_ms - t0, 1)
    print(f"converged {dt}ms after heal; len={len(sv[0].log)}")
    inv.check(sv)
    # uncommitted minority entries were dropped (safe: client never acked)
    cmds = [c for _, c in sv[0].log]
    assert ("set", "x", 100) not in cmds and ("set", "y", 200) not in cmds
    with open("results/exp_partition.json", "w") as f:
        json.dump({"converge_ms": dt, "log_len": len(sv[0].log)}, f, indent=2)
    print("EXP-04 OK")


if __name__ == "__main__":
    main()
