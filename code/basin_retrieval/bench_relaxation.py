"""Full basin-stability + polysemy suite for the unlabeled-basin-relaxation branch.

Implements build-shape steps 2-5:
  2. perturbation stability test  (drop + corrupt modes)
  3. prefix-shared divergent families (from generator)
  4. polysemy disambiguation metric
  5. basin depth / phase-transition report

Held-out retrieval: index built on instances 0..k-2 of each family; instance k-1
is the held-out symbolically-novel query (port of the topology program's design).

Two variants indexed in parallel:
  typed     : edge labels kept (SUPPORTS/WEAKENS/...)
  labelfree : edge labels collapsed (pure topology, phase-8 question)

Headline metric shift (per branch thesis): NOT "did retrieval include the right
family" but "how much evidence can be removed/corrupted before the basin changes."
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from generator import build_generated_graph_with_polysemy
from relaxation import RelaxationIndex

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# No thresholds. This suite measures and reports. No gate, no verdict.


@dataclass
class FamilyResult:
    family: str
    variant: str
    walk_len: int
    full_dominant: str | None
    inclusion: bool                  # true family in active set at full evidence
    bundle_size_full: int
    bundle_reduction: float
    stability_drop_all: float        # all droppable steps (incl. trailing artifact)
    stability_drop_interior: float   # EXCLUDES trailing step (the real basin-depth signal)
    stability_corrupt: float         # frac of interior corruptions where dominant survives
    basin_depth_drop: int            # max contiguous surviving drops from the end (interior)
    per_step_drop: list[dict] = field(default_factory=list)


def corrupt_step(walk, index, alt_label=("CORRUPTED", "out")):
    """Return walk with step `index`'s edge label replaced by a bogus label.

    Root (index 0) is not corruptible. Corrupting tests prefix-survival up to the
    corruption point: everything before still matches; from the corrupt step the
    canonical signature diverges. So the instance survives at the PRE-corruption
    prefix length, which is a real (if limited) form of basin depth.
    """
    if index == 0:
        return None
    node, _et, _dir = walk[index]
    corrupted = list(walk)
    corrupted[index] = (node, alt_label[0], alt_label[1])
    return corrupted


def run_family(idx: RelaxationIndex, inst, family: str, variant: str) -> FamilyResult:
    walk = inst.walk
    full = idx.relax(walk)
    inclusion = family in dict(full.family_counts)
    n_indexed = len(idx.instances)
    bundle_red = (n_indexed / full.n_active) if full.n_active else 0.0

    # drop perturbation
    stab = idx.basin_stability(walk)
    per_step = stab["per_step"]
    # The trailing step (last droppable index) trivially survives because
    # "drop last step" == "compare prefix of length n-1". It is an artifact, not
    # basin depth. Report both: _all (includes it) and _interior (excludes it,
    # the honest basin-depth signal).
    interior = [r for r in per_step if r["dropped_step"] < len(walk) - 1]
    stability_drop_all = stab["stability_rate"]
    stability_drop_interior = (
        sum(r["survived"] for r in interior) / len(interior) if interior else 0.0
    )

    # corrupt perturbation
    n_corrupt_survived = 0
    n_corrupt_total = 0
    for i in range(1, len(walk) - 1):  # exclude trailing; interior corruptions only
        n_corrupt_total += 1
        cw = corrupt_step(walk, i)
        if cw is None:
            continue
        # after corruption, the instance can only match up to step i-1 (pre-corrupt prefix).
        # "survives" = true family still dominates at evidence length i-1.
        st = idx.relax(cw, length=i)  # only the pre-corruption prefix is trustworthy
        if st.dominant_family == family:
            n_corrupt_survived += 1
    stability_corrupt = n_corrupt_survived / n_corrupt_total if n_corrupt_total else 0.0

    # basin depth (drop, interior) = longest run of consecutive surviving drops from the end
    survived_flags_interior = [r["survived"] for r in interior]
    depth = 0
    for f in reversed(survived_flags_interior):
        if f:
            depth += 1
        else:
            break

    return FamilyResult(
        family=family, variant=variant, walk_len=len(walk),
        full_dominant=full.dominant_family, inclusion=inclusion,
        bundle_size_full=full.n_active, bundle_reduction=round(bundle_red, 4),
        stability_drop_all=round(stability_drop_all, 4),
        stability_drop_interior=round(stability_drop_interior, 4),
        stability_corrupt=round(stability_corrupt, 4),
        basin_depth_drop=depth, per_step_drop=per_step,
    )


@dataclass
class PolysemyResult:
    pair_id: int
    family_a: str
    family_b: str
    share_k: int
    both_active_on_shared: bool
    correct_dominates_after_one: bool
    ambiguity_retained_on_missing: bool  # >=2 active on shared prefix
    active_on_shared: int
    families_on_shared: int


def run_polysemy(idx, pair_meta, instances_by_family, pair_id: int) -> PolysemyResult:
    fa, fb, share_k = pair_meta
    inst_a = instances_by_family[fa][-1]  # held-out instance as the evidence
    walk_a = inst_a.walk
    st_shared = idx.relax(walk_a, length=share_k)
    counts = dict(st_shared.family_counts)
    both_active = fa in counts and fb in counts
    ambiguity = st_shared.n_distinct_families >= 2
    # +1 disambiguating step
    st_plus1 = idx.relax(walk_a, length=min(share_k + 1, len(walk_a)))
    correct_dom = st_plus1.dominant_family == fa
    return PolysemyResult(
        pair_id=pair_id, family_a=fa, family_b=fb, share_k=share_k,
        both_active_on_shared=both_active, correct_dominates_after_one=correct_dom,
        ambiguity_retained_on_missing=ambiguity,
        active_on_shared=st_shared.n_active,
        families_on_shared=st_shared.n_distinct_families,
    )


def aggregate(family_results: list[FamilyResult]) -> dict:
    def mean(xs): return round(statistics.fmean(xs), 4) if xs else 0.0
    return {
        "n_instances": len(family_results),
        "inclusion_rate": mean([float(r.inclusion) for r in family_results]),
        "bundle_reduction_gmean": mean([r.bundle_reduction for r in family_results]),
        "stability_drop_all_mean": mean([r.stability_drop_all for r in family_results]),
        "stability_drop_interior_mean": mean([r.stability_drop_interior for r in family_results]),
        "stability_corrupt_mean": mean([r.stability_corrupt for r in family_results]),
        "basin_depth_drop_mean": mean([float(r.basin_depth_drop) for r in family_results]),
        "basin_depth_drop_max": max((r.basin_depth_drop for r in family_results), default=0),
    }


# gate evaluation removed; this suite reports measurements only


def main():
    print("building data...")
    g, disjoint_skel, all_instances, polysemy_meta, _ = build_generated_graph_with_polysemy(
        n_disjoint_families=20, n_polysemy_bases=10, instances_per=3, seed=20260706,
    )
    n_disjoint = len(disjoint_skel)
    print(f"  disjoint families: {n_disjoint}, polysemy pairs: {len(polysemy_meta)}")

    # held-out: index instances 0,1; query instance 2
    results_by_variant: dict[str, list[FamilyResult]] = {}
    for variant in ("typed", "labelfree"):
        idx = RelaxationIndex(variant=variant)
        for family, insts in all_instances.items():
            for inst in insts[:-1]:  # train instances
                idx.add(inst)
        fam_results = []
        for family, insts in all_instances.items():
            if not family.startswith("gen_"):
                continue  # only disjoint families for the basin-stability metric
            held_out = insts[-1]
            fam_results.append(run_family(idx, held_out, family, variant))
        results_by_variant[variant] = fam_results

    # polysemy (typed only for headline; labelfree reported too)
    poly_by_variant = {}
    for variant in ("typed", "labelfree"):
        idx = RelaxationIndex(variant=variant)
        for family, insts in all_instances.items():
            for inst in insts[:-1]:
                idx.add(inst)
        pr = [run_polysemy(idx, pm, all_instances, i) for i, pm in enumerate(polysemy_meta)]
        poly_by_variant[variant] = pr

    agg_typed = aggregate(results_by_variant["typed"])
    agg_lf = aggregate(results_by_variant["labelfree"])

    # ---- results.json ----
    results = {
        "experiment": "basin-stability-and-polysemy",
        "branch": "unlabeled-basin-relaxation",
        "relaxation_rule": "discrete prefix-consistency pruning (elimination, not graded settling)",
        "aggregate": {"typed": agg_typed, "labelfree": agg_lf},
        "polysemy": {
            "typed": [asdict(p) for p in poly_by_variant["typed"]],
            "labelfree": [asdict(p) for p in poly_by_variant["labelfree"]],
        },
        "n_disjoint_families": n_disjoint,
        "n_polysemy_pairs": len(polysemy_meta),
        "family_results_typed": [asdict(r) for r in results_by_variant["typed"]],
    }
    write_json("basin_results.json", results)

    # ---- comparison.md ----
    md = render(agg_typed, agg_lf, poly_by_variant, n_disjoint, len(polysemy_meta))
    with open(os.path.join(OUT_DIR, "basin_comparison.md"), "w") as f:
        f.write(md)

    # ---- run_summary.json ----
    summary = {
        "changed": ["experiments/motif-topology-retrieval/relaxation.py",
                    "experiments/motif-topology-retrieval/generator.py (polysemy pairs)",
                    "experiments/motif-topology-retrieval/bench_relaxation.py"],
        "commands": ["python3 experiments/motif-topology-retrieval/bench_relaxation.py"],
        "metrics": {"typed": agg_typed, "labelfree": agg_lf},
        "artifacts": ["experiments/motif-topology-retrieval/basin_results.json",
                      "experiments/motif-topology-retrieval/basin_comparison.md"],
    }
    write_json("basin_run_summary.json", summary)

    print("\n" + "=" * 70)
    print("RESULTS (no gate, no verdict)")
    print("=" * 70)
    print(json.dumps({"typed": agg_typed, "labelfree": agg_lf}, indent=2))


def render(agg_t, agg_lf, poly_by_v, n_disj, n_poly) -> str:
    pt = poly_by_v["typed"]
    plf = poly_by_v["labelfree"]
    both_t = statistics.fmean([float(p.both_active_on_shared) for p in pt]) if pt else 0.0
    disamb_t = statistics.fmean([float(p.correct_dominates_after_one) for p in pt]) if pt else 0.0
    ambig_t = statistics.fmean([float(p.ambiguity_retained_on_missing) for p in pt]) if pt else 0.0
    both_lf = statistics.fmean([float(p.both_active_on_shared) for p in plf]) if plf else 0.0
    disamb_lf = statistics.fmean([float(p.correct_dominates_after_one) for p in plf]) if plf else 0.0
    ambig_lf = statistics.fmean([float(p.ambiguity_retained_on_missing) for p in plf]) if plf else 0.0
    rows = ["| metric | typed | labelfree |",
            "|---|---|---|",
            f"| inclusion_rate | {agg_t['inclusion_rate']} | {agg_lf['inclusion_rate']} |",
            f"| bundle_reduction | {agg_t['bundle_reduction_gmean']} | {agg_lf['bundle_reduction_gmean']} |",
            f"| stability_drop_all (incl trailing) | {agg_t['stability_drop_all_mean']} | {agg_lf['stability_drop_all_mean']} |",
            f"| stability_drop_interior | {agg_t['stability_drop_interior_mean']} | {agg_lf['stability_drop_interior_mean']} |",
            f"| stability_corrupt | {agg_t['stability_corrupt_mean']} | {agg_lf['stability_corrupt_mean']} |",
            f"| basin_depth_drop_interior (max) | {agg_t['basin_depth_drop_max']} | {agg_lf['basin_depth_drop_max']} |",
            f"| polysemy both_active | {round(both_t,3)} | {round(both_lf,3)} |",
            f"| polysemy disambiguation | {round(disamb_t,3)} | {round(disamb_lf,3)} |",
            f"| polysemy ambiguity_retention | {round(ambig_t,3)} | {round(ambig_lf,3)} |"]
    return f"""# Basin stability and polysemy suite (measurement only)

No gate, no thresholds, no verdict. Numbers only.

Setup: {n_disj} disjoint generated families + {n_poly} prefix-shared polysemy
pairs, 3 instances each. Index on instances 0,1; held-out query = instance 2
(symbolically novel). Two variants: typed (edge labels kept) and labelfree
(edge labels collapsed).

Relaxation rule: discrete prefix-consistency pruning.

## Metrics

{chr(10).join(rows)}

## Raw per-family and per-pair measurements

See `basin_results.json`.
"""


def write_json(name, obj):
    with open(os.path.join(OUT_DIR, name), "w") as f:
        json.dump(obj, f, indent=2)


if __name__ == "__main__":
    main()
