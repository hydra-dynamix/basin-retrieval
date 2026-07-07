# Cost-Aware Adaptive Retrieval Follow-up

## Questions Answered

This follow-up addressed the remaining research questions from the actual-use feedback loop:

1. Can retrieval bounds be selected by utility/cost rather than fixed operating mode?
2. What happens when repeated held-out queries are mixed with genuinely novel queries?
3. Does the long-window finding hold across token modes?
4. Can prefix indexing preserve results while reducing query latency?
5. Can the Pi extension run the benchmark path against the benchmark corpus?

## Setup

Corpus:

```text
/mnt/nas/data/ldgr/benchmarks/splits/benchmarks
```

Main long-window configuration:

```text
token_mode=refined
window=30..36
stride=6
min_support=2
bounds={5,10,15,20,25,35,50,75,100}
```

Raw result:

```text
results/cost_aware_adaptive_retrieval.json
```

## 1. Cost-Aware Bound Selection

A simple utility hill-climber over candidate bounds selected different bounds depending on downstream candidate-scoring cost:

| candidate cost | selected bound | oracle bound | utility/query | regret/query |
|---:|---:|---:|---:|---:|
| 0.005 | 100 | 100 | 0.729371 | 0.0 |
| 0.025 | 35 | 35 | 0.547832 | 0.0 |
| 0.1 | 10 | 10 | 0.106217 | 0.0 |

Conclusion: adaptive retrieval should not be a fixed conservative/balanced/exploratory switch. It should select a candidate bound from an explicit cost/utility model.

## 2. Mixed Repeated + Novel Workload

The previous replay benchmark only held out repeated motifs, so every abstention was effectively bad. This experiment added singleton/novel windows as negative workload.

At cheap candidate scoring (`candidate_cost=0.005`):

| bound | coverage | hits | false answers | good abstentions | bad abstentions | utility/query |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.624827 | 3045 | 111 | 889 | 1006 | 0.520278 |
| 25 | 0.775886 | 3744 | 175 | 825 | 307 | 0.674326 |
| 50 | 0.819442 | 3927 | 212 | 788 | 124 | 0.709062 |
| 100 | 0.846961 | 4051 | 227 | 773 | 0 | 0.729371 |

Conclusion: novel prefixes introduce real false-answer pressure, but the long-window topology memory still provides positive utility. High bounds remain best when downstream scoring is cheap, though medium bounds become attractive as scoring cost rises.

## 3. Long-Window Token Mode Sweep

Long-window recollection held across token modes:

| token mode | query count | best bound | coverage | mean set size | utility/query |
|---|---:|---:|---:|---:|---:|
| entity | 3668 | 100 | 1.0 | 10.475736 | 0.947621 |
| coarse | 3640 | 100 | 1.0 | 10.937912 | 0.945310 |
| refined | 4051 | 100 | 1.0 | 11.522587 | 0.942387 |

Conclusion: long-window topology is robust to token granularity. Entity/coarse slightly outperform refined by utility because they produce denser recurrence and smaller candidate sets, while refined yields more held-out queries.

## 4. Prefix Indexing

A prefix candidate index produced identical candidate suffix sets and much faster query time on a 1000-query sample:

```text
motifs:                   6394
scan query time:          0.852727 s
indexed query time:       0.011754 s
speedup:                  72.549046x
identical candidate sets: true
```

Conclusion: prefix indexing is the right implementation path before larger corpora or Pi runtime use.

## 5. Pi Extension Smoke

Updated `.pi/extensions/ldgr-topology.ts` and `src/ldgr_dataset_benchmark.py` so the extension can target the NAS benchmark split with long-window defaults.

Smoke command:

```bash
pi --offline --no-session \
  --extension .pi/extensions/ldgr-topology.ts \
  --no-builtin-tools \
  --tools ldgr_topology_benchmark \
  -p "/ldgr-topology-benchmark"
```

Output file:

```text
results/pi_ldgr_topology_benchmark.json
```

Observed metrics:

```text
db_count:                 128
query_sequences:          4051
covered_queries:          4051
true_inclusion_rate:      1.0
mean_candidate_set_size:  11.522587
search_reduction_factor:  554.910108
```

Conclusion: project-local extension loading and slash-command benchmark invocation work non-interactively in the Pi harness.

## Final Interpretation

The remaining questions now have clear answers:

- **Adaptive policy:** should be cost-aware bound selection.
- **Novel workload:** introduces false answers, but long-window recollection remains useful.
- **Token mode:** long windows work across token modes; coarser tokens may be preferable for compact recollection.
- **Scalability:** prefix indexing preserves exact outputs and gives large speedup.
- **Pi integration:** smoke test passed and the extension can run the long-window benchmark.

## Recommended Next Engineering Work

1. Promote prefix indexing into `TopologyConstraintMemory` or a production companion index.
2. Replace current `adaptive` mode with a cost-aware policy object.
3. Add `ldgr_topology_recollect` to the Pi extension for single-prefix recollection.
4. Package the benchmark corpus + extension into the handoff harness.
