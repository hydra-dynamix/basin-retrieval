# DP/LCS Full Basin Surface

Representation held fixed: canonical first-occurrence identity.
Architecture: label-free coarse basin bundle → typed payload scoring → soft alignment.
Greedy is the pre-fix comparator; DP/LCS is the new default.

## Summary

| matcher | heldout acc | coarse bundle | fine bundle | fine reduction | polysemy disambig | drop transition | corrupt transition | noise transition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy | 1.0 | 2.0 | 2.0 | 34.0 | 1.0 | 4 | None | 2 |
| dp | 1.0 | 2.0 | 2.0 | 34.0 | 1.0 | 4 | None | 3 |

## Survival Surface

### drop

| magnitude | greedy | dp |
|---:|---:|---:|
| 0 | 1.0 | 1.0 |
| 1 | 0.8 | 0.9 |
| 2 | 0.65 | 0.65 |
| 3 | 0.6 | 0.6 |
| 4 | 0.3 | 0.3 |

### corrupt

| magnitude | greedy | dp |
|---:|---:|---:|
| 0 | 1.0 | 1.0 |
| 1 | 1.0 | 1.0 |
| 2 | 1.0 | 1.0 |
| 3 | 1.0 | 1.0 |
| 4 | 1.0 | 1.0 |

### noise

| magnitude | greedy | dp |
|---:|---:|---:|
| 0 | 1.0 | 1.0 |
| 1 | 0.55 | 0.7 |
| 2 | 0.45 | 0.6 |
| 3 | 0.25 | 0.45 |
| 4 | 0.35 | 0.5 |

## Interpretation

DP/LCS repairs the causal greedy noise failure by allowing unmatched evidence to be skipped and alignment to recover later in the trace. The result is not perfect noise immunity; it is a measurable stability surface. Polysemy and fine bundle reduction remain intact, so the repair does not reduce to bag-of-edges matching.
