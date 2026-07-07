"""Multi-step motif completion horizon experiment."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from control_generator import sample_degree_matched_controls
from motif_completion_experiment import consolidate_motifs
from recurrence_topology_experiment import canonical_signature, training_data

HORIZONS = ("h1", "h2", "full")


@dataclass(frozen=True)
class HorizonCase:
    name: str
    motif_family: str
    expected_class: str
    partial_sequence: tuple[str, ...]
    candidate_sequence: tuple[str, ...] | None
    prediction_available: bool
    predicted_full_suffix: tuple[int, ...]
    observed_full_suffix: tuple[int, ...] | None
    accepted_h1: bool
    accepted_h2: bool
    accepted_full: bool


@dataclass(frozen=True)
class ExperimentResult:
    motifs: dict[str, str]
    cases: tuple[HorizonCase, ...]
    metrics: dict[str, float]
    criteria: dict[str, bool]
    outcome: str


def predicted_suffix(partial_sequence: Sequence[str], motif_family: str) -> tuple[int, ...] | None:
    motif = consolidate_motifs()[motif_family]
    partial_trace = canonical_signature(partial_sequence).trace
    if len(partial_trace) >= len(motif.trace):
        return None
    if motif.trace[: len(partial_trace)] != partial_trace:
        return None
    return motif.trace[len(partial_trace) :]


def observed_suffix(
    partial_sequence: Sequence[str], candidate_sequence: Sequence[str]
) -> tuple[int, ...] | None:
    partial_trace = canonical_signature(partial_sequence).trace
    candidate_trace = canonical_signature(candidate_sequence).trace
    if len(candidate_trace) <= len(partial_trace):
        return None
    if candidate_trace[: len(partial_trace)] != partial_trace:
        return None
    return candidate_trace[len(partial_trace) :]


def accepted_at_horizon(
    predicted: tuple[int, ...], observed: tuple[int, ...] | None, horizon: str
) -> bool:
    if observed is None:
        return False
    if horizon == "h1":
        length = 1
    elif horizon == "h2":
        length = min(2, len(predicted))
    elif horizon == "full":
        length = len(predicted)
    else:
        raise ValueError(horizon)
    return len(observed) >= length and observed[:length] == predicted[:length]


def evaluate_case(
    name: str,
    motif_family: str,
    partial_sequence: Sequence[str],
    candidate_sequence: Sequence[str] | None,
    expected_class: str,
) -> HorizonCase:
    predicted = predicted_suffix(partial_sequence, motif_family)
    observed = (
        None
        if candidate_sequence is None
        else observed_suffix(partial_sequence, candidate_sequence)
    )
    predicted_tuple = () if predicted is None else predicted
    return HorizonCase(
        name=name,
        motif_family=motif_family,
        expected_class=expected_class,
        partial_sequence=tuple(partial_sequence),
        candidate_sequence=None if candidate_sequence is None else tuple(candidate_sequence),
        prediction_available=predicted is not None,
        predicted_full_suffix=predicted_tuple,
        observed_full_suffix=observed,
        accepted_h1=predicted is not None and accepted_at_horizon(predicted, observed, "h1"),
        accepted_h2=predicted is not None and accepted_at_horizon(predicted, observed, "h2"),
        accepted_full=predicted is not None and accepted_at_horizon(predicted, observed, "full"),
    )


def predefined_cases() -> list[tuple[str, str, tuple[str, ...], tuple[str, ...] | None, str]]:
    return [
        (
            "recurrence_positive_full",
            "recurrence_loop",
            ("X", "Y", "X"),
            ("X", "Y", "X", "Z", "X"),
            "positive",
        ),
        (
            "recurrence_prefix_divergent_h1",
            "recurrence_loop",
            ("X", "Y", "X"),
            ("X", "Y", "X", "Z", "Y"),
            "prefix_divergent_control",
        ),
        (
            "recurrence_path",
            "recurrence_loop",
            ("P0", "P1", "P2"),
            ("P0", "P1", "P2", "P3", "P4"),
            "path_control",
        ),
        (
            "branch_positive_full",
            "branch_converge_loop",
            ("X", "Y", "Z", "X"),
            ("X", "Y", "Z", "X", "W", "Z", "X"),
            "positive",
        ),
        (
            "branch_prefix_divergent_h1",
            "branch_converge_loop",
            ("X", "Y", "Z", "X"),
            ("X", "Y", "Z", "X", "W", "Y", "X"),
            "prefix_divergent_control",
        ),
        (
            "branch_prefix_divergent_h2",
            "branch_converge_loop",
            ("X", "Y", "Z", "X"),
            ("X", "Y", "Z", "X", "W", "Z", "Y"),
            "prefix_divergent_control",
        ),
        (
            "branch_path",
            "branch_converge_loop",
            ("P0", "P1", "P2", "P3"),
            ("P0", "P1", "P2", "P3", "P4", "P5", "P6"),
            "path_control",
        ),
        (
            "repeated_positive_full",
            "repeated_substructure",
            ("X", "Y", "X", "Z", "X"),
            ("X", "Y", "X", "Z", "X", "Y", "X", "Z"),
            "positive",
        ),
        (
            "repeated_prefix_divergent_h1",
            "repeated_substructure",
            ("X", "Y", "X", "Z", "X"),
            ("X", "Y", "X", "Z", "X", "Y", "Z", "X"),
            "prefix_divergent_control",
        ),
        (
            "repeated_path",
            "repeated_substructure",
            ("P0", "P1", "P2", "P3", "P4"),
            ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"),
            "path_control",
        ),
    ]


def degree_matched_cases() -> list[tuple[str, str, tuple[str, ...], tuple[str, ...] | None, str]]:
    records: list[tuple[str, str, tuple[str, ...], tuple[str, ...] | None, str]] = []
    for family, motif in consolidate_motifs().items():
        controls = sample_degree_matched_controls(
            motif, family=f"horizon_{family}", count=5, seed=404000 + len(records)
        )
        for control in controls:
            split = max(2, len(control.sequence) // 2)
            records.append(
                (
                    f"{control.name}_horizon_probe",
                    family,
                    control.sequence[:split],
                    control.sequence,
                    "degree_matched_non_isomorphic_control",
                )
            )
    return records


def rate(cases: Sequence[HorizonCase], attr: str) -> float:
    if not cases:
        return 0.0
    return sum(bool(getattr(case, attr)) for case in cases) / len(cases)


def run_experiment() -> ExperimentResult:
    motifs = consolidate_motifs()
    raw_cases = predefined_cases() + degree_matched_cases()
    cases = tuple(evaluate_case(*case) for case in raw_cases)

    positives = [case for case in cases if case.expected_class == "positive"]
    degree_controls = [
        case for case in cases if case.expected_class == "degree_matched_non_isomorphic_control"
    ]
    prefix_controls = [case for case in cases if case.expected_class == "prefix_divergent_control"]
    path_controls = [case for case in cases if case.expected_class == "path_control"]
    compression_ratio = sum(len(sequences) for sequences in training_data().values()) / len(motifs)

    metrics = {
        "positive_h1_acceptance_rate": round(rate(positives, "accepted_h1"), 6),
        "positive_h2_acceptance_rate": round(rate(positives, "accepted_h2"), 6),
        "positive_full_acceptance_rate": round(rate(positives, "accepted_full"), 6),
        "degree_matched_h1_acceptance_rate": round(rate(degree_controls, "accepted_h1"), 6),
        "degree_matched_h2_acceptance_rate": round(rate(degree_controls, "accepted_h2"), 6),
        "degree_matched_full_acceptance_rate": round(rate(degree_controls, "accepted_full"), 6),
        "prefix_divergent_h1_acceptance_rate": round(rate(prefix_controls, "accepted_h1"), 6),
        "prefix_divergent_h2_acceptance_rate": round(rate(prefix_controls, "accepted_h2"), 6),
        "prefix_divergent_full_acceptance_rate": round(rate(prefix_controls, "accepted_full"), 6),
        "path_prediction_rate": round(
            sum(case.prediction_available for case in path_controls) / len(path_controls), 6
        ),
        "compression_ratio": round(compression_ratio, 6),
    }

    criteria = {
        "positive_full_acceptance_rate_eq_1": metrics["positive_full_acceptance_rate"] == 1.0,
        "positive_h1_h2_acceptance_rates_eq_1": metrics["positive_h1_acceptance_rate"] == 1.0
        and metrics["positive_h2_acceptance_rate"] == 1.0,
        "degree_matched_full_acceptance_rate_eq_0": metrics["degree_matched_full_acceptance_rate"]
        == 0.0,
        "prefix_divergent_full_acceptance_rate_eq_0": metrics[
            "prefix_divergent_full_acceptance_rate"
        ]
        == 0.0,
        "prefix_divergent_h2_acceptance_rate_le_0_25": metrics[
            "prefix_divergent_h2_acceptance_rate"
        ]
        <= 0.25,
        "path_prediction_rate_eq_0": metrics["path_prediction_rate"] == 0.0,
        "compression_ratio_ge_3": compression_ratio >= 3.0,
    }

    if all(criteria.values()):
        outcome = "supported"
    elif criteria["positive_full_acceptance_rate_eq_1"]:
        outcome = "partially_supported_control_failures"
    else:
        outcome = "falsified_positive_prediction_failed"

    return ExperimentResult(
        motifs={family: motif.key() for family, motif in motifs.items()},
        cases=cases,
        metrics=metrics,
        criteria=criteria,
        outcome=outcome,
    )


def main() -> None:
    result = run_experiment()
    output_path = Path("results/multi_step_completion_experiment_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(output_path)
    print(json.dumps({"outcome": result.outcome, "criteria": result.criteria}, indent=2))


if __name__ == "__main__":
    main()
