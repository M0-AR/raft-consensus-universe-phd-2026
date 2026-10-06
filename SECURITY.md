# Security policy

This is a teaching and benchmarking implementation of Raft, not a production store. Do not put real user data behind it.

## Reporting a vulnerability

Open a GitHub issue with `[security]` in the title and include:

- What invariant breaks (`P1` election safety or `P2` state-machine safety).
- The seed and commands to reproduce (`experiments/exp_chaos_1000.py --runs 1 --secs 5` style).
- Whether the break needs the vote rule or commit rule disabled.

We will respond with a reproducing seed or a fix, plus a regression experiment.
