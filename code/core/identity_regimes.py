"""Edit-stable anonymous identity regimes.

Four ways to assign node identity in a walk, producing four signature variants:

  CANONICAL   : node_id = first-occurrence position. Edit-brittle (insert/delete
                renumbers everything after the edit point). Baseline. The regime
                that caused drop-stability=0.0 and noise collapse.

  LABEL       : node_id = hash(concrete_label). Direct label key. Identity-free
                FAILS here -- it is literally token overlap. Control for leakage:
                if role/payload-stable performs like LABEL, it has leaked.

  ROLE_PAYLOAD: node_id = hash(local incident edge-type multiset + degree/role +
                typed payload fingerprint). The middle path. Identity is derived
                from STRUCTURAL ROLE, so the same kind of node (same incident
                edges, same degree) shares identity across different concrete
                labels, AND identity does not change when OTHER nodes are
                inserted/deleted. Optionally extends to k-hop neighborhood.

  BAG_OF_EDGES: no node identity. Signature = Counter of typed edges. Control
                that gives up recurrence entirely. If this beats the others on
                stability, recurrence isn't doing work.

The crucial property to verify: under ROLE_PAYLOAD, inserting a foreign node
does NOT change the identities of existing nodes (their incident structure is
unchanged). Under CANONICAL, it renumbers everything. That is the root cause.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from signature import typed_canonical_signature

_REGIMES = ("canonical", "label", "role_payload", "bag_of_edges")


def _h(*parts) -> int:
    """Stable integer hash of the given parts (strings/ints/tuples)."""
    h = hashlib.md5(repr(tuple(parts)).encode()).hexdigest()
    return int(h[:8], 16)


# ---------------------------------------------------------------------------
# identity assignment per regime
# ---------------------------------------------------------------------------

def _incident_structure(walk: Sequence[tuple]) -> dict[str, dict]:
    """For each unique node label in the walk, compute its local incident structure.

    Returns {label: {edge_types: Counter, appearances: int, neighbors: set}}.
    Edge types = the (edge_type, direction) of every step where this label is the
    step node, PLUS the incoming edge from the previous step when this node is a
    target. This is the walk-local incident fingerprint.
    """
    struct: dict[str, dict] = {}
    labels_in_order = []
    for i, (node, et, direction) in enumerate(walk):
        if node not in struct:
            struct[node] = {"edge_types": Counter(), "appearances": 0, "neighbors": set()}
            labels_in_order.append(node)
        struct[node]["appearances"] += 1
        if et is not None:
            struct[node]["edge_types"][(et, direction)] += 1
        # edge from previous node to this one
        if i > 0:
            prev_node = walk[i - 1][0]
            prev_et = walk[i][1]  # edge label lives on the target step
            if prev_et is not None:
                struct[node]["edge_types"][(prev_et, "as_target")] += 1
                struct[prev_node]["edge_types"][(prev_et, "as_source")] += 1
                struct[node]["neighbors"].add(prev_node)
                struct[prev_node]["neighbors"].add(node)
    return struct


def assign_identities(walk: Sequence[tuple], regime: str, *, k_hop: int = 0) -> list[int]:
    """Return a list of integer ids, one per walk step, under the given regime.

    For bag_of_edges this is not meaningful (returns empty); the signature is
    computed separately.
    """
    if regime == "canonical":
        ids = {}
        out = []
        for (node, _et, _dir) in walk:
            if node not in ids:
                ids[node] = len(ids)
            out.append(ids[node])
        return out

    if regime == "label":
        return [_h(node) for (node, _et, _dir) in walk]

    if regime == "role_payload":
        struct = _incident_structure(walk)
        node_ids = {}
        for node in struct:
            edge_sig = tuple(sorted(struct[node]["edge_types"].items()))
            deg = (struct[node]["appearances"], len(struct[node]["neighbors"]))
            node_ids[node] = _h(edge_sig, deg)
        return [node_ids.get(node, _h(node)) for (node, _et, _dir) in walk]

    if regime == "bag_of_edges":
        return []  # handled in signature
    raise ValueError(regime)


# ---------------------------------------------------------------------------
# signature per regime
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegimeSignature:
    regime: str
    # node-trace-based regimes (canonical/label/role_payload):
    node_trace: tuple[int, ...]       # ids per step
    edge_label_trace: tuple[str, ...]  # "et|dir" per step (None->"—")
    typed_edges: tuple[tuple[int, str, int], ...]  # (src_id, label, tgt_id)
    # bag_of_edges:
    edge_bag: tuple[tuple[str, int], ...]  # sorted ((src_role,label,tgt_role? no)->count)
    node_count: int

    def key(self) -> str:
        if self.regime == "bag_of_edges":
            return "bag:" + ",".join(f"{e}:{n}" for e, n in self.edge_bag)
        t = ">".join(str(n) for n in self.node_trace)
        el = ",".join(self.edge_label_trace)
        e = ",".join(f"{a}-{l}->{b}" for a, l, b in self.typed_edges)
        return f"{self.regime}:n={self.node_count};t={t};el={el};e={e}"


def _edge_label(et, direction):
    if et is None:
        return "—"
    return f"{et}|{direction}"


def signature(walk: Sequence[tuple], regime: str, *, k_hop: int = 0) -> RegimeSignature:
    if regime == "bag_of_edges":
        # signature = multiset of edge labels (et|dir), source/target roles ignored
        bag = Counter()
        for i, (node, et, direction) in enumerate(walk):
            if et is not None:
                bag[_edge_label(et, direction)] += 1
        return RegimeSignature(
            regime="bag_of_edges", node_trace=(), edge_label_trace=(),
            typed_edges=(), edge_bag=tuple(sorted(bag.items())),
            node_count=len(set(n for n, _, _ in walk)),
        )

    node_ids = assign_identities(walk, regime, k_hop=k_hop)
    edge_label_trace = tuple(_edge_label(walk[i][1], walk[i][2]) for i in range(len(walk)))
    # typed edges: between consecutive ids
    typed_edges = []
    for i in range(1, len(walk)):
        lab = edge_label_trace[i]
        if lab != "—":
            typed_edges.append((node_ids[i - 1], lab, node_ids[i]))
    edge_counter = Counter(typed_edges)
    return RegimeSignature(
        regime=regime, node_trace=tuple(node_ids),
        edge_label_trace=edge_label_trace,
        typed_edges=tuple(sorted(edge_counter)),
        edge_bag=(),
        node_count=len(set(node_ids)),
    )


# ---------------------------------------------------------------------------
# matching / scoring per regime
# ---------------------------------------------------------------------------

def align_fraction(candidate_sig: RegimeSignature, evidence_sig: RegimeSignature) -> float:
    """Fraction of evidence structure the candidate can account for.

    For node-trace regimes: greedy in-order subsequence match of evidence node
    ids onto candidate node ids (ids are now STABLE under role_payload, so
    insertion in evidence doesn't renumber the candidate).

    For bag_of_edges: weighted Jaccard / containment of edge multisets.
    """
    if candidate_sig.regime == "bag_of_edges":
        cand = Counter(dict(candidate_sig.edge_bag))
        ev = Counter(dict(evidence_sig.edge_bag))
        if not ev:
            return 1.0
        covered = sum(min(cand[e], ev[e]) for e in ev)
        return covered / sum(ev.values())

    # node-trace: subsequence match on node ids
    e_nodes = evidence_sig.node_trace
    c_nodes = candidate_sig.node_trace
    if not e_nodes:
        return 1.0
    it = iter(c_nodes)
    matched = 0
    for e in e_nodes:
        for c in it:
            if c == e:
                matched += 1
                break
    return matched / len(e_nodes)


def typed_support(candidate_sig: RegimeSignature, evidence_sig: RegimeSignature) -> float:
    """How many evidence typed edges the candidate also has (as a fraction)."""
    if candidate_sig.regime == "bag_of_edges":
        return 0.0  # bag already counts edges in align_fraction
    e_edges = evidence_sig.typed_edges
    if not e_edges:
        return 0.0
    cand_set = set(candidate_sig.typed_edges)
    matched = sum(1 for e in e_edges if e in cand_set)
    return matched / len(e_edges)


# ---------------------------------------------------------------------------
# leakage / identity purity metric
# ---------------------------------------------------------------------------

def label_leakage(walks_with_labels: list[tuple[Sequence[tuple], str]]) -> dict:
    """Measure how much role_payload identity correlates with concrete labels.

    walks_with_labels: list of (walk, concrete_label_of_focal_node).
    Returns:
      collision_rate: fraction of pairs of DIFFERENT-label nodes that share a
                      role_payload identity. HIGH = good (identity-free, structural).
                      LOW = leaking toward label-key.
      distinct_identities_per_label: avg distinct role_payload ids per concrete label.
                      ~1.0 = leaked (one id per label). >>1 = structural.
    """
    # collect (concrete_label -> set of role_payload ids) across all walks
    label_to_ids: dict[str, set] = {}
    id_to_labels: dict[int, set] = {}
    for walk, focal_label in walks_with_labels:
        ids = assign_identities(walk, "role_payload")
        for (node, _et, _dir), nid in zip(walk, ids):
            label_to_ids.setdefault(node, set()).add(nid)
            id_to_labels.setdefault(nid, set()).add(node)
    # distinct ids per label (should be ~1 if structural: same label = same role)
    dpls = [len(s) for s in label_to_ids.values()]
    # distinct labels per id (should be >>1 if identity-free: same role = many labels)
    lpid = [len(s) for s in id_to_labels.values()]
    import statistics
    return {
        "n_labels": len(label_to_ids),
        "n_distinct_role_payload_ids": len(id_to_labels),
        "mean_distinct_ids_per_label": round(statistics.fmean(dpls), 4) if dpls else 0,
        "mean_distinct_labels_per_id": round(statistics.fmean(lpid), 4) if lpid else 0,
        "leakage_note": (
            "ids_per_label ~1 AND labels_per_id ~1 = pure label-key (LEAKED). "
            "labels_per_id >>1 = identity-free (good). "
            "ids_per_label >1 = same label has multiple structural roles."
        ),
    }
