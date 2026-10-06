"""Real-socket transport — same Server class, no line changed.

Five threads, one port per server, real clock. Length-prefixed JSON
over TCP loopback. Drop/partition hooks kept for live chaos demos.

Run: python -m raft.net_real  (or experiments/exp_live.py)
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time

from .server import Server


def _send_frame(sock: socket.socket, obj: dict):
    data = json.dumps(obj, default=str).encode()
    sock.sendall(struct.pack("!I", len(data)) + data)


def _recv_frames(conn: socket.socket):
    buf = b""
    while True:
        hdr = conn.recv(4)
        if not hdr:
            return
        (ln,) = struct.unpack("!I", hdr)
        payload = b""
        while len(payload) < ln:
            chunk = conn.recv(ln - len(payload))
            if not chunk:
                return
            payload += chunk
        yield json.loads(payload.decode())


class RealNet:
    """Adapter exposing send()/set_timer() like SimNet but over TCP."""

    def __init__(self, n, base_port=15000):
        import random as _r
        self.n = n
        self.base_port = base_port
        self.alive = [True] * n
        self.groups = [set(range(n))]
        self.rng = _r.Random()
        self.now_ms = 0.0  # wall clock tracked by driver
        self._t0 = time.time()
        self.servers: list[Server | None] = [None] * n
        self._timer_threads: dict = {}

    # SimNet-compatible API
    def attach(self, servers):
        self.servers = servers

    def set_partition(self, groups):
        self.groups = [set(range(self.n))] if groups is None else [set(g) for g in groups]

    def can_talk(self, a, b):
        if a == b:
            return True
        return any(a in g and b in g for g in self.groups)

    def kill(self, i):
        self.alive[i] = False

    def restart(self, i):
        self.alive[i] = True

    def send(self, src, dst, msg):
        if not self.alive[src] or not self.alive[dst]:
            return
        if not self.can_talk(src, dst):
            return
        # JSON-safe: tuples -> lists; convert entries
        def conv(o):
            if isinstance(o, tuple):
                return [conv(x) for x in o]
            if isinstance(o, list):
                return [conv(x) for x in o]
            if isinstance(o, dict):
                return {k: conv(v) for k, v in o.items()}
            return o
        safe = conv(msg)
        safe["_src"] = src
        try:
            with socket.create_connection(("127.0.0.1", self.base_port + dst),
                                          timeout=0.5) as s:
                _send_frame(s, safe)
        except OSError:
            pass

    def set_timer(self, sid, delay_ms, token):
        def fire():
            time.sleep(delay_ms / 1000.0)
            srv = self.servers[sid]
            if srv is not None and self.alive[sid]:
                # decode entries back to tuples for AppendEntries
                srv.on_timer(token, _DecodeNet(self, srv))
        t = threading.Thread(target=fire, daemon=True)
        t.start()

    @property
    def rng_uniform(self):
        return self.rng.uniform


class _DecodeNet:
    """Wraps RealNet so Server timers/requests decode tuples on send."""

    def __init__(self, real: RealNet, owner):
        self._r = real
        self._owner = owner

    def __getattr__(self, name):
        if name == "send":
            return self._send_decode
        return getattr(self._r, name)

    def _send_decode(self, src, dst, msg):
        return self._r.send(src, dst, msg)


def _restore(o):
    # entries arrive as lists; turn [term, [op,...]] back into tuples
    if isinstance(o, dict):
        d = {k: _restore(v) for k, v in o.items() if not k.startswith("_")}
        if "entries" in d and isinstance(d["entries"], list):
            d["entries"] = [tuple([e[0], tuple(e[1])] if isinstance(e, list) else e)
                            for e in d["entries"]]
        return d
    if isinstance(o, list):
        return [_restore(x) for x in o]
    return o


def serve_one(net: RealNet, sid: int, stop: threading.Event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", net.base_port + sid))
    srv.listen(50)
    srv.settimeout(0.2)
    while not stop.is_set():
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        try:
            for raw in _recv_frames(conn):
                src = raw.pop("_src", None)
                msg = _restore(raw)
                target = net.servers[sid]
                if target is not None and net.alive[sid] and src is not None:
                    target.on_message(src, msg, net)
        except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
            pass
        finally:
            conn.close()
    srv.close()
