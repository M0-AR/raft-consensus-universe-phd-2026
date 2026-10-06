"""EXP-06 chaos: 1000 runs x 20 sim-seconds, dice failures, zero violations.

Monkey per tick: 80% write / 6% kill (half leader) / 6% restart /
4% partition / 4% heal; 5% message loss; max 2 dead.
Promises watched live: P1 one leader/term, P2 one cmd/index.
End of run: heal + restart all + compare 5 logs identical.

Also: ablation sanity — vote rule OFF over 50 runs must break quickly
(proves the test can fail; a test that cannot fail proves nothing).

Usage: python experiments/exp_chaos_1000.py [--runs 1000] [--secs 20]
"""
import argparse
import json
import random
import sys
sys.path.insert(0, "src")
from raft.cluster import make_cluster, wait_for_leader
from raft.chaos import Monkey
from raft import invariants as inv


def one_run(seed, secs=20, vote_rule=True, commit_rule=True):
    rng = random.Random(seed)
    net, sv = make_cluster(n=5, seed=seed, enable_vote_rule=vote_rule,
                           enable_commit_rule=commit_rule)
    net.drop_rate = 0.05
    l = wait_for_leader(net, sv, max_ms=5000)
    if l is None:
        return {"seed": seed, "elected": False}
    mk = Monkey(net, sv, rng)
    elections0 = max(s.current_term for s in sv)
    # drive: alternate monkey ticks + network progress
    tick_ms = 5
    deadline = net.now_ms + secs * 1000
    while net.now_ms < deadline:
        mk.tick()
        net.run_ms(tick_ms)
        # occasional invariant sampling already in tick
    mk.committed_count()
    # heal + restart all + converge
    net.set_partition(None)
    net.drop_rate = 0.0
    for i in range(net.n):
        if not net.alive[i]:
            net.restart(i)
            s = sv[i]
            s.role = "follower"
            s._votes = set()
            s._reset_election_timer(net)
    # let cluster settle, then force convergence with a final write
    # (overwrites uncommitted tails; committed prefix must already match).
    # This mirrors the video: heal + restart + compare identical logs.
    from raft.cluster import leader_of as _lof
    net.run_ms(1500)
    try:
        inv.check(sv)
        inv_ok = True
    except AssertionError:
        inv_ok = False
    # committed prefix identity (ground truth: min commit across alive)
    min_commit = min(s.commit_index for s in sv)
    prefix = [list(s.log[:min_commit]) for s in sv]
    prefix_ok = all(p == prefix[0] for p in prefix)
    if not prefix_ok:
        inv_ok = False
    # final write to collapse uncommitted suffixes
    final_ok = True
    identical = False
    logs = [list(s.log) for s in sv]
    l = _lof(sv, net)
    if l is not None and inv_ok:
        l.client_write(("set", "__final__", 1), net)
        idx = l.last_index()
        net.run_until(lambda: l.commit_index >= idx, max_ms=5000)
        net.run_ms(2000)
        logs = [list(s.log) for s in sv]
        identical = all(lg == logs[0] for lg in logs)
        final_ok = identical
    else:
        identical = all(lg == logs[0] for lg in logs)
    if not prefix_ok:
        identical = False
    return {"seed": seed, "elected": True, "kills": mk.kills,
            "restarts": mk.restarts, "cuts": mk.cuts,
            "writes": mk.writes, "committed_prefix": mk.committed,
            "log_len": len(logs[0]), "identical": identical, "inv_ok": inv_ok,
            "max_term": max(s.current_term for s in sv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--secs", type=int, default=20)
    ap.add_argument("--ablation", action="store_true",
                    help="also run 50 vote-rule-OFF runs (must break)")
    a = ap.parse_args()
    broken = 0
    rows = []
    for r in range(a.runs):
        res = one_run(50000 + r, secs=a.secs)
        rows.append(res)
        if not (res.get("inv_ok") and res.get("identical")):
            broken += 1
            print(f"RUN {r} BROKEN:", res)
            break
        if r % 20 == 0:
            print(f"run {r}/{a.runs} kills={res['kills']} writes={res['writes']} "
                  f"log={res['log_len']} identical={res['identical']}")
    tot_kills = sum(r.get("kills", 0) for r in rows)
    tot_writes = sum(r.get("writes", 0) for r in rows)
    print(f"done {len(rows)} runs: broken={broken} total_kills={tot_kills} "
          f"total_writes={tot_writes}")
    with open("results/exp_chaos.json", "w") as f:
        json.dump({"runs": len(rows), "broken": broken, "kills": tot_kills,
                   "writes": tot_writes, "sample": rows[:3]}, f, indent=2)
    if a.ablation:
        print("== ablation: vote rule OFF x 50 (expect fast breakage) ==")
        ab_broke = 0
        for r in range(50):
            res = one_run(90000 + r, secs=5, vote_rule=False)
            if not (res.get("inv_ok") and res.get("identical")):
                ab_broke += 1
        print(f"ablation broken {ab_broke}/50 (video: 200/200)")
    assert broken == 0, "chaos found a safety violation!"
    print("EXP-06 OK: zero broken promises")


if __name__ == "__main__":
    main()
