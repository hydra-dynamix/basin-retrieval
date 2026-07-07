# Findings: Typed Relational Substrate as Basin-Forming Memory

## Phase Package / Frozen Claim

See `operating_envelope_report.md` for the packaged result.

Frozen substrate claim:

```text
canonical label-free topology index
  -> broad basin retrieval
  -> typed/content payload projection
  -> DP/LCS alignment
  -> fine discrimination
```

Operating envelope:

```text
works on LDGR historical memory content under plausible partial queries
known weak point: adversarial/random deletion of identity-establishing evidence
```

Headline LDGR-history result:

```text
clean retrieval:              1.0 accuracy, 32x reduction
plausible query survival:     0.8884
with first-rec deletion:      0.8644
topic shared inclusion:       1.0
+mechanism disambiguation:    0.9231
bundle narrowing:             5.58 -> 1.15
```

Updated boundary:

> first-occurrence deletion is a destructive perturbation in isolation, but
> realistic redundant memory queries often survive it.


Continuation of `../topology/reports/final_findings.md`. The prior program ended on
identity-free recurrent temporal topology as an auxiliary constraint memory and
flagged structural generalization (phase 8) and typed-edge value as open. This
batch ports the canonical-signature mechanism from opaque sequences to a TYPED
relational graph and asks the dynamical question the prior program never measured:
basin stability under perturbation.

## Bottom Line

The strongest defensible finding is:

> A typed relational substrate supports identity-free family consolidation and
> held-out retrieval (perfect inclusion, 36x bundle reduction), and typed edge
> labels carry discriminating information beyond pure topology on prefix-shared
> (polysemous) families and on corrupted-evidence recovery. Under the discrete
> prefix-consistency operator tested here, basins do NOT survive one-item
> interior perturbation.

That last clause is a measurement of the operator, not a defense of the idea.

## What Worked

- Typed canonical signatures: node ids canonicalized by first occurrence, edge
  labels (relation type + traversal direction) preserved. Three disjoint
  contested claims collapse to one signature; relabels match; shuffles differ.
- Identity-free consolidation on a typed graph: 20/20 generated families
  consolidate (all instances share a signature), 20/20 families distinct.
- Held-out retrieval: index on instances 0,1; query instance 2 (symbolically
  novel). Inclusion 1.0, bundle reduction 36x across 20 families + 8 polysemy pairs.
- Polysemy (prefix-shared pairs, the `bat`/`bank` construction): ambiguity
  retained 1.0 — both basins stay active on the shared prefix rather than
  collapsing to one.
- Typed edges beat label-free on two metrics that depend on distinguishing structure.

## What Did Not Work

- Basin stability under interior evidence deletion: stability 0.0 (typed), 0.05
  (labelfree). Below chance (~0.04 on 25 families).
- The operator annihilates the active set on any interior drop. Mechanism:
  dropping an interior step renumbers the first-occurrence canonical trace, so
  the perturbed walk matches nothing.
- Polysemy disambiguation at +1 step: 0.875 typed (one pair of eight fails),
  0.25 labelfree. Typed passes most pairs but not all; labelfree mostly cannot
  disambiguate from a single suffix step.

## Metrics (typed vs labelfree)

```text
n_disjoint_families:     20
n_polysemy_pairs:         8
instances_per_family:     3   (2 indexed, 1 held-out query)

metric                         typed    labelfree
inclusion_rate                 1.0      1.0
bundle_reduction               36.0     36.0
stability_drop_interior        0.0      0.05
stability_corrupt              0.6929   0.2929
basin_depth_drop_interior_max  0        2

polysemy (typed):
  both_active_on_shared        1.0
  disambiguation_at_+1         0.875    (7/8 pairs)
  ambiguity_retention          1.0
```

## The Perturbation Split

The cleanest signal in this batch is that drop and corrupt perturbation behave
oppositely, and that split is the load-bearing finding:

```text
interior DROP:    active set annihilated (0.0).   Basins cannot survive deletion.
interior CORRUPT: basin preserved at pre-corrupt prefix (0.69 typed).
```

So the basin exists and is prefix-recoverable; this operator cannot measure its
depth because deletion breaks canonical numbering. The corrupt-vs-drop gap is
where future work has to land. Anything that claims basin depth must move the
drop number off zero without lying about why.

## Typed vs Label-Free

This is the first time the typed-edge question (prior program phase 4) produced a
non-inert result. On a phase-0 toy it was inert because attributes had a globally
consistent ordering. On generated typed walks with real recurrence:

```text
stability_corrupt:      typed 0.69  vs  labelfree 0.29   (2.4x)
polysemy disambig +1:   typed 0.875 vs  labelfree 0.25
```

Keeping relation types helps when the task is distinguishing two structurally
similar neighborhoods. Label-free topology alone disambiguates poorly from a
single suffix step.

## Important Caveats

