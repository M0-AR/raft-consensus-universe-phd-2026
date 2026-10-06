"""Raft server: leader election (§5.2), log replication (§5.3), safety (§5.4).

Single-threaded per server, driven by SimNet or RealNet. No libraries.
Implements Figure 2 of Ongaro & Ousterhout (extended version 2014):

  Persistent: currentTerm, votedFor, log[(term, cmd)]
  Volatile:   commitIndex, lastApplied
  Leader:     nextIndex[], matchIndex[]

Safety rules (the parts that hurt):
  R1 vote rule   (§5.4.1): never vote for a log behind your own.
      Compare (lastTerm, lastIndex): later term wins; if equal, longer wins.
  R2 commit rule (§5.4.2): leader counts replicas only for own-term entries.
      Older entries commit indirectly with the first own-term majority.
"""

from __future__ import annotations

from .store import apply

FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"

ELECTION_MIN_MS = 150.0
ELECTION_MAX_MS = 300.0
HEARTBEAT_MS = 50.0


def majority(n: int) -> int:
    return n // 2 + 1


def is_up_to_date(cand_last_term, cand_last_idx, voter_last_term, voter_last_idx) -> bool:
    """True if candidate log is at least as up-to-date as voter's."""
    if cand_last_term != voter_last_term:
        return cand_last_term > voter_last_term
    return cand_last_idx >= voter_last_idx


