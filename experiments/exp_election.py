"""EXP-02 election: kill the leader, measure failover; split-vote study.

Replicates Raft paper Fig.16 + video Part 4 on simulated time:
  - healthy election at boot (~183-201ms with seed control)
  - kill leader -> new leader in ~181ms (video number, seed-dependent)
  - kill again with 3 alive -> term with no winner, then recovery
  - 2 alive cannot elect (minority does nothing, term climbs)
  - split-vote sweep: timeout range width vs median/worst failover

Outputs results/exp_election.json + CSV. Deterministic by seed.
"""
import csv
import json
import statistics
import sys
sys.path.insert(0, "src")
from raft.cluster import make_cluster, wait_for_leader, leader_of


def single_failover(seed=7):
    net, sv = make_cluster(n=5, seed=seed)
    l0 = wait_for_leader(net, sv)
    t0 = net.now_ms
    assert l0 is not None
    net.kill(l0.id)
    # run until new leader
    ok, _ = net.run_until(lambda: leader_of(sv, net) is not None, max_ms=10000)
    t1 = net.now_ms
    l1 = leader_of(sv, net)
    return {"seed": seed, "old_leader": l0.id, "new_leader": l1.id if l1 else None,
            "downtime_ms": round(t1 - t0, 1), "term": l1.current_term if l1 else None}


def sweep(trials=200):
    # timeout-range experiment: fixed 150-150 vs 150-155 vs 150-175 vs 150-300
    configs = [(150, 150), (150, 155), (150, 175), (150, 200), (150, 300)]
    rows = []
    for lo, hi in configs:
        downs = []
        stuck = 0
        for s in range(trials):
            net, sv = make_cluster(n=5, seed=10000 + s,
                                   election_range=(lo, hi))
            l0 = wait_for_leader(net, sv, max_ms=30000)
            if l0 is None:
                stuck += 1
                continue
            t0 = net.now_ms
            net.kill(l0.id)
            ok, _ = net.run_until(lambda: leader_of(sv, net) is not None,
                                  max_ms=10000)
            if not ok:
                stuck += 1
            else:
                downs.append(net.now_ms - t0)
        downs_s = sorted(downs)
        med = statistics.median(downs_s) if downs_s else None
        worst = max(downs_s) if downs_s else None
        rows.append({"range": f"{lo}-{hi}", "trials": trials, "stuck": stuck,
                     "median_ms": round(med, 1) if med else None,
                     "worst_ms": round(worst, 1) if worst else None})
        print(f"range {lo}-{hi}: stuck={stuck}/{trials} median={med} worst={worst}")
    return rows


def minority_check():
    net, sv = make_cluster(n=5, seed=99)
    l = wait_for_leader(net, sv)
    assert l is not None
    # kill 3 -> 2 alive
    alive = [s.id for s in sv if s.id != l.id][:2]
    # kill everyone except first two followers
    for s in sv:
        if s.id not in alive:
            net.kill(s.id)
    t_term0 = sv[alive[0]].current_term
    net.run_ms(5000)
    l2 = leader_of(sv, net)
    return {"alive": alive, "leader_after_5s": l2.id if l2 else None,
            "term_grew": sv[alive[0]].current_term > t_term0}


def main():
    print("== single failover ==")
    one = single_failover(seed=7)
    print(one)
    print("== minority liveness check ==")
    mc = minority_check()
    print(mc)
    assert mc["leader_after_5s"] is None, "minority must not elect!"
    print("== split-vote sweep (200 trials per range) ==")
    rows = sweep(trials=200)
    with open("results/exp_election.json", "w") as f:
        json.dump({"single": one, "minority": mc, "sweep": rows}, f, indent=2)
    with open("results/exp_election.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["range", "trials", "stuck",
                                          "median_ms", "worst_ms"])
        w.writeheader()
        w.writerows(rows)
    print("wrote results/exp_election.{json,csv}")


if __name__ == "__main__":
    main()
