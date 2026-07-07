# First-Occurrence Deletion Controls

Fixed DP/LCS for trace regimes. This tests whether drop brittleness is specifically first-occurrence canonical renumbering.

## Clean / Polysemy / Drop Summary

| regime | heldout | bundle | reduction | polysemy | first-rec drop | repeat drop | singleton drop | random drop T |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical_first_occurrence | 1.0 | 2.0 | 34.0 | 1.0 | 0.5 | 1.0 | 0.6 | 4 |
| anchored_recurring | 1.0 | 2.0 | 34.0 | 0.4286 | 0.4412 | 0.7727 | 0.8 | 3 |
| edge_sequence | 1.0 | 2.0 | 34.0 | 0.8571 | 1.0 | 1.0 | 1.0 | None |
| bag_edges | 1.0 | 2.0 | 34.0 | 0.5714 | 1.0 | 1.0 | 1.0 | None |

## Random Drop Surface

| magnitude | canonical_first_occurrence | anchored_recurring | edge_sequence | bag_edges |
|---:|---:|---:|---:|---:|
| 0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 1 | 1.0 | 0.75 | 1.0 | 1.0 |
| 2 | 0.5 | 0.6 | 1.0 | 1.0 |
| 3 | 0.55 | 0.4 | 1.0 | 0.9 |
| 4 | 0.25 | 0.3 | 0.9 | 0.8 |

## Interpretation

The first-occurrence mechanism is confirmed but the narrow anchor is rejected.

Canonical first-occurrence is perfectly stable on repeat deletions (1.0) but only
0.5 on first-recurring-occurrence deletions, so identity-establishing evidence is
the vulnerable case. Singleton deletion also hurts (0.6), but that is loss of a
unique typed relation, not recurrence renumbering.

Anchored recurring nodes did not repair the target failure: first-recurring drop
fell slightly (0.4412 vs 0.5), repeat drop worsened (0.7727 vs 1.0), random-drop
transition worsened (4 -> 3), and polysemy collapsed (1.0 -> 0.4286). So this
narrow identity tweak is not viable.

Edge-sequence and bag-of-edges prove deletion robustness is available cheaply, but
by giving up recurrence identity. Edge-sequence keeps order and retains partial
polysemy (0.8571); bag gives up both order and recurrence and falls to 0.5714.

Boundary statement: with canonical recurrence identity + DP/LCS, the substrate
supports insertion/noise robustness after matcher repair, but deletion of
identity-establishing evidence remains a true destructive perturbation unless one
accepts a representation that gives up some recurrence-sensitive discrimination.
