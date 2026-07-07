"""Payload graph projection refinement.

Question:
  Can semantic/content connections stored inside a keyed recurrence motif be
  projected as a payload graph and used to refine a broad retrieved bundle?

Architecture under test:

    label-free recurrence motif key
      -> broad bundle retrieval
      -> project semantic/content payload graph stored inside each motif
      -> refine using target payload graph topology/relations

Memory content: LDGR historical findings (same source as behavioral relevance).

Important control:
  For each real memory item, create a rewired decoy with the SAME payload nodes
  and SAME relation-label multiset, but different edges. Node-bag/token overlap
  and relation-topology-only cannot distinguish original from decoy. Exact
  content-graph connections can. This directly tests whether the semantic
  connections inside the motif are doing work beyond flat overlap.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE = _HERE.parent / "core"
_BEHAV = _HERE.parent / "behavioral_relevance"
for _p in (str(_CORE), str(_BEHAV)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bench_behavioral_relevance import MemoryItem, build_corpus

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE

SCORERS = ("coarse_only", "node_bag", "relation_topology", "content_graph")
QUERY_MODES = ("core", "partial", "noisy", "topic_mechanism")


@dataclass(frozen=True)
class PayloadGraph:
    family: str
    source: str
    is_decoy: bool
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str, str], ...]  # src, relation, dst


# ---------------------------------------------------------------------------
# graph projection from motif payload data
# ---------------------------------------------------------------------------

def first_node(item: MemoryItem, prefix: str) -> str:
    for node, _et, _dir in item.walk:
        if str(node).startswith(prefix):
            return node
    return f"{prefix}absent"


def all_nodes(item: MemoryItem, prefix: str) -> list[str]:
    out, seen = [], set()
    for node, _et, _dir in item.walk:
        if str(node).startswith(prefix) and node not in seen:
            out.append(node); seen.add(node)
    return out


def payload_graph(item: MemoryItem) -> PayloadGraph:
    """Project semantic/content connections stored inside the motif payload."""
    topic = first_node(item, "topic::")
    mechanism = first_node(item, "mechanism::")
    metric = first_node(item, "metric::")
    kind = first_node(item, "kind::")
    source = first_node(item, "source::")
    boundary = first_node(item, "boundary::")
    terms = all_nodes(item, "term::")
    while len(terms) < 4:
        terms.append(f"term::absent_{len(terms)}")

    edges = [
        (topic, "USES_MECHANISM", mechanism),
        (mechanism, "HAS_METRIC", metric),
        (topic, "HAS_BOUNDARY", boundary),
        (boundary, "EVIDENCED_BY_SOURCE_KIND", kind),
        (source, "SUPPORTS_BOUNDARY", boundary),
        (topic, "MENTIONS_TERM", terms[0]),
        (topic, "MENTIONS_TERM", terms[1]),
        (mechanism, "SUPPORTED_BY_TERM", terms[0]),
        (mechanism, "SUPPORTED_BY_TERM", terms[2]),
        (terms[0], "CO_OCCURS_WITH", terms[1]),
        (terms[1], "CO_OCCURS_WITH", terms[2]),
        (terms[2], "CO_OCCURS_WITH", terms[3]),
        (metric, "QUALIFIES_TERM", terms[3]),
        (kind, "CONTAINS_TERM", terms[0]),
    ]
    nodes = tuple(sorted({n for e in edges for n in (e[0], e[2])}))
    return PayloadGraph(item.family, item.source, False, nodes, tuple(edges))


def rewire_decoy(g: PayloadGraph, rng: random.Random) -> PayloadGraph:
    """Same nodes + same relation multiset, different connections."""
    nodes = list(g.nodes)
    edges = []
    for i, (_src, rel, _dst) in enumerate(g.edges):
        # deterministic-ish rewire: rotate endpoints by different offsets.
        src = nodes[(i + 3) % len(nodes)]
        dst = nodes[(i * 2 + 5) % len(nodes)]
        if src == dst:
            dst = nodes[(i * 2 + 6) % len(nodes)]
        edges.append((src, rel, dst))
    # If by chance any edge survived, perturb it.
    original = set(g.edges)
    fixed = []
    for i, e in enumerate(edges):
        if e in original:
            src, rel, dst = e
            dst = nodes[(nodes.index(dst) + 1) % len(nodes)]
            if src == dst:
                dst = nodes[(nodes.index(dst) + 1) % len(nodes)]
            e = (src, rel, dst)
        fixed.append(e)
    return PayloadGraph(f"decoy_{g.family}", f"decoy_of:{g.source}", True, g.nodes, tuple(fixed))


# ---------------------------------------------------------------------------
# query projection
# ---------------------------------------------------------------------------

def query_edges(g: PayloadGraph, mode: str, rng: random.Random) -> tuple[tuple[str, str, str], ...]:
    if mode == "core":
        keep_rels = {"USES_MECHANISM", "HAS_METRIC", "MENTIONS_TERM", "SUPPORTED_BY_TERM"}
        return tuple(e for e in g.edges if e[1] in keep_rels)[:6]
    if mode == "partial":
        return tuple(rng.sample(list(g.edges), k=min(6, len(g.edges))))
    if mode == "noisy":
        base = list(rng.sample(list(g.edges), k=min(6, len(g.edges))))
        base.append((f"foreign::{rng.randint(0,9999)}", "FOREIGN_RELATION", f"foreign::{rng.randint(0,9999)}"))
        return tuple(base)
    if mode == "topic_mechanism":
        keep_rels = {"USES_MECHANISM", "HAS_BOUNDARY"}
        return tuple(e for e in g.edges if e[1] in keep_rels)
    raise ValueError(mode)


def nodes_of(edges):
    return {n for e in edges for n in (e[0], e[2])}


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def containment(query_counter: Counter, cand_counter: Counter) -> float:
    denom = sum(query_counter.values())
    if denom == 0:
        return 1.0
    hit = sum(min(cand_counter[k], query_counter[k]) for k in query_counter)
    return hit / denom


def score_candidate(candidate: PayloadGraph, q_edges, scorer: str) -> float:
    if scorer == "coarse_only":
        return 1.0
    if scorer == "node_bag":
        q = Counter(nodes_of(q_edges))
        c = Counter(candidate.nodes)
        return containment(q, c)
    if scorer == "relation_topology":
        q = Counter(e[1] for e in q_edges)
        c = Counter(e[1] for e in candidate.edges)
        return containment(q, c)
    if scorer == "content_graph":
        q = Counter(q_edges)
        c = Counter(candidate.edges)
        return containment(q, c)
    raise ValueError(scorer)


def top_bundle(scored, frac=0.9):
    if not scored:
        return []
    top = scored[0]["score"]
    threshold = top * frac
    return [r for r in scored if r["score"] >= threshold] or scored[:1]


def refine(candidates: list[PayloadGraph], target_family: str, q_edges, scorer: str) -> dict:
    scored = []
    for cand in candidates:
        scored.append({"family": cand.family, "source": cand.source, "is_decoy": cand.is_decoy,
                       "score": round(score_candidate(cand, q_edges, scorer), 6)})
    scored.sort(key=lambda r: r["score"], reverse=True)
    top = scored[0]["score"] if scored else None
    top_rows = [r for r in scored if top is not None and abs(r["score"] - top) < 1e-9]
    top_families = {r["family"] for r in top_rows}
    dominant = next(iter(top_families)) if len(top_families) == 1 else None
    bundle = top_bundle(scored)
    target_rank = None
    for i, r in enumerate(scored, start=1):
        if r["family"] == target_family:
            target_rank = i
            break
    return {
        "scorer": scorer,
        "dominant_family": dominant,
        "correct_top1": dominant == target_family,
        "target_in_top_tie": any(r["family"] == target_family for r in top_rows),
        "target_rank": target_rank,
        "top_score": top,
        "top_tie_size": len(top_rows),
        "bundle_size": len(bundle),
        "bundle_reduction": round(len(candidates) / len(bundle), 4) if bundle else 0,
        "top_decoy_rate": sum(r["is_decoy"] for r in top_rows) / len(top_rows) if top_rows else 0.0,
        "ranked_top5": scored[:5],
    }


# ---------------------------------------------------------------------------
# experiment
# ---------------------------------------------------------------------------

def run_pool(real_graphs: list[PayloadGraph], candidates: list[PayloadGraph], pool_name: str, seed=20260706):
    rng = random.Random(seed)
    rows = []
    for g in real_graphs:
        for mode in QUERY_MODES:
            q = query_edges(g, mode, rng)
            for scorer in SCORERS:
                r = refine(candidates, g.family, q, scorer)
                rows.append({"pool": pool_name, "family": g.family, "source": g.source,
                             "mode": mode, "n_query_edges": len(q), **r})
    return rows


def summarize(rows):
    out = {}
    for pool in sorted({r["pool"] for r in rows}):
        out[pool] = {}
        for mode in QUERY_MODES:
            out[pool][mode] = {}
            for scorer in SCORERS:
                xs = [r for r in rows if r["pool"] == pool and r["mode"] == mode and r["scorer"] == scorer]
                out[pool][mode][scorer] = {
                    "n": len(xs),
                    "top1_accuracy": mean([x["correct_top1"] for x in xs]),
                    "target_in_top_tie": mean([x["target_in_top_tie"] for x in xs]),
                    "mean_target_rank": round(statistics.fmean([x["target_rank"] for x in xs]), 4),
                    "mean_top_tie_size": round(statistics.fmean([x["top_tie_size"] for x in xs]), 4),
                    "mean_bundle_size": round(statistics.fmean([x["bundle_size"] for x in xs]), 4),
                    "mean_bundle_reduction": round(statistics.fmean([x["bundle_reduction"] for x in xs]), 4),
                    "mean_top_decoy_rate": round(statistics.fmean([x["top_decoy_rate"] for x in xs]), 4),
                }
    # aggregate by scorer across modes
    out["aggregate"] = {}
    for pool in sorted({r["pool"] for r in rows}):
        out["aggregate"][pool] = {}
        for scorer in SCORERS:
            xs = [r for r in rows if r["pool"] == pool and r["scorer"] == scorer]
            out["aggregate"][pool][scorer] = {
                "top1_accuracy": mean([x["correct_top1"] for x in xs]),
                "target_in_top_tie": mean([x["target_in_top_tie"] for x in xs]),
                "mean_target_rank": round(statistics.fmean([x["target_rank"] for x in xs]), 4),
                "mean_top_tie_size": round(statistics.fmean([x["top_tie_size"] for x in xs]), 4),
                "mean_bundle_size": round(statistics.fmean([x["bundle_size"] for x in xs]), 4),
                "mean_bundle_reduction": round(statistics.fmean([x["bundle_reduction"] for x in xs]), 4),
            }
    return out


def mean(xs):
    return round(statistics.fmean([float(x) for x in xs]), 4) if xs else None


def render_report(summary, rows, n_real, n_decoy):
    lines = [
        "# Payload Graph Projection Refinement",
        "",
        "Memory content: LDGR historical findings. Coarse key: generic label-free recurrence motif. Payload: semantic/content graph connecting data inside the motif.",
        "",
        f"Real payload graphs: {n_real}",
        f"Rewired decoys: {n_decoy}",
        "",
        "## Aggregate Results",
        "",
        "| pool | scorer | top1 | target in top tie | target rank | top tie | bundle | reduction |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pool, scorers in summary["aggregate"].items():
        for scorer, s in scorers.items():
            lines.append(f"| {pool} | {scorer} | {s['top1_accuracy']} | {s['target_in_top_tie']} | "
                         f"{s['mean_target_rank']} | {s['mean_top_tie_size']} | {s['mean_bundle_size']} | {s['mean_bundle_reduction']} |")
    lines += ["", "## Decoy Pool By Query Mode", ""]
    for mode in QUERY_MODES:
        lines += [f"### {mode}", "", "| scorer | top1 | target in top tie | top tie | bundle | reduction | decoy rate |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for scorer in SCORERS:
            s = summary["real_plus_rewired_decoys"][mode][scorer]
            lines.append(f"| {scorer} | {s['top1_accuracy']} | {s['target_in_top_tie']} | "
                         f"{s['mean_top_tie_size']} | {s['mean_bundle_size']} | {s['mean_bundle_reduction']} | {s['mean_top_decoy_rate']} |")
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "The rewired-decoy pool is the decisive control. Each decoy has the same payload nodes and same relation-label multiset as its paired real item, but different semantic connections. If node-bag and relation-topology tie while content_graph isolates the original, then the stored payload graph connections are doing refinement work beyond flat overlap.",
    ]
    return "\n".join(lines) + "\n"


def main():
    print("building LDGR historical payload graphs...")
    items = build_corpus(max_items=32, per_topic_cap=8)
    real = [payload_graph(it) for it in items]
    rng = random.Random(20260706)
    decoys = [rewire_decoy(g, rng) for g in real]

    rows = []
    rows.extend(run_pool(real, real, "real_only"))
    rows.extend(run_pool(real, real + decoys, "real_plus_rewired_decoys"))
    summ = summarize(rows)

    out = {"experiment": "payload-graph-refinement-profile",
           "branch": "payload-graph-refinement",
           "architecture": "label-free recurrence motif -> projected semantic payload graph -> refinement",
           "n_real": len(real), "n_decoys": len(decoys),
           "scorers": SCORERS, "query_modes": QUERY_MODES,
           "summary": summ, "rows": rows,
           "graphs": {"real": [g.__dict__ for g in real], "decoys": [g.__dict__ for g in decoys]}}
    json_path = OUT_DIR / "payload_graph_refinement_results.json"
    json_path.write_text(json.dumps(out, indent=2))
    md_path = OUT_DIR / "payload_graph_refinement_report.md"
    md_path.write_text(render_report(summ, rows, len(real), len(decoys)))

    print("\nPAYLOAD GRAPH PROJECTION REFINEMENT")
    print("=" * 78)
    print(f"real graphs={len(real)} decoys={len(decoys)}")
    print("\naggregate:")
    for pool, scorers in summ["aggregate"].items():
        print(f"  {pool}")
        for scorer, s in scorers.items():
            print(f"    {scorer:<18} top1={s['top1_accuracy']:<6} tieIncl={s['target_in_top_tie']:<6} "
                  f"rank={s['mean_target_rank']:<7} bundle={s['mean_bundle_size']:<7} red={s['mean_bundle_reduction']}")
    print(f"\nwrote {json_path.name}")
    print(f"wrote {md_path.name}")


if __name__ == "__main__":
    main()
