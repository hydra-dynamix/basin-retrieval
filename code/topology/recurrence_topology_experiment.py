"""Nontrivial recurrent temporal topology follow-up experiment.

This experiment preserves temporal recurrence and repeated substructure while
canonicalizing symbol identity away. It uses no ML, embeddings, gradients, or
semantic features.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class TemporalSignature:
    node_count: int
    trace: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    edge_counts: tuple[tuple[int, int, int], ...]

    def key(self) -> str:
        trace = ">".join(str(node) for node in self.trace)
        edges = ",".join(f"{a}>{b}" for a, b in self.edges)
        counts = ",".join(f"{a}>{b}:{count}" for a, b, count in self.edge_counts)
        return f"n={self.node_count};t={trace};e={edges};c={counts}"


@dataclass(frozen=True)
class SequenceResult:
    name: str
    motif_family: str
    sequence: tuple[str, ...]
    expected_class: str
    signature: str
    motif_activation_score: float
    trace_similarity_score: float
    edge_overlap_score: float
    edge_count_similarity_score: float
    structural_similarity_score: float
    false_activation: bool


@dataclass(frozen=True)
class ExperimentResult:
    motif_families: tuple[str, ...]
    training_sequences: dict[str, tuple[tuple[str, ...], ...]]
    consolidated_motifs: dict[str, dict[str, int]]
    compression_ratio: float
    sequence_results: tuple[SequenceResult, ...]
    overall_false_activation_rate: float
    random_false_activation_rate: float
    criteria: dict[str, bool]
    outcome: str


def canonical_signature(sequence: Sequence[str]) -> TemporalSignature:
    ids: dict[str, int] = {}
    encoded: list[int] = []
    for symbol in sequence:
        if symbol not in ids:
            ids[symbol] = len(ids)
        encoded.append(ids[symbol])

    transitions = list(zip(encoded, encoded[1:], strict=False))
    edge_counter = Counter(transitions)
    return TemporalSignature(
        node_count=len(ids),
        trace=tuple(encoded),
        edges=tuple(sorted(edge_counter)),
        edge_counts=tuple(sorted((a, b, count) for (a, b), count in edge_counter.items())),
    )


def consolidate(
    training_sequences: Mapping[str, Iterable[Sequence[str]]], min_support: int = 2
) -> dict[str, Counter[TemporalSignature]]:
    consolidated: dict[str, Counter[TemporalSignature]] = {}
    for family, sequences in training_sequences.items():
        counts: Counter[TemporalSignature] = Counter(canonical_signature(seq) for seq in sequences)
        consolidated[family] = Counter(
            {signature: count for signature, count in counts.items() if count >= min_support}
        )
    return consolidated


def trace_similarity(a: TemporalSignature, b: TemporalSignature) -> float:
    positional_matches = sum(left == right for left, right in zip(a.trace, b.trace, strict=False))
    max_len = max(len(a.trace), len(b.trace))
    if max_len == 0:
        return 1.0
    return positional_matches / max_len


def edge_overlap(a: TemporalSignature, b: TemporalSignature) -> float:
    a_edges = set(a.edges)
    b_edges = set(b.edges)
    if not a_edges and not b_edges:
        return 1.0
    return len(a_edges & b_edges) / len(a_edges | b_edges)


def edge_count_similarity(a: TemporalSignature, b: TemporalSignature) -> float:
    a_counts = {(x, y): count for x, y, count in a.edge_counts}
    b_counts = {(x, y): count for x, y, count in b.edge_counts}
    keys = set(a_counts) | set(b_counts)
    if not keys:
        return 1.0
    numerator = sum(min(a_counts.get(key, 0), b_counts.get(key, 0)) for key in keys)
    denominator = sum(max(a_counts.get(key, 0), b_counts.get(key, 0)) for key in keys)
    return numerator / denominator


def structural_similarity(a: TemporalSignature, b: TemporalSignature) -> float:
    node_similarity = min(a.node_count, b.node_count) / max(a.node_count, b.node_count)
    return (
        trace_similarity(a, b) + edge_overlap(a, b) + edge_count_similarity(a, b) + node_similarity
    ) / 4


def score_sequence(
    name: str,
    motif_family: str,
    sequence: Sequence[str],
    expected_class: str,
    motifs: dict[str, Counter[TemporalSignature]],
) -> SequenceResult:
    signature = canonical_signature(sequence)
    family_motifs = motifs[motif_family]
    exact = 1.0 if signature in family_motifs else 0.0
    motif_signatures = tuple(family_motifs)
    trace_score = max(
        (trace_similarity(signature, motif) for motif in motif_signatures), default=0.0
    )
    edge_score = max((edge_overlap(signature, motif) for motif in motif_signatures), default=0.0)
    count_score = max(
        (edge_count_similarity(signature, motif) for motif in motif_signatures), default=0.0
    )
    structure_score = max(
        (structural_similarity(signature, motif) for motif in motif_signatures), default=0.0
    )
    is_control = expected_class not in {"positive", "automorphic_equivalent"}
    return SequenceResult(
        name=name,
        motif_family=motif_family,
        sequence=tuple(sequence),
        expected_class=expected_class,
        signature=signature.key(),
        motif_activation_score=exact,
        trace_similarity_score=round(trace_score, 6),
        edge_overlap_score=round(edge_score, 6),
        edge_count_similarity_score=round(count_score, 6),
        structural_similarity_score=round(structure_score, 6),
        false_activation=is_control and exact >= 0.75,
    )


def training_data() -> dict[str, tuple[tuple[str, ...], ...]]:
    return {
        "recurrence_loop": (
            ("A1", "B1", "A1", "C1", "A1"),
            ("A2", "B2", "A2", "C2", "A2"),
            ("A3", "B3", "A3", "C3", "A3"),
        ),
        "branch_converge_loop": (
            ("A1", "B1", "D1", "A1", "C1", "D1", "A1"),
            ("A2", "B2", "D2", "A2", "C2", "D2", "A2"),
            ("A3", "B3", "D3", "A3", "C3", "D3", "A3"),
        ),
        "repeated_substructure": (
            ("A1", "B1", "A1", "C1", "A1", "B1", "A1", "C1"),
            ("A2", "B2", "A2", "C2", "A2", "B2", "A2", "C2"),
            ("A3", "B3", "A3", "C3", "A3", "B3", "A3", "C3"),
        ),
    }


def deterministic_random_control(
    rng: random.Random, family: str, index: int, length: int, node_count: int
) -> tuple[str, ...]:
    symbols = tuple(f"R_{family}_{index}_{node}" for node in range(node_count))
    return tuple(rng.choice(symbols) for _ in range(length))


def evaluation_sequences() -> list[tuple[str, str, tuple[str, ...], str]]:
    from control_generator import sample_degree_matched_controls

    records: list[tuple[str, str, tuple[str, ...], str]] = [
        (
            "recurrence_positive",
            "recurrence_loop",
            ("A4", "B4", "A4", "C4", "A4"),
            "positive",
        ),
        (
            "recurrence_length_matched_path",
            "recurrence_loop",
            ("P0", "P1", "P2", "P3", "P4"),
            "length_matched_path_control",
        ),
        (
            "recurrence_shuffled",
            "recurrence_loop",
            ("A4", "B4", "C4", "A4", "A4"),
            "shuffled_control",
        ),
        (
            "recurrence_perturbed",
            "recurrence_loop",
            ("A4", "B4", "A4", "B4", "C4"),
            "perturbed_control",
        ),
        (
            "branch_converge_positive",
            "branch_converge_loop",
            ("A4", "B4", "D4", "A4", "C4", "D4", "A4"),
            "positive",
        ),
        (
            "branch_converge_branch_swap_automorphic",
            "branch_converge_loop",
            ("A4", "C4", "D4", "A4", "B4", "D4", "A4"),
            "automorphic_equivalent",
        ),
        (
            "branch_converge_length_matched_path",
            "branch_converge_loop",
            ("P0", "P1", "P2", "P3", "P4", "P5", "P6"),
            "length_matched_path_control",
        ),
        (
            "branch_converge_perturbed",
            "branch_converge_loop",
            ("A4", "B4", "D4", "C4", "A4", "D4", "A4"),
            "perturbed_control",
        ),
        (
            "repeated_substructure_positive",
            "repeated_substructure",
            ("A4", "B4", "A4", "C4", "A4", "B4", "A4", "C4"),
            "positive",
        ),
        (
            "repeated_substructure_length_matched_path",
            "repeated_substructure",
            ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"),
            "length_matched_path_control",
        ),
        (
            "repeated_substructure_shuffled",
            "repeated_substructure",
            ("A4", "B4", "A4", "B4", "A4", "C4", "A4", "C4"),
            "shuffled_control",
        ),
        (
            "repeated_substructure_perturbed",
            "repeated_substructure",
            ("A4", "B4", "C4", "A4", "B4", "A4", "C4", "A4"),
            "perturbed_control",
        ),
    ]

    motifs_by_family = {
        family: canonical_signature(sequences[0]) for family, sequences in training_data().items()
    }
    for family, motif in motifs_by_family.items():
        generated_controls = sample_degree_matched_controls(
            motif,
            family=family,
            count=5,
            seed=20260622 + len(records),
        )
        records.extend(
            (
                control.name,
                family,
                control.sequence,
                "degree_matched_non_isomorphic_control",
            )
            for control in generated_controls
        )

    rng = random.Random(20260622)
    motif_specs = {
        family: (len(motif.trace), motif.node_count) for family, motif in motifs_by_family.items()
    }
    for family, (length, node_count) in motif_specs.items():
        for index in range(100):
            records.append(
                (
                    f"{family}_random_{index:03d}",
                    family,
                    deterministic_random_control(rng, family, index, length, node_count),
                    "random_control",
                )
            )
    return records


def run_experiment() -> ExperimentResult:
    training = training_data()
    motifs = consolidate(training, min_support=2)
    sequence_results = tuple(
        score_sequence(name, family, sequence, expected_class, motifs)
        for name, family, sequence, expected_class in evaluation_sequences()
    )

    positives = [result for result in sequence_results if result.expected_class == "positive"]
    automorphic_equivalents = [
        result for result in sequence_results if result.expected_class == "automorphic_equivalent"
    ]
    length_controls = [
        result
        for result in sequence_results
        if result.expected_class == "length_matched_path_control"
    ]
    perturbed_controls = [
        result
        for result in sequence_results
        if result.expected_class in {"shuffled_control", "perturbed_control"}
    ]
    degree_matched_controls = [
        result
        for result in sequence_results
        if result.expected_class == "degree_matched_non_isomorphic_control"
    ]
    negative_controls = [
        result
        for result in sequence_results
        if result.expected_class not in {"positive", "automorphic_equivalent"}
    ]
    random_controls = [
        result for result in sequence_results if result.expected_class == "random_control"
    ]

    overall_false_activation_rate = sum(
        result.false_activation for result in negative_controls
    ) / len(negative_controls)
    random_false_activation_rate = sum(result.false_activation for result in random_controls) / len(
        random_controls
    )
    compression_ratio = sum(len(sequences) for sequences in training.values()) / max(
        sum(len(family_motifs) for family_motifs in motifs.values()), 1
    )
    mean_positive_similarity = sum(
        result.structural_similarity_score for result in positives
    ) / len(positives)

    criteria = {
        "all_positive_activation_ge_0_75": all(
            result.motif_activation_score >= 0.75 for result in positives
        ),
        "mean_positive_similarity_ge_0_90": mean_positive_similarity >= 0.90,
        "all_automorphic_equivalents_activation_ge_0_75": all(
            result.motif_activation_score >= 0.75 for result in automorphic_equivalents
        ),
        "all_length_matched_paths_activation_lt_0_75": all(
            result.motif_activation_score < 0.75 for result in length_controls
        ),
        "all_shuffled_perturbed_activation_lt_0_75": all(
            result.motif_activation_score < 0.75 for result in perturbed_controls
        ),
        "all_degree_matched_non_isomorphic_activation_lt_0_75": all(
            result.motif_activation_score < 0.75 for result in degree_matched_controls
        ),
        "overall_false_activation_rate_le_0_05": overall_false_activation_rate <= 0.05,
        "random_false_activation_rate_le_0_05": random_false_activation_rate <= 0.05,
        "compression_ratio_ge_3": compression_ratio >= 3.0,
    }

    if all(criteria.values()):
        outcome = "supported"
    elif criteria["all_positive_activation_ge_0_75"] and criteria["compression_ratio_ge_3"]:
        outcome = "partially_supported_control_failures"
    elif not criteria["all_positive_activation_ge_0_75"]:
        outcome = "falsified_positive_failed"
    else:
        outcome = "inconclusive"

    return ExperimentResult(
        motif_families=tuple(training),
        training_sequences=training,
        consolidated_motifs={
            family: {signature.key(): count for signature, count in family_motifs.items()}
            for family, family_motifs in motifs.items()
        },
        compression_ratio=round(compression_ratio, 6),
        sequence_results=sequence_results,
        overall_false_activation_rate=round(overall_false_activation_rate, 6),
        random_false_activation_rate=round(random_false_activation_rate, 6),
        criteria=criteria,
        outcome=outcome,
    )


def main() -> None:
    output_path = Path("results/recurrence_topology_experiment_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_experiment()
    output_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(output_path)
    print(json.dumps({"outcome": result.outcome, "criteria": result.criteria}, indent=2))


if __name__ == "__main__":
    main()
