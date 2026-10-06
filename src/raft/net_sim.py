"""Deterministic simulated network + clock.

One class, three jobs (as in the video):
  send()     - deliver a message to another server a little later (5-15ms)
  set_timer()- wake a server up after some time
  clock      - jumps straight to next message/timer (fast + replayable)

All randomness flows from random.Random(seed), so the same seed
replays the same run exactly. Supports: kill/restart, partition,
message loss, latency injection.

Design notes from 2026 best practice (Naman Gupta raft-lab, HashiCorp
divergence docs, Antithesis findings):
  - transport is an interface; simulated transport is intentionally hostile
  - each delivery checks: sender alive, receiver alive, partition allows,
    drop-rate, then schedules with latency
  - timers are per-server single deadline (election OR heartbeat tick)
"""

from __future__ import annotations

import heapq
import random


class SimNet:
    def __init__(self, n, seed=0, latency=(5, 15), drop_rate=0.0):
        self.n = n
        self.rng = random.Random(seed)
        self.seed = seed
        self.lat_min, self.lat_max = latency
        self.drop_rate = drop_rate
        self.now_ms = 0.0
        self._seq = 0
        self._queue: list = []  # (time, seq, kind, payload)
        self.alive = [True] * n
        # partition: set of frozenset sides, or None. We model as groups:
        # servers can talk iff same group. Default: one group.
        self.groups: list[set] = [set(range(n))]
        self.servers: list = [None] * n
        self.sent = 0
        self.delivered = 0
        self.dropped = 0

    # -- wiring ---------------------------------------------------------
    def attach(self, servers):
        self.servers = servers

    # -- partitions ------------------------------------------------------
    def set_partition(self, groups: list[set] | None):
        """groups e.g. [{0,1,4},{2,3}] or None for healed."""
        if groups is None:
            self.groups = [set(range(self.n))]
        else:
            self.groups = [set(g) for g in groups]

    def can_talk(self, a: int, b: int) -> bool:
        if a == b:
            return True
        for g in self.groups:
            if a in g and b in g:
                return True
        return False

    # -- failures --------------------------------------------------------
    def kill(self, i: int):
        self.alive[i] = False

    def restart(self, i: int):
        self.alive[i] = True

    # -- messaging -------------------------------------------------------
    def send(self, src: int, dst: int, msg: dict):
        self.sent += 1
        if not self.alive[src]:
            self.dropped += 1
            return
        if not self.alive[dst]:
            self.dropped += 1
            return
        if not self.can_talk(src, dst):
            self.dropped += 1
            return
        if self.rng.random() < self.drop_rate:
            self.dropped += 1
            return
        delay = self.rng.uniform(self.lat_min, self.lat_max)
        self._sched(self.now_ms + delay, "msg", (src, dst, msg))

    def set_timer(self, server_id: int, delay_ms: float, token: int):
        """One-shot timer. Server ignores stale tokens."""
        self._sched(self.now_ms + delay_ms, "timer", (server_id, token))

    def _sched(self, t: float, kind: str, payload):
        self._seq += 1
        heapq.heappush(self._queue, (t, self._seq, kind, payload))

    # -- main loop --------------------------------------------------------
    def step(self) -> bool:
        """Deliver next event. Returns False if queue empty."""
        if not self._queue:
            return False
        t, _, kind, payload = heapq.heappop(self._queue)
        self.now_ms = t
        if kind == "msg":
            src, dst, msg = payload
            # re-check liveness/partition at delivery time (link failures)
            if not self.alive[dst]:
                self.dropped += 1
                return True
            if not self.can_talk(src, dst):
                self.dropped += 1
                return True
            if self.rng.random() < 0.0:  # delivery-time loss disabled; send-time only
                pass
            self.delivered += 1
            srv = self.servers[dst]
            if srv is not None:
                srv.on_message(src, msg, self)
        elif kind == "timer":
            sid, token = payload
            srv = self.servers[sid]
            if srv is not None and self.alive[sid]:
                srv.on_timer(token, self)
        return True

    def run_until(self, cond, max_events=500_000, max_ms=None):
        """Run until cond() is True. Returns (ok, events_used)."""
        ev = 0
        while self._queue:
            if cond():
                return True, ev
            if max_ms is not None and self.now_ms > max_ms:
                return False, ev
            if ev >= max_events:
                return False, ev
            self.step()
            ev += 1
        return cond(), ev

    def run_ms(self, ms: float, max_events=500_000):
        deadline = self.now_ms + ms
        ev = 0
        while self._queue and self.now_ms < deadline and ev < max_events:
            # peek
            t = self._queue[0][0]
            if t > deadline:
                self.now_ms = deadline
                break
            self.step()
            ev += 1
        else:
            if self.now_ms < deadline:
                self.now_ms = deadline
        return ev
