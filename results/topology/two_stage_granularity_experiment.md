# Two-Stage Coarse-to-Fine Granularity Experiment

## Question

Would a two-stage representation work better?

```text
stage 1: coarse topology to preserve recurrence and recall
stage 2: finer topology to narrow/filter candidates
```

## Setup

Corpus:

```text
/mnt/nas/data/ldgr/benchmarks/splits/benchmarks
```

Main configuration:

```text
window=30..36
stride=6
stage1_bound=100
stage2_bound=100
candidate_cost=0.005
```

Strategies compared:

- single-stage: `entity`, `coarse`, `refined`, `command_refined`, `artifact_ext_refined`
- two-stage: `entity|coarse -> refined|command_refined|artifact_ext_refined`

Raw outputs:

```text
results/two_stage_granularity_sweep.json
results/two_stage_granularity_bound_sweep.json
results/two_stage_granularity_cost_sweep.json
```

## Main Result

Best strategy:

```text
entity -> command_refined
```

Metrics:

```text
query_count:                 5051
hits:                        4051
false_answers:               1000
abstentions:                 0
mean stage1 candidate set:   3.338349
mean final candidate set:    2.846763
utility/query:               0.688795
```

Best single-stage baseline:

```text
coarse
utility/query:               0.686217
mean final candidate set:    3.362502
```

Two-stage improved utility modestly and reduced final candidate set size.

## Strategy Comparison

| strategy | hits | false answers | abstentions | mean final set | utility/query |
|---|---:|---:|---:|---:|---:|
| entity | 4050 | 1001 | 0 | 3.338349 | 0.686040 |
| coarse | 4051 | 1000 | 0 | 3.362502 | 0.686217 |
| refined | 4051 | 1000 | 0 | 3.837656 | 0.683841 |
| command_refined | 4051 | 1000 | 0 | 3.775886 | 0.684150 |
| artifact_ext_refined | 4051 | 1000 | 0 | 3.862601 | 0.683716 |
| entity -> refined | 4051 | 1000 | 0 | 2.870125 | 0.688678 |
| entity -> command_refined | 4051 | 1000 | 0 | 2.846763 | 0.688795 |
| entity -> artifact_ext_refined | 4051 | 1000 | 0 | 2.850723 | 0.688775 |
| coarse -> refined | 4051 | 1000 | 0 | 3.045140 | 0.687803 |
| coarse -> command_refined | 4051 | 1000 | 0 | 2.984953 | 0.688104 |
| coarse -> artifact_ext_refined | 4051 | 1000 | 0 | 3.022570 | 0.687916 |

## Bound Sweep

With stricter final candidate bounds, two-stage behavior becomes clearer.

| stage2 bound | best strategy | utility/query | hits | false answers | abstentions | mean final set |
|---:|---|---:|---:|---:|---:|---:|
| 1 | entity -> command_refined | -0.088167 | 502 | 114 | 4435 | 1.000000 |
| 2 | entity -> artifact_ext_refined | 0.548913 | 3364 | 763 | 924 | 1.850739 |
| 3 | entity -> artifact_ext_refined | 0.556574 | 3397 | 767 | 887 | 1.860951 |
| 5 | entity | 0.614982 | 3674 | 844 | 533 | 2.278663 |
| 10 | entity -> artifact_ext_refined | 0.673665 | 3969 | 971 | 111 | 2.442105 |
| 25 | entity -> command_refined | 0.685134 | 4027 | 988 | 36 | 2.647657 |
| 100 | entity -> command_refined | 0.688795 | 4051 | 1000 | 0 | 2.846763 |

Too-strict bounds create bad abstentions. Bounds around 10-100 preserve most hits while narrowing the final candidate set.

## Cost Sweep

At all tested candidate costs, `entity -> command_refined` was best:

| candidate cost | best strategy | utility/query | mean final set |
|---:|---|---:|---:|
| 0.005 | entity -> command_refined | 0.688795 | 2.846763 |
| 0.025 | entity -> command_refined | 0.631860 | 2.846763 |
| 0.100 | entity -> command_refined | 0.418353 | 2.846763 |

Because two-stage filtering reduced candidate sets without losing hits in this setup, the same strategy remained best as candidate cost increased.

## Interpretation

The two-stage idea is supported, but the measured gain is modest in this exact long-window setup because long windows are already highly specific.

Still, the pattern is useful:

```text
coarse/entity stage -> preserves recall
fine command/artifact stage -> reduces candidate set
```

The best observed two-stage combinations use `entity` first, not `coarse`. That suggests the first pass should be as recurrence-preserving as possible, while fine detail should be introduced only after coarse compatibility is established.

## Caveats

- This implementation evaluates aligned windows with a fixed half-window prefix. It is a cleaner two-stage test but not identical to the previous motif-memory query implementation.
- Novel/singleton prefixes remain hard: topology-only canonicalization still answers many of them because it has no semantics or raw content.
- The main improvement is candidate-set reduction, not false-answer elimination.

## Answer

Yes, two sweeps are a good approach:

```text
coarse pass: find broad compatible continuation family
fine pass: narrow candidate set with selected categorical refinements
```

For production, use:

```text
entity/coarse recall index
+ command/artifact fine filter
+ cost-aware candidate bound
+ prefix index for speed
```

Do not use maximum detail as the first-pass representation.
