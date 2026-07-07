# Final Findings: Topology Constraint Memory / LDGR Recollection

## Bottom Line

The strongest defensible finding is:

> Persistent recurrent topological motifs are useful as an auxiliary, model-free constraint memory. They do not replace learning or reasoning, but they can retrieve bounded sets of structurally compatible workflow continuations and substantially reduce downstream search space.

This should be treated as **recollection / candidate-space compression**, not semantic prediction.

## What Worked

- Simple paths failed, as expected.
- Nontrivial recurrent topology worked once automorphic controls were handled correctly.
- Multi-step suffix prediction distinguished shared-prefix controls in the hand-designed setting.
- Exact unique prediction failed in dense generated libraries, but set-valued retrieval succeeded.
- Dense synthetic libraries retained useful compression and low hard-control acceptance.
- The prototype works on real LDGR event logs.
- Benchmark-only NAS split rerun preserved true continuations for covered queries.

## Actual-Use Feedback Update

A utility-based simulation found that the earlier `8..12` benchmark window was underpowered for recollection. Longer workflow windows gave much stronger bounded continuation retrieval.

Best observed benchmark-only setting:

```text
token_mode=refined
window=30..36
stride=6
max_candidates=100
min_support=2
```

Metrics:

```text
query_sequences:         4051
covered_queries:         4051
coverage:                1.0
true inclusion:          1.0
mean candidate set size: 11.522587
search reduction:        554.910108x
utility/query:           0.942387
```

Main interpretation: topology recollection is much more useful as longer-horizon workflow-state recollection than as very short local event continuation.

Detailed report:

```text
reports/actual_use_feedback_simulation.md
```

## Earlier Benchmark-Only Result

Corpus:

```text
/mnt/nas/data/ldgr/benchmarks/splits/benchmarks
```

Configuration:

```text
token_mode=refined
window=8..12
stride=3
max_candidates=100
min_support=2
```

Metrics:

```text
DBs:                      128
queries:                  2772
covered:                  855
coverage:                 0.308442
true inclusion:           1.0
mean candidate set size:  51.187135
search reduction:         220.987273x
```

High-compression benchmark-only mode:

```text
token_mode=coarse
window=8..12
stride=3
max_candidates=10
coverage:                 0.016987
true inclusion:           1.0
search reduction:         33256x
```

## Corpus Organization

NAS corpus root:

```text
/mnt/nas/data/ldgr/benchmarks
```

Split folders:

```text
/mnt/nas/data/ldgr/benchmarks/splits/benchmarks  # 128 DBs
/mnt/nas/data/ldgr/benchmarks/splits/coding      # 94 DBs
/mnt/nas/data/ldgr/benchmarks/splits/research    # 18 DBs
```

Current project LDGR DB was added back into the corpus at:

```text
/mnt/nas/data/ldgr/benchmarks/dbs/bako__research__topology__ldgr.db
/mnt/nas/data/ldgr/benchmarks/splits/research/dbs__bako__research__topology__ldgr.db
```

Manifests:

```text
/mnt/nas/data/ldgr/benchmarks/nas_manifest.jsonl
/mnt/nas/data/ldgr/benchmarks/split_manifest.jsonl
/mnt/nas/data/ldgr/benchmarks/split_summary.json
```

## Prototype Components

- Memory/index: `src/topology_constraint_memory.py`
- LDGR benchmark: `src/ldgr_dataset_benchmark.py`
- Config sweep: `src/ldgr_configuration_sweep.py`
- Pi extension: `.pi/extensions/ldgr-topology.ts`
- Corpus scripts:
  - `scripts/index_nas_ldgr_dataset.py`
  - `scripts/organize_nas_ldgr_splits.py`
  - `scripts/collect_ldgr_dataset.py`

## Pi Extension

Project-local extension:

```text
.pi/extensions/ldgr-topology.ts
```

Registers:

- `ldgr_topology_benchmark`
- `ldgr_topology_sweep`
- `/ldgr-topology-benchmark`

A handoff for building a proper bundled Pi benchmark harness is in:

```text
docs/pi_extension_benchmark_handoff.md
```

## Cost-Aware / Runtime Follow-up

The remaining research questions were answered in:

```text
reports/cost_aware_adaptive_retrieval.md
```

Key updates:

- Mixed repeated+novel workload remains positive at long windows: bound 100 utility/query `0.729371` with 4051 hits, 227 false answers, and 773 good abstentions.
- Utility-optimal bounds depend on downstream candidate cost: cost `0.005 -> bound 100`, cost `0.025 -> bound 35`, cost `0.1 -> bound 10`.
- Long-window results hold across token modes: entity `0.947621`, coarse `0.945310`, refined `0.942387` utility/query on repeated-only workload.
- Prefix indexing preserved identical candidate sets and improved 1000-query lookup from `0.852727s` to `0.011754s` (`72.549046x`).
- Pi extension smoke passed via `/ldgr-topology-benchmark`, writing `results/pi_ldgr_topology_benchmark.json` with the long-window benchmark metrics.

