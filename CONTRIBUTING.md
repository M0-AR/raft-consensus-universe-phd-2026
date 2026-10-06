# Contributing

Thanks for stopping by. This repo is intentionally small so contributions stay reviewable.

## Quick rules

1. One change per pull request.
2. Every behavior change ships with a seed-pinned experiment in `experiments/` and an entry in `results/`.
3. Run before you push:

```bash
python3 -m pytest tests/ -q
python3 scripts/run_all.py --quick
```

4. Determinism is a feature: no wall-clock, no unseeded randomness in `src/raft/`. Live timing lives only in `experiments/exp_live.py`.

## What makes a good PR here

- A new falsifiable experiment (hypothesis → seed → expected `results/*.json`).
- A clearer diagram or beginner-guide paragraph with a concrete example.
- A faster sim without changing observable message order.

## Reporting issues

Include: seed, command, `results/*.json` diff, and the smallest failing run (`--runs 1 --secs 5` first).
