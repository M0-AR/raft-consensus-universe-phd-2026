#!/usr/bin/env python3
"""Run all experiments end-to-end (quick or full). Verifies, never hand-edits.

Usage: python3 scripts/run_all.py [--quick]
  quick: 20-run chaos sample (CI-friendly)
  full : 100-run chaos + live-socket check (needs ports)
"""
import argparse
import subprocess
import sys

CMDS_QUICK = [
    ["python3", "experiments/exp_overlap.py"],
    ["python3", "experiments/exp_replication.py"],
    ["python3", "experiments/exp_partition.py"],
    ["python3", "experiments/exp_safety.py"],
    ["python3", "experiments/exp_election.py"],
    ["python3", "experiments/exp_chaos_1000.py", "--runs", "20", "--secs", "5"],
]
CMDS_FULL = [
    ["python3", "experiments/exp_overlap.py"],
    ["python3", "experiments/exp_replication.py"],
    ["python3", "experiments/exp_partition.py"],
    ["python3", "experiments/exp_safety.py"],
    ["python3", "experiments/exp_election.py"],
    ["python3", "experiments/exp_chaos_1000.py", "--runs", "100", "--secs", "10"],
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    cmds = CMDS_QUICK if a.quick else CMDS_FULL
    for c in cmds:
        print(f"\n### {' '.join(c)}")
        r = subprocess.run(c)
        if r.returncode != 0:
            print(f"FAILED: {' '.join(c)}")
            sys.exit(1)
    print("\nALL EXPERIMENTS PASSED")


if __name__ == "__main__":
    main()
