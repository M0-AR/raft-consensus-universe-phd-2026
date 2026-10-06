# Hidden patterns found by measurement (not by reading)

All numbers below are produced by `scripts/run_all.py` on deterministic
seeds. Re-run to verify; do not trust prose without `results/*.json`.

## H1. Randomness width controls the tail, not the median
`results/exp_election.csv` (200 trials per range, 5 nodes, 5–15ms legs):

| range | stuck | median | worst |
|---|---|---|---|
|150–150|200/200|—|—|
|150–155|22/200|1778ms|8555ms|
|150–175|0/200|334ms|1135ms|
|150–200|0/200|191ms|712ms|
|150–300|0/200|206ms|516ms|

Pattern: zero randomness never converges (split-vote lockstep). 5ms of
jitter fixes liveness but leaves a catastrophic tail. Widening to 150ms
cuts worst-case 16× while median barely moves. **Design rule: size the
timeout range for the tail you can afford, not the median you want.**
Matches Ongaro Fig.16 (their worst 513ms @50ms jitter; ours 516ms @150ms
jitter — same shape, shifted by sim latency).

## H2. Commit latency is one RTT to the majority, immune to the slowest minority
EXP-03: 19.6 / 19.7 / 21.4ms for 3 sequential writes (legs 5–15ms ⇒
1 RTT ≈ 10–30ms). Killing 1 of 5 changes nothing (24.9ms). Catch-up after
restart is 13.8ms. **The 4th and 5th servers are latency-irrelevant.**
This is why etcd/Consul stay fast with a straggler — and why adding nodes
(5→7) buys fault tolerance at the cost of waiting for 4 instead of 3.

## H3. Two leaders can coexist — safety does not require single leadership
EXP-04 partitions {2}|{3}: old leader keeps writing (2 copies, never
committed), new leader commits 3 writes. Heal → old sees higher term,
steps down, drops uncommitted suffix, converges in ~10ms sim (≈61ms in
the video on different latency). **No promise broken because the client
was never acked.** Teaching point: Raft safety is about *committed*
entries, not about preventing dual leadership.

## H4. The vote rule is load-bearing; the commit rule is proof-bearing
Ablation (EXP-05): vote rule OFF → stale empty-log server elected,
overwrites index 1, P2 violation instantly (wall <10ms; video: 200/200,
fastest 402ms, median 2.2s). Commit rule OFF → 0/1000 random runs break
(video: same). **Random testing finds the vote bug always and the commit
bug never** — the failure needs an exact crash sequence (Fig.8 of the
paper: old entry on 3/5 overwritten by a newer-entry holder that never
saw it). Lesson: chaos proves presence of bugs, never absence; the TLA+
proof (400 lines, §9.2) carries what sampling cannot.

## H5. Match-index overcounting: a one-line correctness trap
During this study the implementation initially replied
`match = len(follower log)` on AppendEntries success. A longer follower
then inflated the leader's match to 179 while the leader held 142 —
commit counting on phantom replicas. Fix: `match = prev_idx +
len(entries)` (leader's perspective). Found by chaos (non-convergence),
not by review. Matches Antithesis 2026 finding: every production Raft
they tested had a bug at the spec→code boundary, despite mechanized
proofs of the model.

## H6. Quorum math predicts ops capacity
3 needs 2 (lose 1) · 5 needs 3 (lose 2) · 7 needs 4 (lose 3). 4 nodes need
3 — no better than 3 nodes. **Always use odd sizes.** Minority (2/5)
elections spin the term (28 in 5s in the video) but elect nothing — by
design: a minority cannot tell death from partition, so it does nothing
rather than risk split-brain.

## H7. Live sockets agree with simulation (real-life verification)
EXP-07 runs the *same* `Server` class on TCP loopback (5 threads, real
clock): leader ~150ms, failover ~240ms, 5 stores identical. Sim said
~190ms / ~196ms. Same order, shifted by real stack latency. **Simulation
is faithful for safety; wall-clock adds ~20–50ms of transport noise.**
`docker compose --profile live up` reproduces this anywhere.
