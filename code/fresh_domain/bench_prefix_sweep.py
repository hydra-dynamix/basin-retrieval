"""Prefix-length sweep on the fresh-domain corpus.

The main bench showed ~1.5x compression at half-length prefixes. This sweeps
prefix fractions from 0.3 to 1.0 to show the full compression/inclusion curve.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import fmean

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bench_fresh_domain import build_corpus, CodeInstance, Instance
from relaxation import RelaxationIndex

REPO_ROOTS = [
    Path("/home/bakobi/repos/bako/research/delta-top"),
    Path("/home/bakobi/repos/bako/research/rica"),
    Path("/home/bakobi/repos/bako/research/tdm"),
    Path("/home/bakobi/repos/bako/research/magi"),
]
REPO_ROOTS = [r for r in REPO_ROOTS if r.exists()]


def split_corpus(instances: list):
    from collections import defaultdict
    by_family: dict[str, list] = defaultdict(list)
    for inst in instances:
        by_family[inst.family].append(inst)
    index_insts: list = []
    query_insts: list = []
    for fam, members in by_family.items():
        ms = sorted(members, key=lambda x: x.focal_node())
        split = max(1, len(ms) // 2)
        index_insts.extend(ms[:split])
        query_insts.extend(ms[split:])
    return index_insts, query_insts


def sweep_prefix(index_insts, query_insts, variant, fractions):
    idx = RelaxationIndex(variant=variant)
    idx.add_all([Instance(family=ci.family, labels=(ci._focal,), walk=ci.walk) for ci in index_insts])
    store_size = len(index_insts)
    out = []
    for frac in fractions:
        results = []
        for q in query_insts:
            prefix_len = max(2, int(len(q.walk) * frac))
            prefix_len = min(prefix_len, len(q.walk))
            state = idx.relax(q.walk, length=prefix_len)
            fam_in = q.family in dict(state.family_counts)
            results.append({
                "basin": state.n_active,
                "inclusion": 1.0 if fam_in else 0.0,
                "nonempty": 1.0 if state.n_active > 0 else 0.0,
            })
        basins = [r["basin"] for r in results]
        nonempty = [r for r in results if r["basin"] > 0]
        comps = [store_size / r["basin"] for r in nonempty] if nonempty else [0.0]
        geo = math.exp(fmean(math.log(c) for c in comps)) if comps else 0
        out.append({
            "prefix_fraction": frac,
            "mean_basin": round(fmean(basins), 2),
            "geomean_compression": round(geo, 2),
            "inclusion": round(fmean(r["inclusion"] for r in results), 4),
            "coverage": round(fmean(r["nonempty"] for r in results), 4),
        })
    return out


def main():
    corpus = build_corpus(REPO_ROOTS)
    print(f"corpus: {len(corpus)} walks")
    index_insts, query_insts = split_corpus(corpus)
    print(f"index={len(index_insts)}  queries={len(query_insts)}")
    print()

    fractions = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    print("PREFIX-LENGTH SWEEP")
    print(f"{'variant':12s} {'frac':>5s} {'basin':>8s} {'comp':>8s} {'incl':>7s} {'cov':>7s}")
    print("-" * 55)
    all_results = {}
    for variant in ("labelfree", "typed"):
        sweep = sweep_prefix(index_insts, query_insts, variant, fractions)
        all_results[variant] = sweep
        for row in sweep:
            print(f"{variant:12s} {row['prefix_fraction']:5.1f} {row['mean_basin']:8.1f} "
                  f"{row['geomean_compression']:7.1f}x {row['inclusion']:7.3f} {row['coverage']:7.3f}")
        print()

    out = {
        "experiment": "fresh-domain-prefix-sweep",
        "corpus_size": len(corpus),
        "n_index": len(index_insts),
        "n_queries": len(query_insts),
        "sweep": all_results,
    }
    (_HERE / "fresh_domain_prefix_sweep.json").write_text(json.dumps(out, indent=2))
    print("wrote fresh_domain_prefix_sweep.json")


if __name__ == "__main__":
    main()
