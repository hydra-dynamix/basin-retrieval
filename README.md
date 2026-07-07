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