class Server:
    def __init__(self, sid: int, n: int,
                 election_range=(ELECTION_MIN_MS, ELECTION_MAX_MS),
                 heartbeat_ms: float = HEARTBEAT_MS,
                 enable_vote_rule: bool = True,
                 enable_commit_rule: bool = True):
        self.id = sid
        self.n = n
        self.peers = [p for p in range(n) if p != sid]
        self.election_min, self.election_max = election_range
        self.heartbeat_ms = heartbeat_ms
        self.enable_vote_rule = enable_vote_rule
        self.enable_commit_rule = enable_commit_rule

        # persistent
        self.current_term = 0
        self.voted_for = None
        self.log: list[tuple[int, tuple]] = []  # (term, cmd)

        # volatile
        self.commit_index = 0
        self.last_applied = 0
        self.store: dict = {}
        self.role = FOLLOWER
        self.leader_hint = None

        # candidate
        self._votes: set = set()
        # leader
        self.next_index: dict[int, int] = {}
        self.match_index: dict[int, int] = {}

        self._timer_token = 0
        # for invariant checker: index -> cmd applied
        self.applied_at: dict[int, tuple] = {}

    # -- helpers --------------------------------------------------------
    def last_index(self) -> int:
        return len(self.log)

    def last_term(self) -> int:
        return self.log[-1][0] if self.log else 0

    def _election_delay(self, net) -> float:
        lo, hi = self.election_min, self.election_max
        if hi <= lo:
            return float(lo)
        return net.rng.uniform(lo, hi)

    def _reset_election_timer(self, net):
        self._timer_token += 1
        net.set_timer(self.id, self._election_delay(net), self._timer_token)

    def _schedule_heartbeat(self, net):
        self._timer_token += 1
        net.set_timer(self.id, self.heartbeat_ms, self._timer_token)

    # -- lifecycle -------------------------------------------------------
    def boot(self, net):
        self.role = FOLLOWER
        self._reset_election_timer(net)

    def _step_down(self, new_term: int, net, leader_hint=None):
        if new_term > self.current_term:
            self.current_term = new_term
            self.voted_for = None
        self.role = FOLLOWER
        self.leader_hint = leader_hint
        self._votes = set()
        self._reset_election_timer(net)

    # -- timers ----------------------------------------------------------
    def on_timer(self, token: int, net):
        if token != self._timer_token:
            return
        if not net.alive[self.id]:
            return
        if self.role == LEADER:
            self._send_heartbeats(net)
            self._schedule_heartbeat(net)
        else:
            # election timeout (follower or candidate, incl. split-vote retry)
            self._start_election(net)

    # -- election ---------------------------------------------------------
    def _start_election(self, net):
        self.current_term += 1
        self.role = CANDIDATE
        self.voted_for = self.id
        self._votes = {self.id}
        self.leader_hint = None
        self._timer_token += 1
        tok = self._timer_token
        net.set_timer(self.id, self._election_delay(net), tok)
        last_idx = self.last_index()
        last_term = self.last_term()
        for p in self.peers:
            net.send(self.id, p, {
                "type": "RequestVote",
                "term": self.current_term,
                "candidate": self.id,
                "last_idx": last_idx,
                "last_term": last_term,
            })
        # single-node cluster wins immediately
        if len(self._votes) >= majority(self.n):
            self._become_leader(net)

    def _become_leader(self, net):
        self.role = LEADER
        self.leader_hint = self.id
        last = self.last_index()
        for p in self.peers:
            self.next_index[p] = last + 1
            self.match_index[p] = 0
        self._send_heartbeats(net)
        self._schedule_heartbeat(net)

    # -- client ------------------------------------------------------------
    def client_write(self, cmd, net) -> bool:
        """Returns False if not leader (client should retry elsewhere)."""
        if self.role != LEADER:
            return False
        self.log.append((self.current_term, cmd))
        self._send_heartbeats(net)
        return True

    # -- replication -------------------------------------------------------
    def _send_heartbeats(self, net):
        for p in self.peers:
            nxt = self.next_index.get(p, self.last_index() + 1)
            # Ablation guard: a stale leader (vote rule OFF) can believe a
            # follower matches beyond its own last index. Clamp safely so the
            # run survives long enough to exhibit the P2 data-loss violation
            # instead of crashing with IndexError. Unreachable when R1 holds.
            if nxt > self.last_index() + 1:
                nxt = self.last_index() + 1
                self.next_index[p] = nxt
            prev_idx = nxt - 1
            prev_term = self.log[prev_idx - 1][0] if 1 <= prev_idx <= len(self.log) else 0
            entries = list(self.log[nxt - 1:])
            net.send(self.id, p, {
                "type": "AppendEntries",
                "term": self.current_term,
                "leader": self.id,
                "prev_idx": prev_idx,
                "prev_term": prev_term,
                "entries": entries,
                "commit": self.commit_index,
            })

    def _send_to(self, net, peer: int):
        nxt = self.next_index.get(peer, self.last_index() + 1)
        if nxt > self.last_index() + 1:
            nxt = self.last_index() + 1
            self.next_index[peer] = nxt
        prev_idx = nxt - 1
        prev_term = self.log[prev_idx - 1][0] if 1 <= prev_idx <= len(self.log) else 0
        entries = list(self.log[nxt - 1:])
        net.send(self.id, peer, {
            "type": "AppendEntries",
            "term": self.current_term,
            "leader": self.id,
            "prev_idx": prev_idx,
            "prev_term": prev_term,
            "entries": entries,
            "commit": self.commit_index,
        })

    def _advance_commit(self):
        # R2: only count own-term entries (§5.4.2)
        for cand in range(self.last_index(), self.commit_index, -1):
            term_c = self.log[cand - 1][0]
            if self.enable_commit_rule and term_c != self.current_term:
                continue
            count = 1  # self
            for p in self.peers:
                if self.match_index.get(p, 0) >= cand:
                    count += 1
            if count >= majority(self.n):
                self.commit_index = cand
                self._apply_committed()
                return

    def _apply_committed(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            term_c, cmd = self.log[self.last_applied - 1]
            apply(self.store, cmd)
            # record for cross-server invariant checks
            if self.last_applied in self.applied_at:
                # same server must never apply two cmds at one index
                assert self.applied_at[self.last_applied] == cmd, (
                    f"server {self.id} re-applied index {self.last_applied}"
                )
            self.applied_at[self.last_applied] = cmd

    # -- message dispatch ----------------------------------------------------
    def on_message(self, src: int, msg: dict, net):
        mtype = msg.get("type")
        term = msg.get("term", 0)
        # universal step-down on higher term (§5.1)
        if term > self.current_term:
            self._step_down(term, net,
                            leader_hint=msg.get("leader", msg.get("candidate")))
        if mtype == "RequestVote":
            self._on_request_vote(src, msg, net)
        elif mtype == "RequestVoteRes":
            self._on_request_vote_res(src, msg, net)
        elif mtype == "AppendEntries":
            self._on_append_entries(src, msg, net)
        elif mtype == "AppendEntriesRes":
            self._on_append_entries_res(src, msg, net)

    def _on_request_vote(self, src: int, msg: dict, net):
        term = msg["term"]
        cand = msg["candidate"]
        if term < self.current_term:
            net.send(self.id, src, {"type": "RequestVoteRes",
                                    "term": self.current_term, "granted": False,
                                    "voter": self.id})
            return
        # R1 vote rule (§5.4.1)
        if self.enable_vote_rule:
            if not is_up_to_date(msg["last_term"], msg["last_idx"],
                                 self.last_term(), self.last_index()):
                net.send(self.id, src, {"type": "RequestVoteRes",
                                        "term": self.current_term, "granted": False,
                                        "voter": self.id})
                return
        if self.voted_for is not None and self.voted_for != cand:
            net.send(self.id, src, {"type": "RequestVoteRes",
                                    "term": self.current_term, "granted": False,
                                    "voter": self.id})
            return
        self.voted_for = cand
        # grant resets election timer (prevents candidate's own timeout churn)
        self._reset_election_timer(net)
        net.send(self.id, src, {"type": "RequestVoteRes",
                                "term": self.current_term, "granted": True,
                                "voter": self.id})

    def _on_request_vote_res(self, src: int, msg: dict, net):
        if self.role != CANDIDATE:
            return
        if msg["term"] < self.current_term:
            return
        if msg["term"] > self.current_term:
            return  # already stepped down
        if msg.get("granted"):
            self._votes.add(msg.get("voter", src))
            if len(self._votes) >= majority(self.n):
                self._become_leader(net)

    def _on_append_entries(self, src: int, msg: dict, net):
        term = msg["term"]
        if term < self.current_term:
            net.send(self.id, src, {"type": "AppendEntriesRes",
                                    "term": self.current_term, "ok": False,
                                    "follower": self.id,
                                    "match": self.last_index()})
            return
        # legitimate leader (term >= ours): step down + remember leader
        if self.role != FOLLOWER or self.leader_hint != msg.get("leader"):
            self.role = FOLLOWER
            self.leader_hint = msg.get("leader", src)
            self._votes = set()
        self._reset_election_timer(net)
        prev_idx = msg["prev_idx"]
        prev_term = msg["prev_term"]
        # consistency check (§5.3)
        if prev_idx > 0:
            if len(self.log) < prev_idx or self.log[prev_idx - 1][0] != prev_term:
                # optimization payload: conflict term + first index
                cterm = self.log[prev_idx - 1][0] if len(self.log) >= prev_idx else -1
                net.send(self.id, src, {"type": "AppendEntriesRes",
                                        "term": self.current_term, "ok": False,
                                        "follower": self.id,
                                        "match": self.last_index(),
                                        "conflict_term": cterm})
                return
        # truncate conflicting tail + append new
        new_entries = msg["entries"]
        idx = prev_idx
        for (et, ec) in new_entries:
            idx += 1
            if len(self.log) >= idx:
                if self.log[idx - 1][0] != et:
                    # follower holds uncommitted conflict -> overwrite (§5.3)
                    # never touches committed prefix (leader completeness)
                    del self.log[idx - 1:]
                    self.log.append((et, ec))
                # else identical: skip (idempotent)
            else:
                self.log.append((et, ec))
        # commit advance (never beyond own last index)
        leader_commit = msg["commit"]
        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, len(self.log))
            self._apply_committed()
        net.send(self.id, src, {"type": "AppendEntriesRes",
                                "term": self.current_term, "ok": True,
                                "follower": self.id,
                                "match": prev_idx + len(new_entries)})

    def _on_append_entries_res(self, src: int, msg: dict, net):
        if self.role != LEADER:
            return
        if msg["term"] < self.current_term:
            return
        # (higher term already handled by step-down)
        if msg.get("ok"):
            m = msg.get("match", 0)
            self.match_index[src] = max(self.match_index.get(src, 0), m)
            self.next_index[src] = self.match_index[src] + 1
            old_commit = self.commit_index
            self._advance_commit()
            # if commit moved, followers learn on next heartbeat; push now
            if self.commit_index != old_commit:
                self._send_heartbeats(net)
        else:
            nxt = self.next_index.get(src, self.last_index() + 1)
            self.next_index[src] = max(1, nxt - 1)
            self._send_to(net, src)
