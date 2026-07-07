"""Prototype topology constraint-layer memory.

This is intentionally not a learner/reasoner. It is a structural memory/index
that stores canonical recurrent temporal motifs and retrieves bounded compatible
continuations for a downstream system.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from recurrence_topology_experiment import TemporalSignature, canonical_signature


@dataclass(frozen=True)
class ContinuationCandidate:
    suffix: tuple[int, ...]
    motif_ids: tuple[str, ...]
    support: int


OperatingMode = Literal["conservative", "balanced", "exploratory", "adaptive"]


@dataclass(frozen=True)
class QueryPolicy:
    mode: OperatingMode
    max_candidates: int
    min_remaining: int = 1
    abstain_on_low_confidence: float = 0.0


MODE_POLICIES: dict[OperatingMode, QueryPolicy] = {
    "conservative": QueryPolicy("conservative", max_candidates=5, min_remaining=2),
    "balanced": QueryPolicy("balanced", max_candidates=25, min_remaining=1),
    "exploratory": QueryPolicy("exploratory", max_candidates=100, min_remaining=1),
    "adaptive": QueryPolicy("adaptive", max_candidates=25, min_remaining=1),
}


@dataclass(frozen=True)
class QueryResult:
    prefix: tuple[int, ...]
    candidates: tuple[ContinuationCandidate, ...]
    abstained: bool
    reason: str | None
    mode: OperatingMode = "balanced"
    policy: QueryPolicy | None = None

    @property
    def set_size(self) -> int:
        return len(self.candidates)

    @property
    def confidence(self) -> float:
        """A simple structural confidence proxy based only on set size."""

        if self.abstained or not self.candidates:
            return 0.0
        return 1.0 / len(self.candidates)


@dataclass
class TopologyConstraintMemory:
    """Stores canonical motifs and returns bounded compatible continuations."""

    min_support: int = 2
    motif_support: Counter[TemporalSignature] = field(default_factory=Counter)
    motif_ids: dict[TemporalSignature, set[str]] = field(default_factory=lambda: defaultdict(set))
    mode_feedback: dict[OperatingMode, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )

    def observe(self, sequence: Sequence[str], *, motif_id: str | None = None) -> TemporalSignature:
        signature = canonical_signature(sequence)
        self.motif_support[signature] += 1
        self.motif_ids[signature].add(motif_id or f"motif_{len(self.motif_ids):06d}")
        return signature

    def observe_many(self, sequences: Iterable[Sequence[str]]) -> None:
        for sequence in sequences:
            self.observe(sequence)

    def consolidated_motifs(self) -> tuple[TemporalSignature, ...]:
        return tuple(
            signature
            for signature, support in self.motif_support.items()
            if support >= self.min_support
        )

    def policy_for_mode(self, mode: OperatingMode) -> QueryPolicy:
        if mode != "adaptive":
            return MODE_POLICIES[mode]

        feedback = self.mode_feedback["adaptive"]
        misses = feedback["miss"] + feedback["bad_abstention"]
        overloads = feedback["too_many_compatible_continuations"]
        useful = feedback["selected"] + feedback["hit"]
        max_candidates = MODE_POLICIES["adaptive"].max_candidates
        if misses > useful:
            max_candidates = 100
        elif overloads > useful:
            max_candidates = 10
        return QueryPolicy("adaptive", max_candidates=max_candidates, min_remaining=1)

    def query(
        self,
        partial_sequence: Sequence[str],
        *,
        max_candidates: int | None = None,
        min_remaining: int | None = None,
        mode: OperatingMode = "balanced",
    ) -> QueryResult:
        policy = self.policy_for_mode(mode)
        max_candidates = policy.max_candidates if max_candidates is None else max_candidates
        min_remaining = policy.min_remaining if min_remaining is None else min_remaining
        prefix = canonical_signature(partial_sequence).trace
        matches: dict[tuple[int, ...], tuple[set[str], int]] = {}

        for motif in self.consolidated_motifs():
            if len(prefix) >= len(motif.trace):
                continue
            if motif.trace[: len(prefix)] != prefix:
                continue
            suffix = motif.trace[len(prefix) :]
            if len(suffix) < min_remaining:
                continue
            ids, support = matches.get(suffix, (set(), 0))
            ids.update(self.motif_ids[motif])
            support += self.motif_support[motif]
            matches[suffix] = (ids, support)

        candidates = tuple(
            sorted(
                (
                    ContinuationCandidate(
                        suffix=suffix,
                        motif_ids=tuple(sorted(ids)),
                        support=support,
                    )
                    for suffix, (ids, support) in matches.items()
                ),
                key=lambda candidate: (-candidate.support, candidate.suffix),
            )
        )

        effective_policy = QueryPolicy(mode, max_candidates, min_remaining)
        if not candidates:
            return QueryResult(
                prefix, (), True, "no_compatible_continuation", mode, effective_policy
            )
        if len(candidates) > max_candidates:
            return QueryResult(
                prefix,
                candidates,
                True,
                "too_many_compatible_continuations",
                mode,
                effective_policy,
            )
        result = QueryResult(prefix, candidates, False, None, mode, effective_policy)
        if result.confidence < policy.abstain_on_low_confidence:
            return QueryResult(
                prefix,
                candidates,
                True,
                "low_confidence",
                mode,
                effective_policy,
            )
        return result

    def record_query_outcome(
        self,
        result: QueryResult,
        outcome: Literal["selected", "hit", "miss", "bad_abstention", "ignored"],
    ) -> None:
        self.mode_feedback[result.mode][outcome] += 1
        if result.abstained and result.reason is not None:
            self.mode_feedback[result.mode][result.reason] += 1

    def update_from_confirmed_continuation(
        self,
        partial_sequence: Sequence[str],
        continuation_symbols: Sequence[str],
        *,
        motif_id: str | None = None,
    ) -> TemporalSignature:
        """Update memory after a downstream system observes/selects a continuation."""

        return self.observe(
            tuple(partial_sequence) + tuple(continuation_symbols), motif_id=motif_id
        )
