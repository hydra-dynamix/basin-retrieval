# Promoted Dual Lookup Control Experiment

Date: 2026-07-06

Starting checkpoint: `docs/unlabeled-constraint-basin-pilot.md`

## Purpose

Promote the unlabeled constraint-basin result into the active control loop.

Question:

Can trajectory lookup use both semantic retrieval types to improve internal
choice-state perturbation?

The two semantic retrieval types are:

- labeled semantic neighborhood lookup,
- unlabeled constraint-basin lookup with post-hoc label alignment.

## Boundary

Trajectory lookup remains identity-free and temporal.

The labeled semantic branch uses named concept constraints.

The unlabeled semantic branch uses only anonymous constraint IDs and anonymous
pair structure as the lookup key. Concept labels are revealed only after
retrieval and are then used as actuator payload for the current toy choice
state.

This matters because the experiment is testing whether labels fragment basin
retrieval. Labels are not allowed to create the unlabeled basin.

## Experiment Execution

Command:

```text
uv run python scripts/run_promoted_dual_lookup_control_experiment.py
```

Artifacts:

- Script: `scripts/run_promoted_dual_lookup_control_experiment.py`
- Report: `results/promoted-dual-lookup-control/report.json`
- Control records: `results/promoted-dual-lookup-control/control_records.jsonl`
- Unlabeled records: `results/promoted-dual-lookup-control/unlabeled_records.jsonl`

The promoted pipeline is:

```text
trajectory topology lookup
-> post-lookup evidence hydration
-> labeled semantic lookup
-> unlabeled constraint-basin lookup
-> internal state perturbation
-> choice
-> utility
```

## Results

Default promoted setting: `top_k = 10`.

| Policy | Mean utility |
| --- | ---: |
| No semantic perturbation | 0.533333 |
| Labeled semantic lookup | 0.700000 |
| Unlabeled basin lookup | 1.000000 |
| Naive labeled+unlabeled union | 0.566667 |
| Agreement-gated dual lookup | 1.000000 |
| Oracle | 1.000000 |

Lifts:

- labeled lift versus no semantic: `+0.166667`
- unlabeled lift versus no semantic: `+0.466667`
- unlabeled lift versus labeled: `+0.300000`
- agreement-gated dual lookup lift versus labeled: `+0.300000`
- naive union lift versus labeled: `-0.133333`
- agreement-gated oracle gap: `0.000000`

Choice counts:

| Policy | Choices |
| --- | --- |
| No semantic | `stabilize: 3` |
| Labeled | `expand: 1`, `stabilize: 2` |
| Unlabeled | `counter_expand: 1`, `expand: 1`, `stabilize: 1` |
| Agreement-gated dual lookup | `counter_expand: 1`, `expand: 1`, `stabilize: 1` |
| Oracle | `counter_expand: 1`, `expand: 1`, `stabilize: 1` |

## Top-K Sweep

| top_k | Labeled | Unlabeled | Agreement-gated | Naive union |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.700000 | 0.933333 | 0.933333 | 0.700000 |
| 2 | 0.700000 | 0.933333 | 0.933333 | 0.566667 |
| 3 | 0.700000 | 0.933333 | 0.933333 | 0.566667 |
| 4 | 0.700000 | 0.933333 | 0.933333 | 0.566667 |
| 5 | 0.700000 | 0.566667 | 0.566667 | 0.566667 |
| 8 | 0.700000 | 0.933333 | 0.933333 | 0.566667 |
| 10 | 0.700000 | 1.000000 | 1.000000 | 0.566667 |

The useful knob is basin breadth. On this toy substrate, broad enough unlabeled
retrieval recovers the missing counter/avoidance concepts and hits oracle
utility. The non-monotonic `top_k = 5` result shows that partial basin retrieval
can be worse than either narrow or broad retrieval.

## Interpretation

The result supports promoting unlabeled basins into the semantic-control path.

The key result is not simply that unlabeled retrieval wins. The stronger result
is that naive combination fails:

```text
labeled neighborhood union unlabeled basin
```

is worse than labeled-only, because broad labeled concepts can drown out the
post-hoc basin evidence.

The useful dual path is agreement-gated:

```text
labeled semantic neighborhood
AND
unlabeled basin labels after lookup
```

That preserves the unlabeled substrate's basin signal while still letting the
labeled semantic layer serve as an interpretation check.

## Decision

Keep both semantic retrieval modes:

- labeled lookup for named interpretation,
- unlabeled lookup for basin recovery,
- agreement-gated combination for control.

Do not merge labeled and unlabeled neighborhoods by blind union. Treat union as
an explicitly bad baseline unless later evidence reverses this result.

The next experiment should test whether the agreement-gated dual lookup remains
useful when semantic perturbation weights are learned rather than hand-coded.
