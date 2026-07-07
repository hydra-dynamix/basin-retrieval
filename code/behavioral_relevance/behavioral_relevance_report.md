# Behavioral Relevance of Identity-Establishing Deletion

Memory content: LDGR historical observations, artifact descriptions, and report chunks from this project.
Architecture: label-free canonical topology index → typed payload projection → DP/LCS soft alignment.

## Corpus

- memory items: 32
- topics: {'deletion': 8, 'matcher': 7, 'identity': 4, 'noise': 6, 'polysemy': 2, 'typed': 4, 'phase0': 1}

## Clean Baseline

- clean accuracy: 1.0
- mean fine bundle: 1.0
- bundle reduction: 32.0

If clean accuracy is poor, the behavioral relevance profile should be treated as a corpus/encoding failure, not as evidence about deletion brittleness.

## Overall Query Profile

- n_queries: 320
- first_recurring_deletion_incidence: 0.4719
- survival: 0.7344
- survival_when_first_recurring_deleted: 0.5695
- survival_without_first_recurring_deleted: 0.8817
- mean_fine_bundle: 1.175

## By Query Mode

| mode | n | first-rec incidence | repeat incidence | singleton incidence | survival | fine bundle |
|---|---:|---:|---:|---:|---:|---:|
| adversarial_first_recurring_drop | 32 | 1.0 | 0.0 | 0.0 | 0.9375 | 1.0 |
| prefix_4 | 32 | 0.0 | 0.0 | 0.0 | 0.8438 | 1.25 |
| prefix_6 | 32 | 0.0 | 0.0 | 0.0 | 0.9375 | 1.0625 |
| prefix_8 | 32 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |
| prefix_plus_noise | 32 | 0.0 | 0.0 | 0.0 | 0.625 | 1.0625 |
| random_partial_0 | 32 | 0.875 | 0.9688 | 0.9688 | 0.2812 | 1.375 |
| random_partial_1 | 32 | 1.0 | 0.9688 | 0.9688 | 0.0938 | 1.2188 |
| salient_summary | 32 | 1.0 | 0.0 | 1.0 | 0.8125 | 1.4375 |
| single_omission_0 | 32 | 0.3125 | 0.4375 | 0.25 | 0.9688 | 1.0625 |
| single_omission_1 | 32 | 0.5312 | 0.1562 | 0.3125 | 0.8438 | 1.2812 |

## Plausible vs Control Modes

- plausible_modes: {'n': 224, 'first_recurring_deletion_incidence': 0.2634, 'survival': 0.8616, 'survival_when_first_recurring_deleted': 0.7966, 'survival_without_first_recurring_deleted': 0.8848, 'mean_fine_bundle': 1.1652}
- control_modes: {'n': 96, 'first_recurring_deletion_incidence': 0.9583, 'survival': 0.4375, 'survival_when_first_recurring_deleted': 0.4239, 'survival_without_first_recurring_deleted': 0.75, 'mean_fine_bundle': 1.1979}

## Recovery With Extra Evidence

- overall survival by added evidence step: {'0': 0.5695, '1': 0.6225, '2': 0.6225, '3': 0.6225}

By mode:

- adversarial_first_recurring_drop: {'0': 0.9375, '1': 1.0, '2': 1.0, '3': 1.0}
- random_partial_0: {'0': 0.2143, '1': 0.2143, '2': 0.2143, '3': 0.2143}
- random_partial_1: {'0': 0.0938, '1': 0.0938, '2': 0.0938, '3': 0.0938}
- salient_summary: {'0': 0.8125, '1': 0.8125, '2': 0.8125, '3': 0.8125}
- single_omission_0: {'0': 0.9, '1': 1.0, '2': 1.0, '3': 1.0}
- single_omission_1: {'0': 0.7059, '1': 1.0, '2': 1.0, '3': 1.0}

## Topic Polysemy Probe

- probes: 25
- shared topical inclusion: 1.0
- +mechanism disambiguation: 0.84
- mean shared bundle: 5.64
- mean +mechanism bundle: 1.32

## Interpretation

This profile estimates whether the known destructive perturbation appears under behaviorally plausible historical-query conditions. Prefix/incomplete and noisy-prefix modes model missing tail evidence and inserted noise; single/random omissions model note-taking gaps; adversarial mode calibrates the known boundary.

Overall first-recurring deletion incidence was 0.4719; survival with first-recurring deletion was 0.5695 vs 0.8817 without it.

For the behaviorally plausible modes only, first-recurring deletion incidence was 0.2634 and survival stayed 0.8616 (0.7966 with first-recurring deletion vs 0.8848 without).

For control/adversarial modes, first-recurring deletion incidence was 0.9583 and survival dropped to 0.4375. This separates realistic note/incomplete queries from destructive random/adversarial omissions.

Use the by-mode table, not the overall average alone: adversarial calibration is intentionally included and should not be mistaken for expected workload frequency.
