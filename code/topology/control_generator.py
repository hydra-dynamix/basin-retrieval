"""Automorphism-aware control generation for temporal topology experiments.

Controls are generated only after canonicalization. Candidate negatives that
canonicalize to the target motif are rejected as automorphic/topologically
equivalent rather than counted as false activations.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from recurrence_topology_experiment import TemporalSignature, canonical_signature


@dataclass(frozen=True)
class GeneratedControl:
    name: str
    sequence: tuple[str, ...]
    signature: TemporalSignature
    attempts: int


def simple_degree_profile(signature: TemporalSignature) -> tuple[tuple[int, int], ...]:
    in_degree = Counter[int]()
    out_degree = Counter[int]()
    for source, target in signature.edges:
        out_degree[source] += 1
        in_degree[target] += 1
    return tuple(
        sorted((in_degree[node], out_degree[node]) for node in range(signature.node_count))
    )


def weighted_degree_profile(signature: TemporalSignature) -> tuple[tuple[int, int], ...]:
    in_degree = Counter[int]()
    out_degree = Counter[int]()
    for source, target, count in signature.edge_counts:
        out_degree[source] += count
        in_degree[target] += count
    return tuple(
        sorted((in_degree[node], out_degree[node]) for node in range(signature.node_count))
    )


def is_automorphic_equivalent(candidate: Sequence[str], motif: TemporalSignature) -> bool:
    """Return true when canonicalization makes the candidate the same motif."""

    return canonical_signature(candidate).key() == motif.key()


def is_degree_matched_non_isomorphic(candidate: Sequence[str], motif: TemporalSignature) -> bool:
    """Check length, node count, degree profile, and non-isomorphism after canonicalization."""

    signature = canonical_signature(candidate)
    return (
        len(signature.trace) == len(motif.trace)
        and signature.node_count == motif.node_count
        and signature.key() != motif.key()
        and simple_degree_profile(signature) == simple_degree_profile(motif)
        and weighted_degree_profile(signature) == weighted_degree_profile(motif)
    )


def _trace_to_symbols(trace: Sequence[int], prefix: str) -> tuple[str, ...]:
    return tuple(f"{prefix}_{node}" for node in trace)


def _all_nodes_used(trace: Sequence[int], node_count: int) -> bool:
    return set(trace) == set(range(node_count))


def sample_degree_matched_controls(
    motif: TemporalSignature,
    *,
    family: str,
    count: int,
    seed: int,
    max_attempts: int = 200_000,
) -> tuple[GeneratedControl, ...]:
    """Sample canonicalized, degree-matched, non-isomorphic controls.

    The generator deliberately checks every candidate after canonicalization. This
    prevents automorphic equivalents from entering the negative set.
    """

    rng = random.Random(seed)
    accepted: list[GeneratedControl] = []
    seen: set[str] = set()
    attempts = 0
    length = len(motif.trace)
    node_count = motif.node_count

    while len(accepted) < count and attempts < max_attempts:
        attempts += 1
        raw_trace = tuple(rng.randrange(node_count) for _ in range(length))
        if not _all_nodes_used(raw_trace, node_count):
            continue
        candidate_sequence = _trace_to_symbols(raw_trace, f"G_{family}_{len(accepted)}")
        signature = canonical_signature(candidate_sequence)
        signature_key = signature.key()
        if signature_key in seen or signature_key == motif.key():
            continue
        if not is_degree_matched_non_isomorphic(candidate_sequence, motif):
            continue
        seen.add(signature_key)
        accepted.append(
            GeneratedControl(
                name=f"{family}_degree_matched_non_isomorphic_{len(accepted):03d}",
                sequence=candidate_sequence,
                signature=signature,
                attempts=attempts,
            )
        )

    if len(accepted) < count:
        msg = (
            f"generated {len(accepted)} of {count} controls for {family} after {attempts} attempts"
        )
        raise RuntimeError(msg)
    return tuple(accepted)


def enumerate_automorphic_equivalent(
    motif_sequence: Sequence[str],
    *,
    name: str,
    transform: Callable[[tuple[str, ...]], tuple[str, ...]],
) -> GeneratedControl:
    """Create a known automorphic equivalent and validate it canonicalizes to the motif."""

    motif = canonical_signature(motif_sequence)
    candidate = transform(tuple(motif_sequence))
    signature = canonical_signature(candidate)
    if signature.key() != motif.key():
        raise ValueError("candidate is not automorphic/topologically equivalent")
    return GeneratedControl(name=name, sequence=candidate, signature=signature, attempts=1)
