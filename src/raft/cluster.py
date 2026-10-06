"""Cluster helpers: boot N servers on a SimNet, elect, write, wait."""

from __future__ import annotations

from .net_sim import SimNet
from .server import Server


def make_cluster(n=5, seed=0, **kw):
    net = SimNet(n, seed=seed)
    servers = [Server(i, n, **kw) for i in range(n)]
    net.attach(servers)
    for s in servers:
        s.boot(net)
    return net, servers


def leader_of(servers, net=None):
    ls = [s for s in servers if s.role == "leader" and (net is None or net.alive[s.id])]
    return ls[0] if len(ls) == 1 else None


def wait_for_leader(net, servers, max_ms=5000):
    ok, _ = net.run_until(lambda: leader_of(servers, net) is not None,
                          max_ms=max_ms)
    return leader_of(servers, net) if ok else None


def write_and_commit(net, servers, cmd, max_ms=2000):
    l = leader_of(servers, net)
    assert l is not None, "no leader to write to"
    assert l.client_write(cmd, net)
    idx = l.last_index()
    maj = len(servers) // 2 + 1
    ok, _ = net.run_until(
        lambda: sum(1 for s in servers if len(s.log) >= idx) >= maj
        and l.commit_index >= idx,
        max_ms=max_ms)
    # let followers learn commit
    net.run_ms(100)
    return ok