- The perturbation result is a property of discrete prefix-consistency pruning,
  not a property of typed relational substrates in general. It does not establish
  that basins are shallow; it establishes this operator cannot probe depth.
- Polysemy ambiguity-retention is partly low-surprise: two families sharing a
  canonical prefix both match that prefix by exact arithmetic. It confirms the
  operator holds ambiguity but does not stress it.
- Disambiguation 0.875 is a real near-miss (pair 7 fails), not an artifact. Not
  investigated further in this batch.
- This is a single constraint space. Multi-space intersection (the stronger
  vision) is out of scope and unclaimed.
- 20 families / 8 polysemy pairs is small. Numbers above are point estimates; no
  bootstrap CI was computed.
- Thresholds (0.7, 0.9) appearing in earlier drafts were unprincipled and have
  been removed from interpretation. The only defensible floor is "above chance,"
  and on interior-drop the result is at the floor.

## What This Establishes and Does Not

Establishes:

- Typed relational walks are a valid carrier for identity-free motif memory
  (consolidation + held-out retrieval work, 36x reduction).
- Typed edges carry information that pure topology does not, on tasks that
  require distinguishing similar neighborhoods.
- Polysemy-style prefix-shared families retain ambiguity under this operator.

Does NOT establish:

- Basin stability. The predeclared perturbation criterion fires for this operator.
- That typed relational substrates form stable basins. That requires an operator
  whose drop-stability is measurable, which this batch did not build.
- Anything about multi-space semantics, scale, or real records.

## Open Questions (data-derived, not pre-answered)

1. Does an operator that does not annihilate on interior deletion produce
   non-zero basin depth? The corrupt result (0.69 typed) is consistent with
   basins having prefix-depth, but that is not the same as measured depth.
2. Why does polysemy pair 7 fail to disambiguate at +1? Open.
3. Does typed-vs-labelfree separation hold on a larger generated suite, or is it
   an artifact of 20 families?
4. Does the corrupt-perturbation prefix-recovery generalize to multi-step
   corruption, or collapse?

## Later Correction: Noise Collapse Was a Matcher Failure

A follow-up smoke test falsified the initial representation-layer diagnosis.
Canonical first-occurrence identity is not universally edit-brittle:

```text
                       del first-occ    del repeat node    insertion
canonical              4/9              8/9                9/9
label                  8/9              8/9                9/9
role_payload(local)    0/9              0/9                4/9
```

So canonical has a real but narrow failure mode: deletion of a first-occurrence
node. Neutral noise insertion does **not** renumber existing canonical ids. The
noise-collapse mechanism was instead the greedy matcher: one unmatched inserted
evidence node caused the candidate iterator to exhaust, preventing recovery on
all later evidence.

Matcher ablation (`noise-collapse-matcher-ablation`) kept canonical identity fixed
and compared greedy vs skip-capable alignment:

```text
matcher        noise@1 noise@2 noise@3 noise@4  polysemy  reduction
---            ---     ---     ---     ---      ---       ---
greedy         0.60    0.35    0.30    0.30     1.00      34x
dp/LCS         0.75    0.65    0.50    0.55     1.00      34x
bidirectional  0.85    0.70    0.50    0.60     1.00      34x
bag_edges      1.00    1.00    1.00    1.00     0.571     34x
```

Result: skip-capable alignment improves neutral-noise stability while preserving
polysemy disambiguation and bundle reduction. Bag-of-edges is the expected
control: perfectly noise-stable but loses recurrence-sensitive polysemy.

The full two-stage surface then promoted DP/LCS to the default architecture:

```text
canonical label-free topology index
  -> broad basin retrieval
  -> typed payload projection
  -> DP/LCS soft alignment
  -> fine discrimination
```

Direct pre-fix vs post-fix comparison under that architecture:

```text
matcher  heldout  coarse  fine  reduction  polysemy  dropT  corruptT  noiseT
greedy   1.0      2.0     2.0   34x        1.0       4      none      2
dp/LCS   1.0      2.0     2.0   34x        1.0       4      none      3
```

Survival surface:

```text
drop:    greedy [1.0, 0.8, 0.65, 0.6, 0.3]
         dp/LCS [1.0, 0.9, 0.65, 0.6, 0.3]

corrupt: greedy [1.0, 1.0, 1.0, 1.0, 1.0]
         dp/LCS [1.0, 1.0, 1.0, 1.0, 1.0]

noise:   greedy [1.0, 0.55, 0.45, 0.25, 0.35]
         dp/LCS [1.0, 0.7,  0.6,  0.45, 0.5]
```

Interpretation: DP/LCS does not make the basin noise-perfect; it moves the noise
transition from magnitude 2 to magnitude 3 and preserves recurrence-sensitive
polysemy. That is a mechanism repair, not metric laundering. Drop transition
remains unchanged, so first-occurrence deletion brittleness is still a separate
known issue.

