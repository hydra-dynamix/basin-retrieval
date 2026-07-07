"""Two-stage coarse-to-fine topology recollection experiment.

Stage 1 uses a coarse representation to preserve recurrence and retrieve broad
compatible continuation families. Stage 2 uses a finer representation only
inside that coarse-compatible region to reduce false answers and candidate sets.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from ldgr_dataset_benchmark import discover_ldgr_dbs
from recurrence_topology_experiment import canonical_signature
from representation_granularity_sweep import event_tokens_for_mode

DEFAULT_CORPUS = Path("/mnt/nas/data/ldgr/benchmarks/splits/benchmarks")


@dataclass(frozen=True)
class AlignedWindow:
    tokens_by_mode: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class QueryCase:
    window: AlignedWindow
    is_repeated: bool


@dataclass(frozen=True)
class RetrievalMetrics:
    strategy: str
    train_windows: int
    query_count: int
    answered: int
    hits: int
    false_answers: int
    abstained: int
    good_abstentions: int
    bad_abstentions: int
    coverage: float
    hit_rate_when_answered: float
    mean_stage1_candidate_set_size: float
    mean_final_candidate_set_size: float
    utility_per_query: float


@dataclass(frozen=True)
class TwoStageSweepResult:
    corpus: str
    min_len: int
    max_len: int
    stride: int
    stage1_bound: int
    stage2_bound: int
    candidate_cost: float
    strategies: tuple[RetrievalMetrics, ...]


def aligned_windows(
    corpus: Path,
    modes: tuple[str, ...],
    *,
    min_len: int,
    max_len: int,
    stride: int,
) -> list[AlignedWindow]:
    dbs, _existing, _missing = discover_ldgr_dbs([corpus])
    out: list[AlignedWindow] = []
    for db in dbs:
        tokens_by_mode = {mode: event_tokens_for_mode(db, mode) for mode in modes}
        if not tokens_by_mode or not all(tokens_by_mode.values()):
            continue
        token_count = min(len(tokens) for tokens in tokens_by_mode.values())
        for length in range(min_len, max_len + 1):
            if token_count < length:
                continue
            for start in range(0, token_count - length + 1, stride):
                record = {
                    mode: tokens[start : start + length] for mode, tokens in tokens_by_mode.items()
                }
                # Keep only recurrent-topology windows; mirrors the main benchmark.
                if len(set(record[modes[0]])) < len(record[modes[0]]):
                    out.append(AlignedWindow(record))
    return out


def split_cases(
    windows: list[AlignedWindow], group_mode: str, *, novel_limit: int = 1000
) -> tuple[list[AlignedWindow], list[QueryCase]]:
    groups: dict[str, list[AlignedWindow]] = defaultdict(list)
    for window in windows:
        groups[canonical_signature(window.tokens_by_mode[group_mode]).key()].append(window)

    train: list[AlignedWindow] = []
    repeated_queries: list[QueryCase] = []
    singleton_windows: list[AlignedWindow] = []
    for group in groups.values():
        if len(group) >= 3:
            repeated_queries.append(QueryCase(group[0], True))
            train.extend(group[1:])
        elif len(group) == 1:
            singleton_windows.append(group[0])
            train.extend(group)
        else:
            train.extend(group)

    random.Random(23).shuffle(singleton_windows)
    novel_queries = [QueryCase(window, False) for window in singleton_windows[:novel_limit]]
    queries = repeated_queries + novel_queries
    random.Random(31).shuffle(queries)
    return train, queries


def _prefix_suffix(tokens: tuple[str, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    prefix_len = max(2, len(tokens) // 2)
    signature = canonical_signature(tokens)
    return signature.trace[:prefix_len], signature.trace[prefix_len:]


def build_single_index(
    train: list[AlignedWindow], mode: str
) -> dict[tuple[int, ...], Counter[tuple[int, ...]]]:
    index: dict[tuple[int, ...], Counter[tuple[int, ...]]] = defaultdict(Counter)
    for window in train:
        prefix, suffix = _prefix_suffix(window.tokens_by_mode[mode])
        index[prefix][suffix] += 1
    return index


def build_two_stage_index(
    train: list[AlignedWindow], stage1_mode: str, stage2_mode: str
) -> dict[tuple[int, ...], dict[tuple[int, ...], Counter[tuple[int, ...]]]]:
    index: dict[tuple[int, ...], dict[tuple[int, ...], Counter[tuple[int, ...]]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    for window in train:
        stage1_prefix, stage1_suffix = _prefix_suffix(window.tokens_by_mode[stage1_mode])
        stage2_prefix, stage2_suffix = _prefix_suffix(window.tokens_by_mode[stage2_mode])
        # The query uses the fine prefix at stage 2, but the coarse suffix gates
        # which fine suffixes are allowed to survive.
        combined_prefix = stage1_prefix + (-1,) + stage2_prefix
        index[combined_prefix][stage1_suffix][stage2_suffix] += 1
    return index


def _top_suffixes(counter: Counter[tuple[int, ...]], bound: int) -> tuple[tuple[int, ...], ...]:
    ranked = tuple(suffix for suffix, _support in counter.most_common())
    return ranked if len(ranked) <= bound else ()


def evaluate_single(
    train: list[AlignedWindow],
    queries: list[QueryCase],
    *,
    mode: str,
    bound: int,
    candidate_cost: float,
) -> RetrievalMetrics:
    index = build_single_index(train, mode)
    return _evaluate(
        strategy=mode,
        train_count=len(train),
        queries=queries,
        candidate_cost=candidate_cost,
        candidate_fn=lambda case: (
            (),
            _top_suffixes(
                index.get(_prefix_suffix(case.window.tokens_by_mode[mode])[0], Counter()), bound
            ),
        ),
        expected_mode=mode,
    )


def evaluate_two_stage(
    train: list[AlignedWindow],
    queries: list[QueryCase],
    *,
    stage1_mode: str,
    stage2_mode: str,
    stage1_bound: int,
    stage2_bound: int,
    candidate_cost: float,
) -> RetrievalMetrics:
    stage1_index = build_single_index(train, stage1_mode)
    stage2_index = build_two_stage_index(train, stage1_mode, stage2_mode)

    def candidates(
        case: QueryCase,
    ) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
        stage1_prefix, _stage1_expected = _prefix_suffix(case.window.tokens_by_mode[stage1_mode])
        stage2_prefix, _stage2_expected = _prefix_suffix(case.window.tokens_by_mode[stage2_mode])
        stage1_candidates = _top_suffixes(stage1_index.get(stage1_prefix, Counter()), stage1_bound)
        if not stage1_candidates:
            return (), ()
        combined_prefix = stage1_prefix + (-1,) + stage2_prefix
        by_coarse_suffix = stage2_index.get(combined_prefix, {})
        fine_counter: Counter[tuple[int, ...]] = Counter()
        for coarse_suffix in stage1_candidates:
            fine_counter.update(by_coarse_suffix.get(coarse_suffix, Counter()))
        fine_candidates = _top_suffixes(fine_counter, stage2_bound)
        return stage1_candidates, fine_candidates

    return _evaluate(
        strategy=f"{stage1_mode}->{stage2_mode}",
        train_count=len(train),
        queries=queries,
        candidate_cost=candidate_cost,
        candidate_fn=candidates,
        expected_mode=stage2_mode,
    )


def _evaluate(
    *,
    strategy: str,
    train_count: int,
    queries: list[QueryCase],
    candidate_cost: float,
    candidate_fn,
    expected_mode: str,
) -> RetrievalMetrics:
    answered = hits = false_answers = abstained = good_abstentions = bad_abstentions = 0
    stage1_total = final_total = 0
    utility = 0.0
    for case in queries:
        stage1_candidates, final_candidates = candidate_fn(case)
        _prefix, expected_suffix = _prefix_suffix(case.window.tokens_by_mode[expected_mode])
        stage1_total += len(stage1_candidates) if stage1_candidates else len(final_candidates)
        if not final_candidates:
            abstained += 1
            if case.is_repeated:
                bad_abstentions += 1
                utility -= 0.25
            else:
                good_abstentions += 1
            continue
        answered += 1
        final_total += len(final_candidates)
        utility -= candidate_cost * len(final_candidates)
        if case.is_repeated and expected_suffix in final_candidates:
            hits += 1
            utility += 1.0
        else:
            false_answers += 1
            utility -= 0.5
    return RetrievalMetrics(
        strategy=strategy,
        train_windows=train_count,
        query_count=len(queries),
        answered=answered,
        hits=hits,
        false_answers=false_answers,
        abstained=abstained,
        good_abstentions=good_abstentions,
        bad_abstentions=bad_abstentions,
        coverage=round(answered / len(queries), 6) if queries else 0.0,
        hit_rate_when_answered=round(hits / answered, 6) if answered else 0.0,
        mean_stage1_candidate_set_size=round(stage1_total / len(queries), 6) if queries else 0.0,
        mean_final_candidate_set_size=round(final_total / answered, 6) if answered else 0.0,
        utility_per_query=round(utility / len(queries), 6) if queries else 0.0,
    )


def run_sweep(
    corpus: Path = DEFAULT_CORPUS,
    *,
    min_len: int = 30,
    max_len: int = 36,
    stride: int = 6,
    stage1_bound: int = 100,
    stage2_bound: int = 100,
    candidate_cost: float = 0.005,
) -> TwoStageSweepResult:
    modes = ("entity", "coarse", "refined", "command_refined", "artifact_ext_refined")
    records = aligned_windows(corpus, modes, min_len=min_len, max_len=max_len, stride=stride)
    train, queries = split_cases(records, "refined")
    strategies: list[RetrievalMetrics] = []
    for mode in modes:
        strategies.append(
            evaluate_single(
                train, queries, mode=mode, bound=stage2_bound, candidate_cost=candidate_cost
            )
        )
    for stage1 in ("entity", "coarse"):
        for stage2 in ("refined", "command_refined", "artifact_ext_refined"):
            strategies.append(
                evaluate_two_stage(
                    train,
                    queries,
                    stage1_mode=stage1,
                    stage2_mode=stage2,
                    stage1_bound=stage1_bound,
                    stage2_bound=stage2_bound,
                    candidate_cost=candidate_cost,
                )
            )
    return TwoStageSweepResult(
        corpus=str(corpus),
        min_len=min_len,
        max_len=max_len,
        stride=stride,
        stage1_bound=stage1_bound,
        stage2_bound=stage2_bound,
        candidate_cost=candidate_cost,
        strategies=tuple(strategies),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--output", type=Path, default=Path("results/two_stage_granularity_sweep.json")
    )
    args = parser.parse_args()
    result = run_sweep(args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(args.output)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
