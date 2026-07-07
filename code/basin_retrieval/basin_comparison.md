# Basin stability and polysemy suite (measurement only)

No gate, no thresholds, no verdict. Numbers only.

Setup: 20 disjoint generated families + 7 prefix-shared polysemy
pairs, 3 instances each. Index on instances 0,1; held-out query = instance 2
(symbolically novel). Two variants: typed (edge labels kept) and labelfree
(edge labels collapsed).

Relaxation rule: discrete prefix-consistency pruning.

## Metrics

| metric | typed | labelfree |
|---|---|---|
| inclusion_rate | 1.0 | 1.0 |
| bundle_reduction | 34.0 | 34.0 |
| stability_drop_all (incl trailing) | 0.125 | 0.1562 |
| stability_drop_interior | 0.0 | 0.05 |
| stability_corrupt | 0.6929 | 0.2929 |
| basin_depth_drop_interior (max) | 0 | 2 |
| polysemy both_active | 1.0 | 1.0 |
| polysemy disambiguation | 1.0 | 0.286 |
| polysemy ambiguity_retention | 1.0 | 1.0 |

## Raw per-family and per-pair measurements

See `basin_results.json`.
