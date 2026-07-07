# Representation Granularity Sweep

## Question

If topology recollection captures finer-grained LDGR event detail, does it improve or reduce the ability to encode a reusable representation?

## Short Answer

Finer detail helps only when it adds recurrent structural information. Detail that fragments otherwise repeated motifs reduces utility. In this corpus, the best result came from **selective categorical enrichment**, not maximum detail.

## Setup

Corpus:

```text
/mnt/nas/data/ldgr/benchmarks/splits/benchmarks
```

Configuration:

```text
window=30..36
stride=6
max_candidates=100
candidate_cost=0.005
min_support=2
```

Compared token granularities:

- `entity`: entity type only
- `coarse`: entity + event type
- `refined`: existing content-safe categories
- `phase_refined`: refined + run phase payload category
- `status_refined`: refined + run/work-item status
- `artifact_ext_refined`: refined + artifact extension bucket
- `command_refined`: refined + run command bucket
- `full_categorical`: phase + status + artifact extension + command bucket

Raw result:

```text
results/representation_granularity_sweep.json
```

## Repeated-Motif Workload

| mode | unique tokens | queries | coverage | mean set size | utility/query |
|---|---:|---:|---:|---:|---:|
| entity | 21 | 3668 | 1.000000 | 10.475736 | 0.947621 |
| coarse | 42 | 3640 | 1.000000 | 10.937912 | 0.945310 |
| refined | 60 | 4051 | 1.000000 | 11.522587 | 0.942387 |
| phase_refined | 67 | 4049 | 0.989380 | 14.889915 | 0.913066 |
| status_refined | 78 | 4036 | 1.000000 | 11.692765 | 0.941536 |
| artifact_ext_refined | 98 | 4062 | 1.000000 | 11.565731 | 0.942171 |
| command_refined | 64 | 4056 | 1.000000 | 11.308925 | 0.943455 |
| full_categorical | 147 | 4046 | 0.983688 | 14.453769 | 0.908520 |

Repeated-only finding:

- Coarser `entity` tokens had the best utility because they preserve recurrence density and small candidate sets.
- `command_refined` was the best fine-grained addition, slightly outperforming baseline refined.
- `phase_refined` and `full_categorical` hurt: phase detail fragmented repeated motifs and increased candidate set size.

## Mixed Repeated + Novel Workload

This workload adds singleton/novel windows to test false-answer pressure and good abstentions.

| mode | mixed coverage | false answers | good abstentions | bad abstentions | mean set size | utility/query |
|---|---:|---:|---:|---:|---:|---:|
| entity | 0.818766 | 154 | 846 | 0 | 10.776818 | 0.725162 |
| coarse | 0.815517 | 144 | 856 | 0 | 11.056818 | 0.723880 |
| refined | 0.850327 | 244 | 756 | 0 | 11.918976 | 0.727191 |
| phase_refined | 0.852248 | 297 | 703 | 43 | 15.590518 | 0.695449 |
| status_refined | 0.851469 | 252 | 748 | 0 | 12.075093 | 0.725002 |
| artifact_ext_refined | 0.846503 | 223 | 777 | 0 | 11.776663 | 0.730578 |
| command_refined | 0.844343 | 213 | 787 | 0 | 11.605997 | 0.732154 |
| full_categorical | 0.850377 | 311 | 689 | 66 | 15.028432 | 0.690758 |

Mixed-workload finding:

- Best utility: `command_refined` at `0.732154`.
- Second: `artifact_ext_refined` at `0.730578`.
- Baseline refined: `0.727191`.
- Full detail was worst among categorical modes: `0.690758`.

So selective fine detail can improve utility, but simply adding all available categories reduces it.

## Interpretation

The representation has a clear recurrence/specificity tradeoff:

```text
coarser tokens
  -> more recurrence density
  -> smaller motifs/candidate sets
  -> stronger compression
  -> possible false-answer risk

finer tokens
  -> more situational specificity
  -> more motifs and query groups
  -> possible lower false-answer pressure
  -> fragmentation if detail is incidental
```

The experiment shows that **not all detail is equal**:

Useful / promising detail:

- command category on run start,
- artifact extension/type category.

Less useful or harmful detail:

- detailed run phase categories,
- combining all categorical details at once.

The likely reason is that command/artifact buckets correlate with workflow continuation type, while phase/status details often duplicate common control-flow scaffolding or split equivalent traces by incidental runtime state.

## Answer to the User Question

Capturing finer-grained detail can improve encoding only if the detail is recurrent and continuation-relevant. Otherwise it reduces the ability to encode by fragmenting motifs.

For this corpus:

```text
best repeated-only: entity
best mixed workload: command_refined
worst tested: full_categorical / phase_refined
```

The optimal representation is therefore a **middle layer**:

```text
coarse structural event categories
+ a small number of continuation-relevant categorical refinements
- raw text, IDs, timestamps, one-off path details, and overly detailed phase/status noise
```

## Product Implication

Production topology recollection should expose a configurable token schema and measure each schema by:

- recurrence density,
- candidate set size,
- mixed workload false answers,
- good vs bad abstentions,
- utility under downstream scoring cost.

Do not default to maximum detail. Default to a conservative categorical schema, then allow targeted refinements proven by utility.
