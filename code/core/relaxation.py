"""Discrete relaxation by prefix-consistency pruning.

This is the retrieval mechanism for the unlabeled-basin-relaxation branch. It is
named honestly: it is ELIMINATION, not graded settling. Each evidence step is a
constraint; instance-walks whose typed canonical signature is not prefix-consistent
with the evidence are pruned. The surviving set is the current active basin.

Why this is "relaxation" and not "lookup":
  - The query is a GROWING evidence walk, fed one step at a time.
  - After each step the active set is recomputed (constraints tighten monotonically).
  - The dynamical quantity we care about is not "did we find the right family" but
    "how much can we perturb the evidence before the active basin changes" (basin
    depth). That is measured by re-relaxing after removing/corrupting steps.

The relaxation supports two signature variants on the same index:
  * typed    : node ids canonicalized, EDGE LABELS (edge_type + direction) kept.
  * labelfree: edge labels collapsed. Tests whether structure alone (phase 8)
               produces basins, or whether typed relations are required.

Index = all instance-walks. Query = concrete evidence walk (a prefix of a held-out
instance, or a perturbed version). Canonicalization strips concrete labels, so a
query matches an instance iff they share canonical structure -- identity-free.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from generator import Instance
from signature import label_free_canonical_signature, typed_canonical_signature

VARIANT = ("typed", "labelfree")


def _signature(walk, variant: str):
    if variant == "typed":
        return typed_canonical_signature(walk)
    return label_free_canonical_signature(walk)


def _prefix_view(sig, length: int):
    """Return (node_trace_prefix, edge_label_prefix) truncated to `length` nodes.

    Edge labels align with the TARGET step (see signature.py); step 0 has the
    sentinel label. So node_trace[:length] pairs with edge_label_trace[:length].
    """
    return (sig.node_trace[:length], sig.edge_label_trace[:length])


@dataclass(frozen=True)
class RelaxationState:
    """Snapshot of the active basin after a given evidence length."""
    evidence_length: int
    active_instances: tuple[str, ...]          # instance focal labels
    active_families: tuple[str, ...]           # family of each active instance
    family_counts: tuple[tuple[str, int], ...]  # sorted desc by count
    n_active: int
    n_distinct_families: int

    @property
    def dominant_family(self) -> str | None:
        if not self.family_counts:
            return None
        top = self.family_counts[0][1]
        tied = [f for f, c in self.family_counts if c == top]
        return None if len(tied) > 1 else self.family_counts[0][0]  # None = ambiguous/tied


@dataclass
class RelaxationIndex:
    variant: str
    instances: list[Instance] = field(default_factory=list)
    # cached full signatures
    _sigs: dict[str, object] = field(default_factory=dict)  # focal_label -> TypedSignature

    def add(self, inst: Instance) -> None:
        self.instances.append(inst)
        self._sigs[inst.focal_node()] = _signature(inst.walk, self.variant)

    def add_all(self, insts: Sequence[Instance]) -> None:
        for inst in insts:
            self.add(inst)

    def relax(self, evidence_walk, length: int | None = None) -> RelaxationState:
        """Run discrete relaxation for `length` evidence steps (default: full walk).

        Keeps instances whose canonical signature truncated to `length` matches the
        evidence's canonical signature truncated to `length`.
        """
        if length is None:
            length = len(evidence_walk)
        q_sig = _signature(evidence_walk, self.variant)
        q_node_pref, q_edge_pref = _prefix_view(q_sig, length)
        active: list[Instance] = []
        for inst in self.instances:
            isig = self._sigs[inst.focal_node()]
            i_node_pref, i_edge_pref = _prefix_view(isig, length)
            if i_node_pref == q_node_pref and i_edge_pref == q_edge_pref:
                active.append(inst)
        return self._snapshot(length, active)

    def relax_trajectory(self, evidence_walk) -> list[RelaxationState]:
        """Full relaxation trajectory: active basin after EACH evidence step.

        The narrowing curve. Returns len(walk) states (step 1 .. step N).
        """
        return [self.relax(evidence_walk, length=L) for L in range(1, len(evidence_walk) + 1)]

    # -- perturbation (the dynamical measurement) -----------------------------

    def perturb_drop(self, evidence_walk, drop_index: int) -> RelaxationState:
        """Drop evidence step at `drop_index` (0-based, 0 = root; dropping root is invalid).

        Returns the re-relaxed active basin. Recomputes canonical signature on the
        shortened concrete walk (node ids re-number, which is the point: the basin
        is defined by concrete evidence, not by a fixed index).
        """
        if drop_index == 0:
            raise ValueError("cannot drop the root step (index 0)")
        shortened = [evidence_walk[i] for i in range(len(evidence_walk)) if i != drop_index]
        return self.relax(shortened)

    def basin_stability(self, evidence_walk) -> dict:
        """For each droppable evidence step, does the dominant family survive?

        Compares the full-evidence dominant family against the dominant family
        after removing each single non-root step. A step is 'load-bearing' if
        dropping it changes the dominant family (incl. collapsing to ambiguity).
        """
        full = self.relax(evidence_walk)
        base_family = full.dominant_family
        results = []
        for i in range(1, len(evidence_walk)):
            perturbed = self.perturb_drop(evidence_walk, i)
            survived = (perturbed.dominant_family == base_family) if base_family else False
            results.append({
                "dropped_step": i,
                "dominant_after": perturbed.dominant_family,
                "n_active_after": perturbed.n_active,
                "n_families_after": perturbed.n_distinct_families,
                "survived": survived,
            })
        n_survived = sum(r["survived"] for r in results)
        return {
            "base_family": base_family,
            "n_droppable_steps": len(results),
            "n_survived": n_survived,
            "stability_rate": round(n_survived / len(results), 4) if results else 0.0,
            "per_step": results,
        }

    # -- internals ------------------------------------------------------------

    def _snapshot(self, length: int, active: list[Instance]) -> RelaxationState:
        fam_counts = Counter(i.family for i in active)
        sorted_counts = tuple(sorted(fam_counts.items(), key=lambda kv: (-kv[1], kv[0])))
        return RelaxationState(
            evidence_length=length,
            active_instances=tuple(i.focal_node() for i in active),
            active_families=tuple(i.family for i in active),
            family_counts=sorted_counts,
            n_active=len(active),
            n_distinct_families=len(fam_counts),
        )
