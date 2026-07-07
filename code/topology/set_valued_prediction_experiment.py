"""Set-valued suffix prediction coverage/specificity tradeoff experiment."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from generalized_trajectory_experiment import (
    GeneratedMotif,
    divergent_candidate,
    generate_motifs,
    prefix_depths,
    suffix_predictions,
)

LIMITS = (1, 2, 3, 5)


@dataclass(frozen=True)
class LimitResult:
    limit: int
    coverage: float
    positive_inclusion_rate: float
    control_full_acceptance_rate: float
    mean_suffix_set_size: float
    mean_observation_fraction: float
    mean_remaining_prediction_length: float
    compression_factor: float
    utility_score: float
    criteria_passed: bool


@dataclass(frozen=True)
class ExperimentResult:
    motif_count: int
    limit_results: tuple[LimitResult, ...]
    best_supported_limit: int | None
    criteria: dict[str, bool]
    outcome: str


def earliest_prefix_for_limit(
    motif: GeneratedMotif, motifs: Sequence[GeneratedMotif], limit: int
) -> int | None:
    for prefix_length in range(1, len(motif.trace)):
        if len(suffix_predictions(motif.trace[:prefix_length], motifs)) <= limit:
            return prefix_length
    return None


def positive_included(
    motif: GeneratedMotif, motifs: Sequence[GeneratedMotif], prefix_length: int
) -> bool:
    true_suffix = motif.trace[prefix_length:]
    return true_suffix in suffix_predictions(motif.trace[:prefix_length], motifs)


def control_acceptance_for_motif(
    motif: GeneratedMotif, motifs: Sequence[GeneratedMotif], prefix_length: int
) -> tuple[int, int]:
    accepted = 0
    total = 0
    prefix = motif.trace[:prefix_length]
    suffix = motif.trace[prefix_length:]
    # Include direct divergences from the selected prefix and from canonical test depths when possible.
    candidate_prefixes = [(prefix, suffix)]
    for depth in prefix_depths(motif.trace):
        if depth != prefix_length:
            candidate_prefixes.append((motif.trace[:depth], motif.trace[depth:]))
    for control_prefix, control_suffix in candidate_prefixes:
        for mode in ("diverge_immediate", "diverge_after_h1", "diverge_after_h2"):
            candidate = divergent_candidate(control_prefix, control_suffix, mode)
            if candidate is None or len(candidate) <= prefix_length:
                continue
            if tuple(candidate[:prefix_length]) != prefix:
                continue
            total += 1
            observed_suffix = tuple(candidate[prefix_length:])
            if observed_suffix in suffix_predictions(prefix, motifs):
                accepted += 1
    return accepted, total


def evaluate_limit(limit: int, motifs: Sequence[GeneratedMotif]) -> LimitResult:
    covered: list[tuple[GeneratedMotif, int]] = []
    for motif in motifs:
        prefix_length = earliest_prefix_for_limit(motif, motifs, limit)
        if prefix_length is not None:
            covered.append((motif, prefix_length))

    positive_rate = (
        sum(positive_included(motif, motifs, prefix_length) for motif, prefix_length in covered)
        / len(covered)
        if covered
        else 0.0
    )
    control_accepted = 0
    control_total = 0
    for motif, prefix_length in covered:
        accepted, total = control_acceptance_for_motif(motif, motifs, prefix_length)
        control_accepted += accepted
        control_total += total
    control_rate = control_accepted / control_total if control_total else 0.0
    suffix_sizes = [
        len(suffix_predictions(motif.trace[:prefix_length], motifs))
        for motif, prefix_length in covered
    ]
    observation_fractions = [prefix_length / len(motif.trace) for motif, prefix_length in covered]
    remaining_lengths = [len(motif.trace) - prefix_length for motif, prefix_length in covered]
    coverage = len(covered) / len(motifs)
    mean_suffix_size = mean(suffix_sizes) if suffix_sizes else 0.0
    mean_remaining = mean(remaining_lengths) if remaining_lengths else 0.0
    compression_factor = len(motifs) / mean_suffix_size if mean_suffix_size else 0.0
    utility = coverage * (1.0 - control_rate) * mean_remaining
    passed = (
        coverage >= 0.85
        and positive_rate == 1.0
        and control_rate <= 0.05
        and mean_suffix_size <= limit
        and mean_remaining >= 2.0
    )
    return LimitResult(
        limit=limit,
        coverage=round(coverage, 6),
        positive_inclusion_rate=round(positive_rate, 6),
        control_full_acceptance_rate=round(control_rate, 6),
        mean_suffix_set_size=round(mean_suffix_size, 6),
        mean_observation_fraction=round(mean(observation_fractions), 6)
        if observation_fractions
        else 0.0,
        mean_remaining_prediction_length=round(mean_remaining, 6),
        compression_factor=round(compression_factor, 6),
        utility_score=round(utility, 6),
        criteria_passed=passed,
    )


def run_experiment(motif_count: int = 50) -> ExperimentResult:
    motifs = generate_motifs(motif_count)
    limit_results = tuple(evaluate_limit(limit, motifs) for limit in LIMITS)
    supported = [result for result in limit_results if result.criteria_passed]
    best = min((result.limit for result in supported), default=None)
    criteria = {
        "at_least_one_limit_supported": bool(supported),
        "positive_inclusion_all_limits": all(
            result.positive_inclusion_rate == 1.0 for result in limit_results if result.coverage > 0
        ),
        "strict_uniqueness_not_best_coverage": any(
            result.limit > 1 and result.coverage > limit_results[0].coverage
            for result in limit_results
        ),
    }
    outcome = (
        "supported" if criteria["at_least_one_limit_supported"] else "falsified_tradeoff_failed"
    )
    return ExperimentResult(
        motif_count=len(motifs),
        limit_results=limit_results,
        best_supported_limit=best,
        criteria=criteria,
        outcome=outcome,
    )


def main() -> None:
    result = run_experiment()
    output_path = Path("results/set_valued_prediction_experiment_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(output_path)
    print(json.dumps({"outcome": result.outcome, "best": result.best_supported_limit}, indent=2))


if __name__ == "__main__":
    main()
