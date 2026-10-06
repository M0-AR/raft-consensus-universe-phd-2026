"""EXP-07 live: same Server class on real TCP sockets (no line changed).

5 threads, ports BASE..BASE+4, real clock. Boot -> leader ~150ms,
3 writes -> kill leader -> new leader ~244ms -> writes -> restart old,
catch up, all 5 stores agree. Timings vary per run (real network).
This is the 'real life data' verification: simulated determinism +
live wall-clock agreement.
"""
import sys
import threading
import time
sys.path.insert(0, "src")
from raft.server import Server
from raft.net_real import RealNet, serve_one


def main(base=17800):
    net = RealNet(5, base_port=base)
    servers = [Server(i, 5) for i in range(5)]
    net.attach(servers)
    stop = threading.Event()
    threads = [threading.Thread(target=serve_one, args=(net, i, stop),
                                daemon=True) for i in range(5)]
    for t in threads:
        t.start()
    for s in servers:
        s.boot(net)
    time.sleep(1.2)
    ls = [s for s in servers if s.role == "leader"]
    assert len(ls) == 1, f"expected 1 live leader, got {len(ls)}"
    l = ls[0]
    print(f"live leader={l.id} term={l.current_term}")
    for cmd in [(("set", "x", 1)), (("set", "x", 3)), (("set", "y", 7))]:
        assert l.client_write(cmd, net)
        time.sleep(0.4)
    print("stores after 3 writes:", [dict(s.store) for s in servers])
    # kill leader
    net.kill(l.id)
    print(f"killed {l.id}")
    t0 = time.time()
    l2 = None
    for _ in range(100):
        time.sleep(0.1)
        cand = [s for s in servers
                if s.role == "leader" and net.alive[s.id]]
        if cand:
            l2 = cand[0]
            break
    assert l2 is not None, "no live failover!"
    dt = (time.time() - t0) * 1000
    print(f"failover to {l2.id} term={l2.current_term} in {dt:.0f}ms (live)")
    for cmd in [(("set", "z", 1)), (("set", "z", 2))]:
        assert l2.client_write(cmd, net)
        time.sleep(0.4)
    net.restart(l.id)
    s = servers[l.id]
    s.role = "follower"
    s._votes = set()
    s._reset_election_timer(net)
    time.sleep(1.5)
    print("final stores:", [dict(x.store) for x in servers])
    assert len({tuple(sorted(x.store.items())) for x in servers}) == 1
    print("EXP-07 OK: live cluster agrees")
    stop.set()


if __name__ == "__main__":
    main()
