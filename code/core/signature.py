"""Canonical signatures for typed walks.

Faithful port of recurrence_topology_experiment.canonical_signature, extended to
preserve edge labels. The original canonicalizes node identity by first
occurrence (identity-free) and deliberately strips semantics to test pure
topology. Here we keep TWO signatures:

  * typed_canonical_signature   - node ids canonicalized; EDGE LABELS kept
                                  (edge_type + traversal direction). Tests whether
                                  typed-edge topology retrieves (episteme phase 4).
  * label_free_canonical_signature - edge labels ignored; reduces to the original
                                  topology signature. Tests pure structural
                                  generalization (episteme phase 8): two objects
                                  with different relations but the same shape
                                  (e.g. A-SUPPORTS->B-WEAKENS->C vs
                                  X-CONTRADICTS->Y-SUPERSEDES->Z) match.

The comparison between these two is itself scientific content: does keeping
relation types beat label-free topology? That is the phase-4-vs-phase-8 question
the toy could not ask.

Walk shape (from graph_dataset.rooted_walk):
    [(root, None, None), (node, edge_type, direction), ...]
where direction in {'out','in'} encodes traversal orientation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

# a walk step is (node, edge_type|None, direction|None)
WalkStep = tuple  # (str, str|None, str|None)

_UNTYPED = "—"  # sentinel edge label for the label-free signature


def _encode_edge_label(edge_type: str | None, direction: str | None) -> str:
    if edge_type is None:
        return _UNTYPED
    return f"{edge_type}|{direction}"


@dataclass(frozen=True)
class TypedSignature:
    node_count: int
    node_trace: tuple[int, ...]
    edge_label_trace: tuple[str, ...]
    typed_edges: tuple[tuple[int, str, int], ...]
    typed_edge_counts: tuple[tuple[int, str, int, int], ...]

    def key(self) -> str:
        t = ">".join(str(n) for n in self.node_trace)
        el = ",".join(self.edge_label_trace)
        e = ",".join(f"{a}-{lab}->{b}" for a, lab, b in self.typed_edges)
        c = ",".join(f"{a}-{lab}->{b}:{n}" for a, lab, b, n in self.typed_edge_counts)
        return f"n={self.node_count};t={t};el={el};e={e};c={c}"

    def label_free(self) -> "TypedSignature":
        """Collapse edge labels -> the original identity-free topology signature."""
        relabeled = tuple(_UNTYPED for _ in self.edge_label_trace)
        cnt: Counter[tuple[int, int]] = Counter()
        for a, _lab, b in self.typed_edges:
            cnt[(a, b)] += 1  # NOTE: this loses multiplicity across labels; recompute below
        # recompute edge multiset ignoring labels, preserving counts per (a,b)
        raw_counts: Counter[tuple[int, int]] = Counter()
        for a, lab, b, n in self.typed_edge_counts:
            raw_counts[(a, b)] += n
        edges = tuple(sorted(raw_counts))
        counts = tuple(sorted((a, b, n) for (a, b), n in raw_counts.items()))
        return TypedSignature(
            node_count=self.node_count,
            node_trace=self.node_trace,
            edge_label_trace=relabeled,
            typed_edges=tuple((a, _UNTYPED, b) for a, b in edges),
            typed_edge_counts=tuple((a, _UNTYPED, b, n) for a, b, n in counts),
        )


def _canonical_node_trace(walk: Sequence[WalkStep]) -> tuple[int, ...]:
    ids: dict[str, int] = {}
    encoded: list[int] = []
    for step in walk:
        node = step[0]
        if node not in ids:
            ids[node] = len(ids)
        encoded.append(ids[node])
    return tuple(encoded)


def typed_canonical_signature(walk: Sequence[WalkStep]) -> TypedSignature:
    node_trace = _canonical_node_trace(walk)
    # edge label per transition = label of the step we took TO reach each node
    # (step 0 has no incoming edge -> sentinel)
    edge_label_trace: list[str] = []
    for i, step in enumerate(walk):
        if i == 0:
            edge_label_trace.append(_UNTYPED)
        else:
            edge_label_trace.append(_encode_edge_label(step[1], step[2]))
    # the "edge label of a transition" aligns with the TARGET step's label
    incoming_labels = edge_label_trace[1:]
    transitions = list(zip(node_trace[:-1], incoming_labels, node_trace[1:], strict=False))
    counter: Counter[tuple[int, str, int]] = Counter(transitions)
    typed_edges = tuple(sorted(counter))
    typed_edge_counts = tuple(sorted((a, lab, b, n) for (a, lab, b), n in counter.items()))
    return TypedSignature(
        node_count=len(set(node_trace)),
        node_trace=node_trace,
        edge_label_trace=tuple(edge_label_trace),
        typed_edges=typed_edges,
        typed_edge_counts=typed_edge_counts,
    )


def label_free_canonical_signature(walk: Sequence[WalkStep]) -> TypedSignature:
    return typed_canonical_signature(walk).label_free()
