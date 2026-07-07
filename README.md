# Basin Retrieval: Structural Compatibility as a First-Stage Search-Space Compression Operator

This repository contains the code, data, and results for the paper *Basin
Retrieval: Structural Compatibility as a First-Stage Search-Space Compression
Operator*.

The paper makes one claim: a semantically indifferent structural retrieval
operator can compress a relational search space into a bounded basin of
compatible candidates while preserving the target, leaving identification to a
downstream stage. On held-out relational data it achieves **34× compression
with perfect target inclusion (1.0)**, on project-history content **32×**, and
on temporal traces up to **554×**, again with perfect inclusion.

## Repository layout

```
basin-retrieval/
├── paper/
│   └── basin-retrieval.md            the paper
├── code/
│   ├── core/                         the encoding + retrieval operator
│   │   ├── signature.py              canonical first-occurrence recurrence signatures
│   │   ├── graph_dataset.py          typed relational graph data model
│   │   ├── generator.py              synthetic relational-family generator
│   │   ├── relaxation.py             prefix-consistency basin retrieval
│   │   ├── matcher_relaxation.py     DP/LCS alignment
│   │   └── identity_regimes.py       identity regime comparisons
│   ├── basin_retrieval/              → 34× compression result (self-contained)
│   ├── behavioral_relevance/         → 32× compression on LDGR history
│   ├── payload_graph/                → 0.80 content-graph vs node-bag control
│   └── topology/                     → 23.9× / 554× / granularity-sweep results
├── data/
│   ├── ldgr_history/                 extracted LDGR observations + artifacts (JSONL)
│   └── ldgr_benchmarks/              LDGR event-log dbs (for topology experiments)
├── results/                          result JSONs (primary evidence)
│   ├── topology/                     554× / granularity-sweep evidence of record
│   └── dual_lookup/                  0.567 naive-union evidence of record
└── reports/                          human-readable analysis
```

## How LDGR was used in this research

LDGR is a minimal durable investigation loop backed by SQLite — a tool our team
uses to record research as permanent event logs. In this paper it played two
distinct and deliberate roles, and both are worth stating because they are what
keep the 32× and 554× results grounded in real rather than synthetic content.

### 1. The project's own history as memory content (`data/ldgr_history/`)

The research that produced this paper was itself run through LDGR. Every
observation (hypothesis, finding), artifact (code file, report, result JSON),
and decision (pivot, validation, stop) was recorded as it happened. We then
used that self-recorded history as the memory content for the 32× behavioral
result and the 0.80 content-graph control.

This is deliberate and a little recursive: the substrate retrieves the
project's own recorded findings. It tests the operator on natural relational
content — real observations, real artifact descriptions, real report chunks —
rather than on generated families. The corpus is 32 items stratified by topic
(deletion, matcher, identity, noise, polysemy, typed, phase 0), drawn from 17
observations and 40 artifacts.

The `data/ldgr_history/` directory is a complete, field-faithful extraction of
the source LDGR database into JSONL — 17 observations and 40 artifacts with
zero field mismatches against the source. The behavioral experiment reads
these directly; no database or LDGR installation is required to reproduce the
32× result.

### 2. LDGR event logs as a temporal-trace corpus (`data/ldgr_benchmarks/`)

For the temporal-trace results (23.9× on synthetic motifs, 554× on long-window
workflow logs), we used LDGR event logs from many separate LDGR-tracked
software-development runs. LDGR records every workflow event as a row
(`entity_type:event_type` over `observation`, `artifact`, `decision`, `run`).

We do not feed raw text into the operator. We tokenize each event into a
coarse, content-safe category tag — for example `observation:add:failure`,
`artifact:add:report`, `decision:record:continue`, `run:end:pass`. The
coarsening is rule-based: observations are categorized by keywords in their
body (failure / constraint / result / implementation / data / note), artifacts
by their path (validator / report / result / implementation / patch), decisions
by their rationale (stop / pivot / blocker / validated / completed), runs by
status (pass / fail / partial). These tagged events are then windowed into
state-transition sequences and indexed by the same canonical recurrence
signature used for the relational graph.

This tokenization choice is itself part of the paper's thesis. The finest
categorical detail (the raw text of each observation) would fragment the
recurrence basins; coarse category tags preserve recurrence density. That is
the granularity sweep result stated the other way around: coarse tokens gave
best reuse (0.948), full categorical detail the worst (0.691).

`data/ldgr_benchmarks/` bundles 28 of these event-log databases. The full
128-db corpus is available on Hugging Face.

### Why both roles matter

Together the two roles cover the two regimes the paper needs to defend: the
behavioral result shows the operator compresses natural relational content
(real project history); the temporal result shows it scales on genuinely
sequential, high-volume data. Neither uses synthetic families alone. LDGR is
what lets us claim the compression envelope holds on real workloads rather
than only on the generated corpus.

## Quick reproduction

Python 3.12, no external dependencies beyond the standard library.

```bash
# 34× compression on synthetic relational families (self-contained, ~5s)
python3 code/basin_retrieval/bench_relaxation.py

# 32× compression on LDGR project history (self-contained via JSONL snapshot, ~10s)
python3 code/behavioral_relevance/bench_behavioral_relevance.py

# content-graph vs node-bag on rewired decoys (self-contained, ~20s)
python3 code/payload_graph/bench_payload_graph_refinement.py

# 23.9× synthetic motif compression (self-contained)
python3 code/topology/set_valued_prediction_experiment.py
```

Seed for all experiments: `20260706`.

See `REPRODUCING.md` for the full claim-to-evidence map, including which
experiments are fully self-contained and which require the LDGR benchmark
corpus.

## What this is not

This is a compression operator, not a semantic retrieval system, reasoning
engine, or memory architecture. It does not rank, does not interpret content,
and does not claim to be a complete retrieval solution. It compresses the
candidate space so a downstream stage can afford to process what survives.

## License

MIT.
