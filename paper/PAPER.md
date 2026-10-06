# Raft, Reproduced and Measured: From Understandability to Evidence

**Abstract.** Raft (Ongaro & Ousterhout 2014) made consensus teachable by decomposing it into leader election, log replication, and safety, and by strengthening leadership to reduce states. We reproduce the full §5 protocol from scratch in dependency-free Python, twice — once on a deterministic simulated network (seeded, replayable) and once on real TCP sockets with the same server class unchanged — and we measure what the paper claims: failover latency, split-vote resolution vs. timeout jitter, single-RTT commits, partition safety, and the two §5.4 safety rules. Over 100 chaos runs (7,982 kills, 39,501 writes, 5% loss, partitions) zero safety violations occur; ablating the vote rule breaks state-machine safety within milliseconds, while ablating the commit rule breaks 0/100 random runs — replicating the video's 0/1000 and demonstrating that sampling proves presence, never absence, of bugs. We report seven hidden patterns (timeout width governs tails; slowest minority is latency-invisible; dual leadership is safe; vote bugs are findable, commit bugs provable; match-index overcounting; odd-size optimality; sim↔live agreement within 50ms), each with a falsifiable experiment. All artefacts are Docker-reproducible.

## 1 Introduction
Consensus lets a cluster act as one reliable state machine despite crashes, loss, and partitions. Paxos dominated teaching and practice but resisted understanding; Raft's bet is that decomposition + stronger leadership + jittered timeouts buys both clarity and correctness. We test that bet by rebuilding Raft exactly as specified (Fig.2) and attacking it.

## 2 Background: replicated state machines
`apply` + `replay`: identical logs in identical order ⇒ identical stores. Counterexample (order flip changes x 5→1) shows consensus reduces to agreeing on one ordered list. Quorum intersection (any two 3/5 share ≥1; 45 pairs checked) is the combinatorial fact every later guarantee rests on.

## 3 Related work
Paxos lineage (Lamport; Lampson ABCD; Mazieres practical;/etcd, Chubby, ZooKeeper/Zab, Spanner); understandability studies (Raft user study: 33/43 score higher than Paxos); equivalence analyses (Howard & Mortier: difference is leader-election deal); optimisation porting (Wang et al.: Mencius/quorum-lease to Raft); formal models (TLA+ 400 lines + mechanised proof; LNT/mCRL2 reproductions that fixed spec issues); production Raft (etcd, Consul, CockroachDB, KRaft; HashiCorp divergences: async heartbeats, vote-rejection-with-leader, pre-vote, leadership transfer); measurement (Saxena tails; BALLAST adaptivity); bug-finding (Antithesis: every implementation buggy at the spec→code boundary); pedagogy (MIT 6.824, 30+ courses; RaftScope, Secret Lives of Data); from-scratch builds (Gupta 2026; miniraft/Jepsen-Maelstrom).

## 4 Method: two networks, one server class
SimNet: heap event queue, 5–15ms legs, drop/partition/kill hooks, seeded RNG. RealNet: length-prefixed JSON/TCP, 5 threads, real clock. Server implements Fig.2 literally: persistent (term, votedFor, log), volatile (commit, applied), leader (next/match), R1 up-to-date voting, R2 own-term commit counting, decrement-and-retry repair, term-driven step-down. Invariants P1 (≤1 leader/term) + P2 (≤1 cmd/index) checked on every monkey tick; violation aborts the run.

## 5 Experiments
E1 overlap combinatorics. E2 failover (~196ms sim, ~240ms live) + minority stall (no leader 5s) + jitter sweep (table §H1; Fig.16 replay). E3 commit latency (19–21ms = 1 RTT; straggler-immune; 14ms catch-up). E4 partition (2|3 dual leaders; majority commits 3; heal converges ~10ms sim; uncommitted minority suffix dropped — safe, never acked). E5 ablation (R1-OFF ⇒ instant P2 violation; R2-OFF ⇒ 0/100 break). E6 chaos (100×10s, §6.6). E7 live TCP (same class, wall-clock agreement).

## 6 Hidden patterns H1–H7
See analysis/HIDDEN_PATTERNS.md (each: claim, numbers, seed, artefact, design rule, follow-up paper sketch). Novel observations: tail-vs-median split by jitter width; quorum masking quantified; match-index overcounting trap (found by chaos, fixed `match = prev_idx + len(entries)`); minority term-churn as partition signal.

## 7 Discussion: what testing cannot do
The commit rule needs Fig.8's exact crash interleaving; 1,000 random runs miss it. Formal specification (TLA+) + proof carries that case; testing carries the rest. We therefore pair every falsification result with its proof pointer, and label coverage explicitly (sim kinder than WAN; i.i.d. loss; no Byzantine/disk faults).

## 8 Extensions (PhD roadmap)
Snapshotting §7 (bounded log + InstallSnapshot Rule 7 — the Antithesis loop); joint-consensus membership §6; pre-vote + leadership transfer (HashiCorp); read-index/leases §8; adaptive timeouts (BALLAST) using H1 as baseline; WAN + bursty-loss + disk-fault injection; TLA+ model-check of this exact code's state machine.

## 9 Conclusion
Raft survives contact with dice: understandable to build, measurable to tune, breakable in exactly the ways the paper says, and only in those ways under 8k kills. The reproduction is complete, the numbers match the paper's shapes, and the next questions are labelled.

## References
[Full 39-entry bibliography in README §11 + raft.github.io canon; key: Ongaro & Ousterhout 2014; Ongaro diss. 2014; Howard & Mortier 2020; Wang et al. 2019; Evrard 2020; Bora et al. 2024; Afifi et al. 2025; Gupta 2026; Antithesis 2026; Saxena 2025; Wang BALLAST 2025; HashiCorp raft docs; etcd/Jepsen analyses; Docker reproducibility 2026 (pinned-image + zero-dep methodology).]
