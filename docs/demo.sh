#!/usr/bin/env bash
# Record a 60-second terminal demo for the README + preview.html.
# Best practice 2026: asciinema (interactive) -> agg (GIF) -> <video> + GIF fallback.
#
#   1) asciinema rec docs/demo.cast --command "bash docs/demo.sh play"
#   2) agg docs/demo.cast docs/demo.gif          # needs: cargo install agg  (or docker)
#   3) agg docs/demo.cast docs/demo.mp4 --format mp4
#   4) Commit demo.cast + demo.gif + demo.mp4, reference from README.
set -euo pipefail
cd "$(dirname "$0")/.."

play() {
  echo "=== 1/5 overlap (quorum math) ==="
  python3 experiments/exp_overlap.py
  sleep 1
  echo ""
  echo "=== 2/5 replication (1 RTT commits) ==="
  python3 experiments/exp_replication.py
  sleep 1
  echo ""
  echo "=== 3/5 partition (dual leaders are safe) ==="
  python3 experiments/exp_partition.py
  sleep 1
  echo ""
  echo "=== 4/5 safety ablation (vote rule OFF breaks instantly) ==="
  python3 experiments/exp_safety.py
  sleep 1
  echo ""
  echo "=== 5/5 chaos sample (20 runs, zero broken) ==="
  python3 experiments/exp_chaos_1000.py --runs 2 --secs 5
  echo ""
  echo "Done. Full suite: python3 scripts/run_all.py --quick"
}

if [ "${1:-}" = "play" ]; then play; else
  echo "Usage:"
  echo "  bash docs/demo.sh play                       # play the demo"
  echo "  asciinema rec docs/demo.cast --command 'bash docs/demo.sh play'"
  echo "  agg docs/demo.cast docs/demo.gif"
  echo "  agg docs/demo.cast docs/demo.mp4 --format mp4"
fi
