# Set-Valued Suffix Prediction Tradeoff Analysis

## Summary

This experiment tested whether topology still compresses the future trajectory problem when strict unique prediction is unavailable. Instead of requiring one continuation, the predictor returns a bounded set of compatible suffixes and abstains when the set is too large.

Outcome: **supported**.

The best predeclared operating point is `N=3`: coverage reaches `0.88`, positive inclusion is `1.0`, control full-acceptance is `0.0`, mean suffix set size is `2.090909`, and mean remaining prediction length is `3.181818`.

## Results by Suffix-Set Limit

| N | Coverage | Positive inclusion | Control acceptance | Mean set size | Mean observed fraction | Mean remaining length | Compression factor | Passed |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.70 | 1.0 | 0.0 | 1.0 | 0.677041 | 2.828571 | 50.0 | no |
| 2 | 0.80 | 1.0 | 0.0 | 1.55 | 0.632609 | 3.125 | 32.258065 | no |
| 3 | 0.88 | 1.0 | 0.0 | 2.090909 | 0.617722 | 3.181818 | 23.913043 | yes |
| 5 | 0.92 | 1.0 | 0.0 | 2.913043 | 0.591149 | 3.391304 | 17.164179 | yes |

## Interpretation

Strict uniqueness was too brittle: it covered only 70% of motifs. Set-valued retrieval gives a better formulation of the memory behavior.

The stored motif library acts like compressed possibility retrieval:

```text
observed topology -> small compatible suffix set -> later evidence/reasoning can disambiguate
```

At `N=3`, the system covers 88% of motifs while reducing the 50-motif library to about two compatible suffixes on average. This is a strong compression of the future trajectory search space without accepting the tested divergent controls.

## Refined Claim

The defensible claim is now:

> Identity-free recurrent temporal motif memory can retrieve small sets of compatible future trajectories from partial topology, producing a useful coverage/specificity tradeoff without requiring universal unique prediction.

This is narrower than exact prediction but more robust than the uniqueness framing.

## Validation

Latest validation command:

```text
dev run py_check
```

Observed:

- Ruff format check passed.
- Ruff lint passed.
- Mypy passed.
- Pytest passed: `21 passed`.
- `uv run python src/set_valued_prediction_experiment.py` regenerated deterministic supported results.
