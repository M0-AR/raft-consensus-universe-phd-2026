"""EXP-01 overlap: any two majorities of 5 share >=1 server.

10 ways to pick 3 of 5 -> 45 pairs. Smallest overlap is 1.
With groups of 2, 15 of 45 pairs share nobody -> unsafe.
Verifies §2 / Part two of the video on live combinatorics.
"""
import itertools
import json


def main():
    servers = list(range(5))
    triples = list(itertools.combinations(servers, 3))
    assert len(triples) == 10
    min_overlap = 5
    for a, b in itertools.combinations(triples, 2):
        ov = len(set(a) & set(b))
        min_overlap = min(min_overlap, ov)
        assert ov >= 1, f"majorities {a},{b} disjoint!"
    pairs = len(list(itertools.combinations(triples, 2)))
    assert pairs == 45
    # groups of 2 are unsafe
    pairs2 = list(itertools.combinations(servers, 2))
    bad = sum(1 for a, b in itertools.combinations(pairs2, 2)
              if not (set(a) & set(b)))
    # quorum table
    table = {n: (n // 2 + 1, n - (n // 2 + 1)) for n in (3, 5, 7)}
    out = {"n_triples": 10, "n_pairs": 45, "min_overlap": min_overlap,
           "pairs_of_2_disjoint": bad, "quorum_table": table}
    print(json.dumps(out, indent=2))
    print("EXP-01 OK: every two majorities intersect; pairs-of-2 do not.")
    return out


if __name__ == "__main__":
    main()
