# Reproducing the Results

Every number in the paper traces to a specific experiment and result file. This
document maps claims to evidence and states exactly how to reproduce each.

All experiments use seed `20260706` and require only Python 3.12 (standard
library). The ecphory-2 project's venv works: `../ecphory-2/.venv/bin/python`.

## Claim → Evidence Map

### Claim 1: 34× compression, 1.0 inclusion (synthetic relational families)

**Paper section:** §7.1, first row of the compression table.

| | |
|---|---|
| experiment | `code/basin_retrieval/bench_relaxation.py` |
| result | `results/basin_results.json` |
| metric | `aggregate.typed.bundle_reduction_gmean = 34.0`, `inclusion_rate = 1.0` |
| self-contained | **yes** — uses the synthetic generator, no external data |
| reproduce | `python3 code/basin_retrieval/bench_relaxation.py` |

Corpus: 20 disjoint generated families + 10 polysemy bases (prefix-shared,
divergent continuations), 68 stored items. The operator indexes instances
`0..k−2` of each family and queries the held-out instance `k−1`.

### Claim 2: 32× compression, 1.0 clean accuracy (LDGR project history)

**Paper section:** §7.1, second row of the compression table.

| | |
|---|---|
| experiment | `code/behavioral_relevance/bench_behavioral_relevance.py` |
| result | `results/behavioral_relevance_results.json` |
| metric | `clean_baseline.bundle_reduction = 32.0`, `clean_baseline.clean_accuracy = 1.0` |
| self-contained | **yes** — reads `data/ldgr_history/{observations,artifacts}.jsonl` |
| reproduce | `python3 code/behavioral_relevance/bench_behavioral_relevance.py` |

The JSONL snapshots are complete, field-faithful extractions of the source
LDGR SQLite database (17 observations, 40 artifacts, 0 field mismatches).

### Claim 3: 0.80 content-graph vs 0.0 node-bag (rewired decoy control)

**Paper section:** §8, the same-node rewired decoy table.

| | |
|---|---|
| experiment | `code/payload_graph/bench_payload_graph_refinement.py` |
| result | `results/payload_graph_refinement_results.json` |
| metric | `summary.real_plus_rewired_decoys.*.content_graph.top1_accuracy = 0.80`; `node_bag = 0.0` |
| self-contained | **yes** — builds on the behavioral corpus |
| reproduce | `python3 code/payload_graph/bench_payload_graph_refinement.py` |

### Claim 4: 23.9× compression, 0.88 coverage (synthetic motifs)

**Paper section:** §7.1, third row of the compression table.

| | |
|---|---|
| experiment | `code/topology/set_valued_prediction_experiment.py` |
| result | `results/topology/set_valued_prediction_analysis.md` (evidence of record) |
| metric | N=3 suffix set: coverage 0.88, inclusion 1.0, compression 23.9× |
| self-contained | **yes** — synthetic motif families |
| reproduce | `cd code/topology && python3 set_valued_prediction_experiment.py` |

### Claim 5: 554× compression, 1.0 coverage (temporal traces, long window)

**Paper section:** §7.1, fourth row of the compression table.

| | |
|---|---|
| experiment | `code/topology/ldgr_dataset_benchmark.py` (called via `two_stage_granularity_experiment.py`) |
| result | `results/topology/nas_benchmarks_long_window_rerun.json`, `results/topology/final_findings.md` |
| metric | token_mode=refined, window=30..36, stride=6: coverage 1.0, reduction 554× |
| self-contained | **partial** — requires LDGR benchmark dbs |
| reproduce | see "Topology experiments" below |

### Claim 6: Semantic labels fragment neighborhoods (granularity sweep)

**Paper section:** §5, the granularity table (0.948 / 0.909 / 0.691).

| | |
|---|---|
| experiment | `code/topology/two_stage_granularity_experiment.py` |
| result | `results/topology/representation_granularity_sweep.json`, `.md` |
| metric | entity 0.948, phase_refined 0.909, full_categorical 0.691 (repeated-only utility) |
| self-contained | **partial** — requires LDGR benchmark dbs |

### Claim 7: Naive union fragments neighborhoods (0.567)

**Paper section:** §5, the dual-lookup control table.

| | |
|---|---|
| experiment | ecphory-2 `run_promoted_dual_lookup_control_experiment.py` (not ported; deep dependency chain) |
| result | `results/dual_lookup/promoted-dual-lookup-control.json` (evidence of record) |
| metric | naive union utility 0.567 vs labeled-only 0.700, structural 1.000, agreement-gated 1.000 |
| self-contained | **no** — included as result-of-record; the experiment lives in the ecphory-2 lineage |

## Topology experiments (Claims 5–6)

The 554× and granularity results use LDGR event-log benchmark databases. A
28-db subset is bundled in `data/ldgr_benchmarks/`. The full 128-db corpus is
on Hugging Face.

```bash
# set the corpus path (defaults to the NAS mount used during development)
export LDGR_BENCHMARK_CORPUS="$(pwd)/data/ldgr_benchmarks"

cd code/topology
python3 two_stage_granularity_experiment.py --corpus "$LDGR_BENCHMARK_CORPUS"
python3 ldgr_dataset_benchmark.py --corpus "$LDGR_BENCHMARK_CORPUS"
```

If the bundled subset does not contain all dbs the sweep expects, download the
full corpus from Hugging Face (`Bakobiibizo/basin-retrieval`, `ldgr_benchmarks/`).

## Data provenance

### `data/ldgr_history/`

Extracted from the source project's LDGR SQLite database
(`episteme/.ldgr/ldgr.db`). The extraction is complete: all 17 observations and
40 artifacts are present with zero field mismatches against the source. The
behavioral experiment reads these JSONL files directly — no database required.

### `data/ldgr_benchmarks/`

LDGR event-log benchmark databases used by the topology experiments. These are
real workflow event logs from LDGR-tracked software-development runs, tokenized
into content-safe categories (e.g. `observation:add:failure`,
`artifact:add:report`, `decision:record:continue`) — no raw text.

## Archived state

```text
GitHub:   https://github.com/hydra-dynamix/basin-retrieval
HF data:  https://huggingface.co/datasets/Bakobiibizo/basin-retrieval
```