## Representation Granularity Update

A granularity sweep answered whether finer detail improves encoding:

```text
reports/representation_granularity_sweep.md
```

Finding: finer detail helps only when it is recurrent and continuation-relevant. Maximum categorical detail fragmented motifs and reduced utility.

Best repeated-only utility:

```text
entity: utility/query=0.947621, mean set=10.475736
```

Best mixed repeated+novel utility:

```text
command_refined: utility/query=0.732154
artifact_ext_refined: utility/query=0.730578
refined baseline: utility/query=0.727191
full_categorical: utility/query=0.690758
```

Conclusion: production should use a middle-layer token schema: coarse structural events plus a small number of proven categorical refinements, not raw/maximal detail.

## Two-Stage Granularity Update

A two-stage coarse-to-fine experiment tested the proposed strategy:

```text
reports/two_stage_granularity_experiment.md
```

Result: the idea is supported. The best strategy was:

```text
entity -> command_refined
utility/query=0.688795
mean final candidate set=2.846763
```

Best single-stage baseline was:

```text
coarse
utility/query=0.686217
mean final candidate set=3.362502
```

The gain was modest because long windows were already specific, but two-stage filtering reduced candidate set size without losing hits. Production should use an entity/coarse recall index followed by command/artifact fine filters and cost-aware bounds.

## Outcome-Weighted Recollection Update

A global outcome-weighting experiment tested whether success motifs should receive higher support and failure/blocker motifs lower support:

```text
reports/outcome_weighted_recollection.md
```

Result: simple global outcome weighting was not supported. On the primary long-window mixed workload, unweighted support was best across practical bounds. At bound 25:

```text
unweighted utility/query:          0.702080
success_boost utility/query:       0.701486
aggressive_success utility/query:  0.701486
failure_suppressed utility/query:  0.701486
```

Outcome weighting also worsened mean expected rank:

```text
unweighted:     1.974821
success_boost:  2.102197
```

Recommendation: do not globally suppress failures or boost successes in the base topology index. Use outcome as a query-conditioned filter/reranker instead, e.g. failure-recovery motifs when currently failing, validated motifs when seeking stable automation.

## Dumb Learned Ranker Update

A minimal downstream learned discriminator was tested over topology-generated candidates:

```text
reports/dumb_learned_candidate_ranker.md
```

The model was a tiny no-dependency linear pairwise ranker with a learned abstention threshold. It did not replace the index.

Primary refined-token result:

```text
support baseline utility/query:       0.100679
learned no-threshold utility/query:   0.099491
learned thresholded utility/query:    0.103098
```

Token-mode follow-up found the strongest learned-threshold result on `artifact_ext_refined`:

```text
baseline utility/query:   0.098913
learned utility/query:    0.113953
```

However, the gain came mostly from abstaining on false emits, not better top-1 ranking. Conclusion: a dumb model provides weak evidence for learned discrimination, but not enough to justify heavy model training yet. Next ML attempt should add richer cross-index and goal-conditioned features before changing model class.

## Product Interpretation

The adapter product should package this as a yearly frozen auxiliary knowledge base:

```text
adapter binary
+ frozen LDGR corpus
+ topology motif index
+ content-safe tokenization rules
+ API capability layer
+ compatibility manifest
```

Users buy a yearly binary that remains functional. Future yearly versions improve the corpus/index without disabling old releases.

## Important Caveats

- The topology layer does not understand semantics.
- It does not make final decisions.
- It does not replace a downstream model or reasoner.
- Raw context would likely improve same-corpus retrieval but risks lexical/content leakage.
- Current LDGR token categories are heuristic and should be iterated.
- Benchmark scores depend strongly on split, window shape, stride, and candidate bound.

## Final Claim Review and Operations Handoff

Final claim status and reproducible operator guidance are recorded in:

```text
docs/research_program/claim_review_final.md
docs/research_program/operator_guide.md
```

Use those files as the claim boundary before quoting results externally: every final claim must remain linked to raw evidence or a documented decision gate (`req.01`, `test.02`), and unavailable baselines must remain labeled as unknowns (`req.03`).

## Best Next Work

1. Smoke-test the Pi extension inside an interactive Pi harness.
2. Build the bundled Pi benchmark harness described in `docs/pi_extension_benchmark_handoff.md`.
3. Add prefix indexing for faster large-corpus querying.
4. Run actual-use feedback simulation across operating modes.
5. Compare benchmark/coding/research splits separately after additional DB uploads.
