"""Dataset B: typed knowledge graph for motif-topology retrieval.

Replaces the phase-0 toy semantic world. The phase-0 world was a bag of
attributes on a taxonomic PATH, which the topology program already falsified as
"simple unlabeled paths are enough" -> Falsified (see
../topology/docs/research_program/claim_review_final.md). A path has no
recurrence topology, which is why ordered==unordered==typed there.

This dataset is a typed directed graph whose memory objects (rooted walks) have
real recurrence: shared intermediates create diamonds. Example motif:

    K-001 <--SUPPORTS-- L-001 --USES_METHOD--> long_window_motifs
       ^                                          ^
       |--WEAKENS--- L-002 --USES_METHOD----------+

Both records point at K-001 and share the method `long_window_motifs`, so a
depth-2 walk from K-001 revisits the method node -> recurrence -> a canonical
motif exists. Three claims built on the same typed diamond consolidate.

Motif families (each >=2 symbolically-disjoint instances so they consolidate):
  contested_claim   : SUPPORTS + WEAKENS records sharing a method (diamond)
  validated_claim   : single SUPPORTS record (star; expected WEAK motif, like a path)
  superseded_claim  : SUPPORTS + SUPERSEDED_BY another claim (chain recurrence)

The validated_claim family is included ON PURPOSE as a predicted-weak control:
per the topology falsification, a star has no recurrence and should NOT
consolidate into a discriminative motif. If it does as well as the diamond,
something is wrong.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# graph model
# ---------------------------------------------------------------------------

# node "kind" is metadata, not part of the canonical signature (signature is
# identity-free over node labels). It exists so humans can read the graph.
NODES: dict[str, str] = {
    # claims
    "K-001": "claim", "K-002": "claim", "K-003": "claim",
    "K-004": "claim", "K-005": "claim",
    "K-006": "claim", "K-007": "claim", "K-008": "claim", "K-009": "claim",
    # learning records
    "L-001": "record", "L-002": "record", "L-003": "record", "L-004": "record",
    "L-005": "record", "L-006": "record", "L-007": "record", "L-008": "record",
    "L-009": "record", "L-010": "record",
    # shared intermediates (the source of recurrence)
    "long_window_motifs": "method",
    "short_window_motifs": "method",
    "structural_signature": "method",
    "degree_match_control": "method",
    "true_inclusion": "metric",
    "coverage": "metric",
    "candidate_reduction": "metric",
    "false_activation_rate": "metric",
    "topology_memory": "domain",
    "retrieval_specificity": "domain",
    # verdicts are leaves
    "passed": "verdict", "failed": "verdict", "inconclusive": "verdict",
}

# directed typed edges: (source, edge_type, target)
EDGES: list[tuple[str, str, str]] = [
    # --- family: contested_claim (SUPPORTS + WEAKENS sharing a method) -------
    # K-001 contested on topology_memory; both records use long_window_motifs
    ("L-001", "SUPPORTS", "K-001"),
    ("L-001", "USES_METHOD", "long_window_motifs"),
    ("L-001", "MEASURES", "true_inclusion"),
    ("L-001", "IN_DOMAIN", "topology_memory"),
    ("L-001", "HAS_VERDICT", "passed"),
    ("L-002", "WEAKENS", "K-001"),
    ("L-002", "USES_METHOD", "long_window_motifs"),
    ("L-002", "MEASURES", "coverage"),
    ("L-002", "IN_DOMAIN", "topology_memory"),
    ("L-002", "HAS_VERDICT", "failed"),

    # K-002 contested on retrieval_specificity; both records use structural_signature
    ("L-003", "SUPPORTS", "K-002"),
    ("L-003", "USES_METHOD", "structural_signature"),
    ("L-003", "MEASURES", "candidate_reduction"),
    ("L-003", "IN_DOMAIN", "retrieval_specificity"),
    ("L-003", "HAS_VERDICT", "passed"),
    ("L-004", "WEAKENS", "K-002"),
    ("L-004", "USES_METHOD", "structural_signature"),
    ("L-004", "MEASURES", "coverage"),
    ("L-004", "IN_DOMAIN", "retrieval_specificity"),
    ("L-004", "HAS_VERDICT", "failed"),

    # K-003 contested on topology_memory; both records use short_window_motifs
    ("L-005", "SUPPORTS", "K-003"),
    ("L-005", "USES_METHOD", "short_window_motifs"),
    ("L-005", "MEASURES", "true_inclusion"),
    ("L-005", "IN_DOMAIN", "topology_memory"),
    ("L-005", "HAS_VERDICT", "inconclusive"),
    ("L-006", "WEAKENS", "K-003"),
    ("L-006", "USES_METHOD", "short_window_motifs"),
    ("L-006", "MEASURES", "coverage"),
    ("L-006", "IN_DOMAIN", "topology_memory"),
    ("L-006", "HAS_VERDICT", "failed"),

    # --- family: validated_claim (single SUPPORTS star; predicted-weak) -----
    ("L-007", "SUPPORTS", "K-004"),
    ("L-007", "USES_METHOD", "degree_match_control"),
    ("L-007", "MEASURES", "false_activation_rate"),
    ("L-007", "IN_DOMAIN", "retrieval_specificity"),
    ("L-007", "HAS_VERDICT", "passed"),
    ("L-008", "SUPPORTS", "K-005"),
    ("L-008", "USES_METHOD", "degree_match_control"),
    ("L-008", "MEASURES", "false_activation_rate"),
    ("L-008", "IN_DOMAIN", "retrieval_specificity"),
    ("L-008", "HAS_VERDICT", "passed"),

    # --- family: superseded_claim (SUPPORTS + SUPERSEDED_BY chain) ----------
    ("L-009", "SUPPORTS", "K-006"),
    ("L-009", "USES_METHOD", "long_window_motifs"),
    ("L-009", "MEASURES", "true_inclusion"),
    ("L-009", "IN_DOMAIN", "topology_memory"),
    ("L-009", "HAS_VERDICT", "passed"),
    ("K-006", "SUPERSEDED_BY", "K-007"),
    # NOTE: K-008 gets its OWN support record L-010 below (not a reuse of L-009).
    # Reusing L-009 for both K-006 and K-008 coupled the two claims through the
    # shared record and made their typed signatures differ (correct behavior,
    # but it broke the "family consolidates >=2" design).
]

EDGES = [e for e in EDGES if not (e[0] == "L-007" and e[1] == "SUPPORTS" and e[2] == "K-008")]
EDGES += [
    ("L-010", "SUPPORTS", "K-008"),
    ("L-010", "USES_METHOD", "long_window_motifs"),
    ("L-010", "MEASURES", "true_inclusion"),
    ("L-010", "IN_DOMAIN", "topology_memory"),
    ("L-010", "HAS_VERDICT", "passed"),
    ("K-008", "SUPERSEDED_BY", "K-009"),
]

# focal entities whose rooted walks are the "memory objects" / retrieval targets
FOCAL_CLAIMS = ["K-001", "K-002", "K-003", "K-004", "K-005", "K-006", "K-008"]
FOCAL_RECORDS = ["L-001", "L-003", "L-005", "L-007", "L-009"]

# declared motif families for evaluation (focal claim -> expected family)
FAMILY_OF_CLAIM = {
    "K-001": "contested_claim",
    "K-002": "contested_claim",
    "K-003": "contested_claim",
    "K-004": "validated_claim",
    "K-005": "validated_claim",
    "K-006": "superseded_claim",
    "K-008": "superseded_claim",
}


@dataclass
class TypedGraph:
    nodes: dict[str, str]
    out_edges: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    in_edges: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def neighbors(self, node: str) -> list[tuple[str, str, str]]:
        """All incident edges as (other_node, edge_type, direction).

        direction='out' means node->other via edge_type;
        direction='in' means other->node via edge_type (traversed backward).
        Reverse traversal is tagged so the typed signature can distinguish
        'A supports B' (out) from 'A is-supported-by B' (in).
        """
        out = [(tgt, et, "out") for (et, tgt) in self.out_edges.get(node, [])]
        inn = [(src, et, "in") for (et, src) in self.in_edges.get(node, [])]
        # deterministic order: by (edge_type, direction, other_node)
        return sorted(out + inn, key=lambda e: (e[1], e[2], e[0]))


def build_graph() -> TypedGraph:
    g = TypedGraph(nodes=dict(NODES))
    for src, et, tgt in EDGES:
        g.out_edges.setdefault(src, []).append((et, tgt))
        g.in_edges.setdefault(tgt, []).append((et, src))
    for d in (g.out_edges, g.in_edges):
        for k, v in d.items():
            v.sort()
    return g


def rooted_walk(g: TypedGraph, root: str, max_depth: int = 2) -> list[tuple]:
    """Deterministic DFS walk from `root`.

    Returns a list of steps. Step 0 is the root. Each subsequent step is
    (node, edge_type, direction) describing the edge traversed to reach `node`
    from the previous node in the walk. Direction in {'out','in'} (see neighbors).

    Visited-set is per-branch (we allow revisiting a node if it sits on a
    different incident edge, because recurrence is exactly what we want to
    capture); we cap depth and total steps to stay bounded.
    """
    walk: list[tuple] = [(root, None, None)]
    # stack of (node, depth, path-set of canonical node ids on this branch)
    stack = [(root, 0, (root,))]
    # iterative DFS yielding in insertion order
    while stack:
        node, depth, branch_path = stack.pop(0)
        if depth >= max_depth:
            continue
        for other, et, direction in g.neighbors(node):
            step = (other, et, direction)
            walk.append(step)
            stack.append((other, depth + 1, branch_path + (other,)))
    return walk


def walks_for(g: TypedGraph, focals: Iterable[str], max_depth: int = 2) -> dict[str, list[tuple]]:
    return {f: rooted_walk(g, f, max_depth=max_depth) for f in focals}
