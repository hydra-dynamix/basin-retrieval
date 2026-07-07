# Architecture Boundary: Recurrence-Sensitive Basin Retriever

## Current Architecture

```text
label-free canonical topology index
  -> broad basin retrieval
  -> typed payload projection
  -> DP/LCS soft alignment
  -> fine discrimination
```

This substrate is **not** a general edit-distance memory. It is a recurrence-sensitive basin retriever.

## Main Finding

Canonical recurrence identity preserves discrimination, but depends on identity-establishing evidence.

```text
canonical recurrence:
  strong polysemy / discrimination
  weaker first-occurrence deletion

edge_sequence / bag_edges controls:
  deletion robust
  weaker polysemy / discrimination
```

So the deletion weakness is not currently treated as a bug to tune away. It is a measured representation cost.

## Mechanisms Separated

### Noise brittleness

```text
layer: matcher
cause: greedy single-pass alignment treated one unmatched inserted evidence node as terminal failure
repair: DP/LCS skip-capable alignment
```

Observed repair:

```text
noise transition: 2 -> 3
heldout:          1.0 unchanged
polysemy:         1.0 unchanged
reduction:        34x unchanged
```

### Drop brittleness

```text
layer: identity / recurrence representation
cause: deletion of identity-establishing first occurrence
status: boundary, not fixed
```

Deletion controls:

```text
regime                      heldout reduction polysemy first-rec repeat singleton dropT
canonical_first_occurrence  1.0     34x       1.0      0.50      1.00   0.60      4
anchored_recurring          1.0     34x       0.4286   0.4412    0.7727 0.80      3
edge_sequence               1.0     34x       0.8571   1.00      1.00   1.00      none
bag_edges                   1.0     34x       0.5714   1.00      1.00   1.00      none
```

Anchored recurring nodes are rejected: they do not repair first-recurring deletion and they damage polysemy.

Edge-sequence and bag controls prove deletion robustness is available, but only by giving up recurrence-sensitive discrimination.

## Boundary Statement

> This substrate tolerates insertion/noise after DP/LCS matcher repair, but deletion of identity-establishing evidence can destroy the basin. That is a legitimate architecture boundary for canonical recurrence identity, not currently a scoring bug.

## What Not To Do Next

Do not continue patching deletion inside this substrate unless a downstream task proves the boundary is unacceptable.

Do not return to `role_payload(local)`: smoke tests showed it is worse than canonical under edits because walk-local incident structure changes when neighbors are inserted/deleted.

Do not adopt `anchored_recurring`: deletion-control results rejected it.

## Next Useful Experiment

Behavioral relevance test:

> In realistic retrieval conditions, how often does identity-establishing evidence get deleted versus merely noisy/incomplete?

Interpretation:

```text
if first-occurrence deletion is rare or recoverable through extra evidence:
  boundary is acceptable

if first-occurrence deletion is common:
  substrate is too brittle for semantic memory unless paired with another representation
```

The next experiment should therefore measure realistic perturbation incidence and recovery, not invent another deletion fix.
