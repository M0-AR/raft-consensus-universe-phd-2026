"""Chaos monkey — dice choose the failure, invariants judge.

Per tick (every few ms of sim time):
  80% client write to whoever claims to be leader
   6% kill a server (half the time the leader)
   6% restart a dead one
   4% cut the network into two random pieces
   4% heal it
Plus 5% of all messages disappear (SimNet drop_rate).
Never keeps more than two servers dead at once (with 3 dead nothing
can happen anyway — minority cannot elect, by design).

While this runs, invariants.py watches:
  P1 one leader per term, P2 one command per index.
"""

from __future__ import annotations

from . import invariants as inv


class Monkey:
    def __init__(self, net, servers, rng, max_dead=2):
        self.net = net
        self.servers = servers
        self.rng = rng
        self.max_dead = max_dead
        self.kills = 0
        self.restarts = 0
        self.cuts = 0
        self.heals = 0
        self.writes = 0
        self.committed = 0
        self.wkey = 0

    def leaders(self):
        return [s for s in self.servers if s.role == "leader" and self.net.alive[s.id]]

    def tick(self):
        r = self.rng.random()
        if r < 0.80:
            self._write()
        elif r < 0.86:
            self._kill()
        elif r < 0.92:
            self._restart()
        elif r < 0.96:
            self._cut()
        else:
            self._heal()
        inv.check(self.servers)

    def _write(self):
        ls = self.leaders()
        if not ls:
            return
        l = self.rng.choice(ls)
        self.wkey += 1
        cmd = ("set", f"k{self.wkey % 7}", self.wkey)
        if l.client_write(cmd, self.net):
            self.writes += 1

    def _kill(self):
        alive = [i for i in range(self.net.n) if self.net.alive[i]]
        dead = self.net.n - len(alive)
        if dead >= self.max_dead or not alive:
            return
        ls = self.leaders()
        target = None
        if ls and self.rng.random() < 0.5:
            target = ls[0].id
        else:
            target = self.rng.choice(alive)
        self.net.kill(target)
        self.kills += 1

    def _restart(self):
        dead = [i for i in range(self.net.n) if not self.net.alive[i]]
        if not dead:
            return
        t = self.rng.choice(dead)
        self.net.restart(t)
        # restarted server reboots as follower with same persistent state
        # (log/term/vote survive — we never cleared them), fresh timers
        s = self.servers[t]
        s.role = "follower"
        s.leader_hint = None
        s._votes = set()
        s._reset_election_timer(self.net)
        # leader (if any) will bring it up to date via AppendEntries retry
        for u in self.servers:
            if u.role == "leader" and self.net.alive[u.id]:
                u._send_heartbeats(self.net)
        self.restarts += 1

    def _cut(self):
        n = self.net.n
        order = list(range(n))
        self.rng.shuffle(order)
        k = self.rng.randint(1, n - 1)
        self.net.set_partition([set(order[:k]), set(order[k:])])
        self.cuts += 1

    def _heal(self):
        self.net.set_partition(None)
        self.heals += 1
        for u in self.servers:
            if u.role == "leader" and self.net.alive[u.id]:
                u._send_heartbeats(self.net)

    def committed_count(self):
        # committed = min over alive-majority? Use leader commit as proxy:
        # count entries replicated on a majority (ground truth scan)
        if not self.servers:
            return 0
        maxlen = max(len(s.log) for s in self.servers)
        c = 0
        for idx in range(1, maxlen + 1):
            voters = 0
            cmd0 = None
            ok = True
            for s in self.servers:
                if len(s.log) >= idx:
                    if cmd0 is None:
                        cmd0 = s.log[idx - 1]
                    elif s.log[idx - 1] != cmd0:
                        ok = False
                        break
                    voters += 1
            if ok and voters >= self.net.n // 2 + 1:
                c = idx
        self.committed = c
        return c
