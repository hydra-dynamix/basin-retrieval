"""Run topology constraint memory on LDGR SQLite databases.

LDGR event logs are treated as temporal state-transition sequences. Event symbols
are intentionally coarse (`entity_type:event_type`) so the topology layer sees
workflow structure rather than project-specific IDs or text.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from topology_constraint_memory import TopologyConstraintMemory

DEFAULT_ROOTS = (
    Path("/mnt/d/apps/benchmarks"),
    Path("/mnt/d/apps/ldgr-bench"),
    Path("/mnt/e/apps/ldgr-bench"),
    Path("/mnt/e/apps/benchmarks"),
    Path.home() / "repos/benchmarks2",
    Path.home() / "repos/benchmarks",
    Path.home() / "repos/ldgr-bench",
    Path.home() / "repos",
)


@dataclass(frozen=True)
class LdgrDatasetStats:
    db_count: int
    existing_requested_roots: tuple[str, ...]
    missing_requested_roots: tuple[str, ...]
    extracted_sequences: int
    training_sequences: int
    query_sequences: int
    consolidated_motifs: int
    covered_queries: int
    abstained_queries: int
    true_inclusion_rate: float
    mean_candidate_set_size: float
    unconstrained_scores: int
    constrained_scores: int
    search_reduction_factor: float
    top_event_tokens: tuple[tuple[str, int], ...]


def _looks_like_ldgr_db(path: Path) -> bool:
    try:
        con = sqlite3.connect(path)
        try:
            row = con.execute(
                "select 1 from sqlite_master where type = 'table' and name = 'event_log'"
            ).fetchone()
            return row is not None
        finally:
            con.close()
    except sqlite3.Error:
        return False


def discover_ldgr_dbs(
    roots: Iterable[Path],
) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
    existing: list[Path] = []
    missing: list[Path] = []
    candidates: set[Path] = set()
    for root in roots:
        expanded = root.expanduser()
        if not expanded.exists():
            missing.append(expanded)
            continue
        existing.append(expanded)
        if expanded.is_file() and (expanded.name == "ldgr.db" or expanded.suffix == ".db"):
            candidates.add(expanded)
        else:
            candidates.update(expanded.rglob(".ldgr/ldgr.db"))
            candidates.update(expanded.rglob("*.db"))
    dbs = {path for path in candidates if _looks_like_ldgr_db(path)}
    return tuple(sorted(dbs)), tuple(existing), tuple(missing)


def _category_from_text(text: str, rules: dict[str, tuple[str, ...]], default: str) -> str:
    lowered = text.lower()
    for category, needles in rules.items():
        if any(needle in lowered for needle in needles):
            return category
    return default


def _observation_category(con: sqlite3.Connection, entity_id: int) -> str:
    row = con.execute("select body from observation where id = ?", (entity_id,)).fetchone()
    body = "" if row is None else str(row[0])
    return _category_from_text(
        body,
        {
            "failure": ("fail", "error", "exception", "broken", "regression"),
            "constraint": ("constraint", "threshold", "must", "cannot", "boundary"),
            "result": ("result", "metric", "coverage", "rate", "supported", "passed"),
            "implementation": ("implemented", "built", "added", "updated", "prototype"),
            "data": ("dataset", "data", "extracted", "benchmark"),
        },
        "note",
    )


def _artifact_category(con: sqlite3.Connection, entity_id: int) -> str:
    row = con.execute(
        "select path, description from artifact where id = ?", (entity_id,)
    ).fetchone()
    text = "" if row is None else f"{row[0]} {row[1]}"
    return _category_from_text(
        text,
        {
            "validator": ("test", "validation", "validator", "pytest", "check"),
            "report": ("report", "analysis", "meta", ".md"),
            "result": ("result", "metrics", ".json"),
            "implementation": ("implementation", "src/", ".py", "script"),
            "patch": ("patch", "diff"),
        },
        "other",
    )


def _decision_category(con: sqlite3.Connection, entity_id: int) -> str:
    row = con.execute(
        "select outcome, rationale from decision where id = ?", (entity_id,)
    ).fetchone()
    if row is None:
        return "unknown"
    outcome, rationale = str(row[0]), str(row[1])
    if outcome == "stop":
        return "stop"
    return _category_from_text(
        rationale,
        {
            "pivot": ("pivot", "refined", "shift", "instead", "rather than"),
            "blocker": ("block", "blocked", "missing", "unmounted", "waiting"),
            "validated": ("validated", "passed", "supported"),
            "completed": ("completed", "finished", "done"),
        },
        outcome,
    )


def _run_category(payload_json: str) -> str:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        payload = {}
    status = str(payload.get("status", ""))
    if status in {"success", "passed", "pass"}:
        return "pass"
    if status in {"failed", "failure", "fail", "error"}:
        return "fail"
    if status == "partial":
        return "partial"
    return status or "unknown"


def _event_token(
    con: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    event_type: str,
    payload_json: str,
    mode: str = "refined",
) -> str:
    if mode == "entity":
        return entity_type
    if mode == "coarse":
        return f"{entity_type}:{event_type}"
    if entity_type == "observation" and event_type == "add":
        return f"observation:add:{_observation_category(con, entity_id)}"
    if entity_type == "artifact" and event_type == "add":
        return f"artifact:add:{_artifact_category(con, entity_id)}"
    if entity_type == "decision" and event_type == "record":
        return f"decision:record:{_decision_category(con, entity_id)}"
    if entity_type == "run" and event_type == "finish":
        return f"run:end:{_run_category(payload_json)}"
    return f"{entity_type}:{event_type}"


def event_tokens(db_path: Path, mode: str = "refined") -> tuple[str, ...]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "select entity_type, entity_id, event_type, payload_json from event_log order by id"
        ).fetchall()
        return tuple(
            _event_token(con, str(entity), int(entity_id), str(event), str(payload), mode)
            for entity, entity_id, event, payload in rows
        )
    except sqlite3.Error:
        return ()
    finally:
        con.close()


def windows(
    tokens: tuple[str, ...], *, min_len: int = 5, max_len: int = 12, stride: int = 3
) -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    for length in range(min_len, max_len + 1):
        if len(tokens) < length:
            continue
        for start in range(0, len(tokens) - length + 1, stride):
            window = tokens[start : start + length]
            if len(set(window)) < len(window):
                out.append(window)
    return out


def extract_sequences(
    dbs: Iterable[Path],
    *,
    token_mode: str = "refined",
    min_len: int = 5,
    max_len: int = 12,
    stride: int = 3,
) -> tuple[list[tuple[str, ...]], Counter[str]]:
    sequences: list[tuple[str, ...]] = []
    token_counts: Counter[str] = Counter()
    for db in dbs:
        tokens = event_tokens(db, token_mode)
        token_counts.update(tokens)
        sequences.extend(windows(tokens, min_len=min_len, max_len=max_len, stride=stride))
    return sequences, token_counts


def split_train_query(
    sequences: list[tuple[str, ...]],
) -> tuple[list[tuple[str, ...]], list[tuple[tuple[str, ...], tuple[int, ...]]]]:
    """Hold out one sequence from each repeated canonical motif group."""

    from recurrence_topology_experiment import canonical_signature

    groups: dict[str, list[tuple[str, ...]]] = {}
    for sequence in sequences:
        groups.setdefault(canonical_signature(sequence).key(), []).append(sequence)

    train: list[tuple[str, ...]] = []
    query_full: list[tuple[str, ...]] = []
    for grouped in groups.values():
        if len(grouped) >= 3:
            query_full.append(grouped[0])
            train.extend(grouped[1:])
        else:
            train.extend(grouped)

    queries: list[tuple[tuple[str, ...], tuple[int, ...]]] = []
    for sequence in query_full:
        prefix_len = max(2, len(sequence) // 2)
        signature = canonical_signature(sequence)
        queries.append((sequence[:prefix_len], signature.trace[prefix_len:]))
    return train, queries


def run_benchmark(
    roots: Iterable[Path] = DEFAULT_ROOTS,
    *,
    min_support: int = 2,
    max_candidates: int = 10,
    token_mode: str = "refined",
    min_len: int = 5,
    max_len: int = 12,
    stride: int = 3,
) -> LdgrDatasetStats:
    dbs, existing, missing = discover_ldgr_dbs(roots)
    sequences, token_counts = extract_sequences(
        dbs, token_mode=token_mode, min_len=min_len, max_len=max_len, stride=stride
    )
    train, queries = split_train_query(sequences)
    memory = TopologyConstraintMemory(min_support=min_support)
    memory.observe_many(train)
    consolidated = memory.consolidated_motifs()

    included = 0
    constrained = 0
    abstained = 0
    for prefix, expected_suffix in queries:
        result = memory.query(prefix, max_candidates=max_candidates)
        if result.abstained:
            abstained += 1
            continue
        constrained += result.set_size
        if any(candidate.suffix == expected_suffix for candidate in result.candidates):
            included += 1
    covered = len(queries) - abstained
    unconstrained = len(consolidated) * len(queries)
    return LdgrDatasetStats(
        db_count=len(dbs),
        existing_requested_roots=tuple(str(path) for path in existing),
        missing_requested_roots=tuple(str(path) for path in missing),
        extracted_sequences=len(sequences),
        training_sequences=len(train),
        query_sequences=len(queries),
        consolidated_motifs=len(consolidated),
        covered_queries=covered,
        abstained_queries=abstained,
        true_inclusion_rate=round(included / covered, 6) if covered else 0.0,
        mean_candidate_set_size=round(constrained / covered, 6) if covered else 0.0,
        unconstrained_scores=unconstrained,
        constrained_scores=constrained,
        search_reduction_factor=round(unconstrained / constrained, 6) if constrained else 0.0,
        top_event_tokens=tuple(token_counts.most_common(20)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/ldgr_dataset_benchmark.json"))
    parser.add_argument(
        "--root", action="append", type=Path, help="LDGR DB/corpus root; may be repeated"
    )
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--token-mode", choices=("entity", "coarse", "refined"), default="refined")
    parser.add_argument("--min-len", type=int, default=5)
    parser.add_argument("--max-len", type=int, default=12)
    parser.add_argument("--stride", type=int, default=3)
    args = parser.parse_args()
    result = run_benchmark(
        roots=args.root or DEFAULT_ROOTS,
        min_support=args.min_support,
        max_candidates=args.max_candidates,
        token_mode=args.token_mode,
        min_len=args.min_len,
        max_len=args.max_len,
        stride=args.stride,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(args.output)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
