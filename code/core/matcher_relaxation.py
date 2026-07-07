"""Matcher ablation for canonical typed signatures.

This keeps the representation fixed (canonical first-occurrence ids + typed edge
payloads) and changes only the alignment rule:

  greedy        : current single-pass evidence->candidate matcher. If one
                  inserted evidence node is not found in the remaining candidate,
                  the candidate iterator is exhausted and later evidence cannot
                  align. This is the suspected noise-collapse bug.

  dp            : LCS / edit-distance-style alignment over node_trace. Can skip
                  unmatched evidence and candidate nodes optimally.

  bidirectional : cheap skip-capable heuristic. Forward pass can skip unmatched
                  evidence without consuming the candidate; backward pass does the
                  same from the end; keep the better alignment.

  bag_edges     : control that ignores recurrence/node identity. Score = typed
                  edge-label multiset containment. Stable but shape-free.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from generator import Instance
from signature import typed_canonical_signature


@dataclass(frozen=True)
class SigView:
    node_trace: tuple[int, ...]
    edge_label_trace: tuple[str, ...]
    typed_edges: frozenset[tuple[int, str, int]]
    typed_edge_counts: tuple[tuple[int, str, int, int], ...]
    node_set: frozenset[int]
    edge_bag: tuple[tuple[str, int], ...]


def view(walk) -> SigView:
    sig = typed_canonical_signature(walk)
    edge_bag = Counter(lab for lab in sig.edge_label_trace[1:] if lab != "—")
    return SigView(
        node_trace=sig.node_trace,
        edge_label_trace=sig.edge_label_trace,
        typed_edges=frozenset(sig.typed_edges),
        typed_edge_counts=sig.typed_edge_counts,
        node_set=frozenset(range(sig.node_count)),
        edge_bag=tuple(sorted(edge_bag.items())),
    )


# ---------------------------------------------------------------------------
# aligners: return {evidence_pos: candidate_pos}
# ---------------------------------------------------------------------------

def align_greedy(candidate: SigView, evidence: SigView) -> dict[int, int]:
    """Current buggy matcher: a missing evidence node exhausts the candidate."""
    out: dict[int, int] = {}
    c = candidate.node_trace
    j = 0
    for i, e_node in enumerate(evidence.node_trace):
        while j < len(c):
            if c[j] == e_node:
                out[i] = j
                j += 1
                break
            j += 1
    return out


def align_forward_skip(candidate: SigView, evidence: SigView) -> dict[int, int]:
    """Forward pass that can skip an unmatched evidence node and continue.

    Difference from greedy: when e_node is not found in the remaining candidate,
    leave j unchanged rather than consuming the rest of the candidate.
    """
    out: dict[int, int] = {}
    c = candidate.node_trace
    j = 0
    for i, e_node in enumerate(evidence.node_trace):
        found = None
        for k in range(j, len(c)):
            if c[k] == e_node:
                found = k
                break
        if found is not None:
            out[i] = found
            j = found + 1
        # else: skip this evidence node; keep j so later evidence can recover
    return out


def _reverse_alignment(aln_rev: dict[int, int], n_e: int, n_c: int) -> dict[int, int]:
    return {n_e - 1 - ei_r: n_c - 1 - ci_r for ei_r, ci_r in aln_rev.items()}


def align_backward_skip(candidate: SigView, evidence: SigView) -> dict[int, int]:
    c_rev = SigView(
        node_trace=tuple(reversed(candidate.node_trace)),
        edge_label_trace=(), typed_edges=frozenset(), typed_edge_counts=(),
        node_set=candidate.node_set, edge_bag=(),
    )
    e_rev = SigView(
        node_trace=tuple(reversed(evidence.node_trace)),
        edge_label_trace=(), typed_edges=frozenset(), typed_edge_counts=(),
        node_set=evidence.node_set, edge_bag=(),
    )
    return _reverse_alignment(
        align_forward_skip(c_rev, e_rev), len(evidence.node_trace), len(candidate.node_trace)
    )


def align_dp(candidate: SigView, evidence: SigView) -> dict[int, int]:
    """LCS alignment over node ids; skips evidence/candidate nodes optimally."""
    c = candidate.node_trace
    e = evidence.node_trace
    n, m = len(e), len(c)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if e[i] == c[j]:
                dp[i][j] = 1 + dp[i + 1][j + 1]
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    out: dict[int, int] = {}
    i = j = 0
    while i < n and j < m:
        if e[i] == c[j]:
            out[i] = j
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1  # skip evidence
        else:
            j += 1  # skip candidate
    return out


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

@dataclass
class MatchScore:
    matcher: str
    aligned: int
    missing: int
    extraneous: int
    contradiction: float
    structure_score: float
    typed_support: float
    missing_penalty: float
    extraneous_penalty: float
    contradict_penalty: float
    total: float


def _typed_support_and_contradiction(candidate: SigView, evidence: SigView, aln: dict[int, int], weights: dict) -> tuple[float, float]:
    typed_support = 0.0
    contradiction = 0.0
    for i in range(1, len(evidence.node_trace)):
        if i not in aln or (i - 1) not in aln:
            continue
        e_lab = evidence.edge_label_trace[i] if i < len(evidence.edge_label_trace) else "—"
        if e_lab == "—":
            continue
        a = candidate.node_trace[aln[i - 1]]
        b = candidate.node_trace[aln[i]]
        if (a, e_lab, b) in candidate.typed_edges:
            typed_support += weights["w_typed"]
        else:
            pair_labels = {lab for (aa, lab, bb) in candidate.typed_edges if aa == a and bb == b}
            if pair_labels and e_lab not in pair_labels:
                contradiction += weights["w_contradict"]
    return typed_support, contradiction


def _score_with_alignment(candidate: SigView, evidence: SigView, aln: dict[int, int], matcher: str, weights: dict) -> MatchScore:
    total_e = len(evidence.node_trace)
    aligned = len(aln)
    missing = 0
    extraneous = 0
    for i, e_node in enumerate(evidence.node_trace):
        if i in aln:
            continue
        if e_node in candidate.node_set:
            missing += 1
        else:
            extraneous += 1

    typed_support, contradiction = _typed_support_and_contradiction(candidate, evidence, aln, weights)
    aligned_frac = aligned / total_e if total_e else 1.0
    structure_score = weights["w_structure"] * aligned_frac
    missing_penalty = weights["w_missing"] * (missing / total_e if total_e else 0.0)
    extraneous_penalty = weights["w_extraneous"] * (extraneous / total_e if total_e else 0.0)
    contradict_penalty = contradiction
    total = structure_score + typed_support - missing_penalty - extraneous_penalty - contradict_penalty
    return MatchScore(
        matcher=matcher, aligned=aligned, missing=missing, extraneous=extraneous,
        contradiction=round(contradiction, 4), structure_score=round(structure_score, 4),
        typed_support=round(typed_support, 4), missing_penalty=round(missing_penalty, 4),
        extraneous_penalty=round(extraneous_penalty, 4), contradict_penalty=round(contradict_penalty, 4),
        total=round(total, 4),
    )


def _score_bag(candidate: SigView, evidence: SigView, weights: dict) -> MatchScore:
    cand = Counter(dict(candidate.edge_bag))
    ev = Counter(dict(evidence.edge_bag))
    denom = sum(ev.values())
    covered = sum(min(cand[e], ev[e]) for e in ev)
    containment = covered / denom if denom else 1.0
    total = weights["w_structure"] * containment
    return MatchScore(
        matcher="bag_edges", aligned=covered, missing=max(denom - covered, 0), extraneous=0,
        contradiction=0.0, structure_score=round(total, 4), typed_support=0.0,
        missing_penalty=0.0, extraneous_penalty=0.0, contradict_penalty=0.0,
        total=round(total, 4),
    )


def score(candidate: SigView, evidence: SigView, *, matcher: str, weights: dict) -> MatchScore:
    if matcher == "greedy":
        return _score_with_alignment(candidate, evidence, align_greedy(candidate, evidence), matcher, weights)
    if matcher == "dp":
        return _score_with_alignment(candidate, evidence, align_dp(candidate, evidence), matcher, weights)
    if matcher == "bidirectional":
        f = _score_with_alignment(candidate, evidence, align_forward_skip(candidate, evidence), matcher, weights)
        b = _score_with_alignment(candidate, evidence, align_backward_skip(candidate, evidence), matcher, weights)
        return f if f.total >= b.total else b
    if matcher == "bag_edges":
        return _score_bag(candidate, evidence, weights)
    raise ValueError(matcher)


@dataclass
class MatcherRelaxationIndex:
    # DP/LCS is now the default: skip-capable, preserves polysemy/reduction in
    # matcher_ablation_results.json, and fixes the causal greedy noise failure.
    matcher: str = "dp"
    weights: dict = None
    entries: list[dict] = None

    def __post_init__(self):
        if self.weights is None:
            self.weights = {"w_structure": 1.0, "w_typed": 0.5, "w_contradict": 0.7,
                            "w_missing": 1.0, "w_extraneous": 0.15}
        if self.entries is None:
            self.entries = []

    def add(self, inst: Instance) -> None:
        self.entries.append({
            "family": inst.family, "focal": inst.focal_node(),
            "view": view(inst.walk), "walk": inst.walk,
        })

    def add_all(self, insts: Sequence[Instance]) -> None:
        for inst in insts:
            self.add(inst)

    def relax(self, evidence_walk) -> dict:
        e_view = view(evidence_walk)
        scored = []
        for ent in self.entries:
            s = score(ent["view"], e_view, matcher=self.matcher, weights=self.weights)
            scored.append({**s.__dict__, "family": ent["family"], "focal": ent["focal"]})
        scored.sort(key=lambda r: r["total"], reverse=True)
        dominant = None
        if scored:
            top_score = scored[0]["total"]
            top_fams = {r["family"] for r in scored if abs(r["total"] - top_score) < 1e-9}
            dominant = next(iter(top_fams)) if len(top_fams) == 1 else None
        gap = None
        if len(scored) >= 2:
            top_fam = scored[0]["family"]
            for r in scored[1:]:
                if r["family"] != top_fam:
                    gap = round(scored[0]["total"] - r["total"], 4)
                    break
        bundle_n = self._bundle(scored)
        return {
            "ranked": scored,
            "dominant_family": dominant,
            "top_score": scored[0]["total"] if scored else None,
            "score_gap": gap,
            "bundle_size": bundle_n,
            "family_counts": dict(Counter(r["family"] for r in scored[:bundle_n])),
        }

    @staticmethod
    def _bundle(scored) -> int:
        if not scored:
            return 0
        top = scored[0]["total"]
        threshold = top * 0.9 if top > 0 else top * 1.1
        n = 0
        for r in scored:
            if (top >= 0 and r["total"] >= threshold) or (top < 0 and r["total"] <= threshold):
                n += 1
            else:
                break
        return max(n, 1)