## Later Correction 2: Drop Brittleness Is a Real Identity Boundary

A focused deletion-control experiment compared:

```text
canonical_first_occurrence
anchored_recurring
edge_sequence
bag_edges
```

Fixed DP/LCS was used for trace regimes. Results:

```text
regime                      heldout reduction polysemy first-rec repeat singleton dropT
canonical_first_occurrence  1.0     34x       1.0      0.50      1.00   0.60      4
anchored_recurring          1.0     34x       0.4286   0.4412    0.7727 0.80      3
edge_sequence               1.0     34x       0.8571   1.00      1.00   1.00      none
bag_edges                   1.0     34x       0.5714   1.00      1.00   1.00      none
```

The mechanism is confirmed: canonical is perfectly stable on repeat deletion but
weak on first-recurring-occurrence deletion. However, the narrow recurring-node
anchor is rejected: it does not improve the target failure and it damages
polysemy. Edge-sequence and bag controls prove deletion robustness is available
by giving up recurrence identity; edge-sequence keeps order and preserves partial
polysemy, bag loses more discrimination.

Boundary statement:

> With canonical recurrence identity + DP/LCS, the substrate supports
> insertion/noise robustness after matcher repair, but deletion of
> identity-establishing evidence remains a true destructive perturbation unless
> one accepts a representation that gives up some recurrence-sensitive
> discrimination.

## Later Relevance Test: LDGR Historical Findings as Memory Content

A behavioral relevance experiment used actual LDGR project history as memory
content: observations, artifact descriptions, and report chunks. The architecture
was unchanged:

```text
label-free canonical topology index
  -> typed payload projection
  -> DP/LCS soft alignment
```

The corpus was stratified by topic to avoid one recent deletion report dominating:
32 memory items, clean accuracy 1.0, mean fine bundle 1.0, reduction 32x. This
means the behavioral profile is valid as a retrieval test, not merely an encoding
failure.

Headline profile:

```text
overall queries:                         320
overall first-recurring deletion rate:   0.4719
overall survival:                        0.7562
survival with first-recurring deletion:  0.6026
survival without it:                     0.8935
mean fine bundle:                        1.1313
```

But the key result is the stratification:

```text
plausible modes only:
  n:                                  224
  first-recurring deletion incidence: 0.2634
  survival:                           0.8884
  survival with first-rec deletion:   0.8644
  survival without:                   0.8970

control/adversarial modes:
  n:                                  96
  first-recurring deletion incidence: 0.9583
  survival:                           0.4479
```

So, in this historical-memory setting, identity-establishing deletion is harmful
but not usually fatal under plausible query modes; typed/content redundancy often
rescues the basin. Broad random partial notes remain destructive, and adversarial
controls confirm the boundary. Topic-level polysemy remained meaningful: shared
topical inclusion 1.0, +mechanism disambiguation 0.9231.

Updated boundary:

> Canonical recurrence identity has a real destructive perturbation under
> adversarial/broad random deletion, but on LDGR historical findings the boundary
> is often behaviorally acceptable because realistic incomplete/salient/single-gap
> queries retain enough typed recurrence evidence to recover.

Current priority order:

1. keep DP/LCS as the default matcher;
2. do not adopt anchored_recurring;
3. treat first-occurrence deletion as a measured boundary whose relevance depends
   on query behavior, not a universal failure;
4. do not return to role_payload(local), which was falsified.

## Artifacts

```text
experiments/motif-topology-retrieval/
  graph_dataset.py              typed knowledge graph (curated seed)
  signature.py                  typed + label-free canonical signatures (the port)
  generator.py                  role-graph motif generator + prefix-shared polysemy pairs
  relaxation.py                 discrete prefix-consistency pruning index
  bench_relaxation.py           full suite (this report's source)
  soft_relaxation*.py           soft scoring variants
  identity_regimes.py           falsified identity-regime smoke support
  smoke_identity.py             showed role_payload(local) worse than canonical
  matcher_relaxation.py         matcher ablation implementation
  smoke_matcher.py              shows greedy choke vs skip recovery
  bench_matcher_ablation.py     greedy vs DP vs bidirectional vs bag surface
  matcher_ablation_results.json raw matcher-ablation measurements
  basin_results.json            per-family + per-pair raw measurements
  basin_comparison.md           metrics table + gate
  basin_run_summary.json        compact summary
  smoke.py                      signature invariants
  smoke_generator.py            generator invariants
  smoke_relaxation.py           behavior demo (polysemy + perturbation)
```

## Reproduce

```text
python3 experiments/motif-topology-retrieval/smoke.py
python3 experiments/motif-topology-retrieval/smoke_generator.py
python3 experiments/motif-topology-retrieval/smoke_relaxation.py
python3 experiments/motif-topology-retrieval/bench_relaxation.py
```
