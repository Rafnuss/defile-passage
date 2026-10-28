# Minimum daily coverage experiment

This experiment tests `trend.MIN_COVERAGE`, 0.10 before calibration and now 0.20: the share of a species' expected daily passage covered by the observation intervals, rather than a fraction of clock hours. Below the cutoff, production excludes the day's count and coverage from fitting and Gamma–Poisson conditioning, keeps its birds in `extra`, and predicts the unobserved daily level. This differs from the empirical ratio's separate 50% cutoff (`profile.COVERAGE_MIN`). The production cutoff is now 20%; existing exports require a rebuild to reflect it.

## Design

Eight fixed candidates: 0%, 1%, 2.5%, 5%, 10%, 20%, 30% and 50%. Fit the current production daily GAM, including its nine weather terms, independently at each threshold, re-estimating smoothing and dispersion. Use the ten existing core species, their 1993–2025 observation inputs (including weather stops), and five existing development mask draws. Do not use lockbox outcomes to choose a threshold.

Two complementary assessments use the same target dates and hidden observations for every threshold:

- **Realistic masks:** existing whole-day and early-end masks. The early-end cases usually retain high coverage, so this mostly tests how excluding short days affects the fitted model and whole-day prediction.
- **Short mornings:** take recent hourly dates selected by the existing whole-day masks, requiring at least six intervals, no interval longer than an hour, and no weather-stop intervals. On each date retain a morning prefix near one of 1%, 2.5%, 5%, 10%, 20%, 30% or 50% coverage, balanced and shuffled with a fixed seed. Cut only between recorded intervals; keep at least one interval and hide at least one. Coverage used to choose the cut comes from a profile trained with all these target dates excluded. Refit the prediction profile using only observations surviving the cuts. This is a deliberate stress test, not an estimate of how frequently such gaps occur.

Recompute interval effort rather than using the historical cache's row-count-only key. Estimate each fold's time-of-day profile from retained hourly observations from 2014 onward, without hidden counts. Compute weather terms with production's weather reader and standardise them on the days retained at that threshold. Coarse historical daily counts are never subdivided.

## Predictions and scores

Use the posterior predictive **mean**, matching exported daily means and seasonal means. Integrate the conditional Gaussian coefficient uncertainty with 64-node Gaussian quadrature and the Gamma–Poisson/flock means analytically; compare with 32 nodes as a numerical check. This removes count-simulation noise from differences between cutoffs. For an unobserved day the integral is the exact log-normal mean. These scores do not assess predictive interval calibration.

When a partially retained target falls below the cutoff, production adds its retained birds and predicts over their coverage as well. The primary `predicted` score includes that effect: it compares the reconstructed observed-day total with its known total after subtracting the unchanged retained birds from both. `hidden_only` predicts just the genuinely hidden intervals; it is a diagnostic showing the effect of removing the additional coverage. It does not silently replace production's rule.

Primary scores are daily mean absolute error in birds and seasonal absolute reconstruction error, `abs(sum(predicted - hidden_count)) / observed_season_total`. The latter is the reconstruction error induced by artificial gaps relative to the known counted season; it does not validate naturally unobserved passage. Score species equally, with mask draws averaged, including zero-count targets. A season comprises the input observation window. Paired bootstrap intervals resample years jointly across species and masks (2,000 replicates); repeated masks are not treated as independent years. Comparisons across eight candidate cutoffs are exploratory, without an independent confirmation set or a multiple-comparison adjustment. The core panel contains raptors, storks, herons and cormorants; it cannot establish a universal cutoff for pigeons and passerines.

## Reproduce

From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python scripts/hierarchical/coverage_threshold.py --workers 4
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python scripts/hierarchical/coverage_threshold.py --workers 4 --mask-mode low-coverage --out logs/hierarchical/coverage-threshold-low
```

Results are under `logs/hierarchical/coverage-threshold/` and `logs/hierarchical/coverage-threshold-low/`: per-species daily predictions and fit diagnostics, saved short-morning masks, `summary.csv`, `season.csv`, `by_species_year.csv`, and `paired_intervals.csv`. `run.json` records source/input hashes and run options; the initial realistic batch's provenance was recorded after the run because metadata recording was added during development. `--summarise-only` recalculates scores from saved predictions. Generated data remain uncommitted.

## Results (28 October 2026)

All 800 fits completed: 400 for realistic masks (19,552 held-out species-days) and 400 for short mornings (4,908 held-out species-days, including 2,314 retaining less than 10% coverage). Species-days repeat across the five mask draws; they are not independent replicates. The largest 32-versus-64-node quadrature discrepancy was below `2.6e-15` relative to `1 + predicted intensity`. A final check found only one zero-coverage retained morning, with zero retained birds; the exact zero-coverage integral therefore does not change any saved scores.

| Cutoff | Realistic daily MAE (birds) | Realistic season error (%) | Short-morning daily MAE (birds) | Short-morning season error (%) |
| ------ | --------------------------: | -------------------------: | ------------------------------: | -----------------------------: |
| 0%     |                      17.644 |                      3.581 |                          25.971 |                          2.733 |
| 1%     |                      17.415 |                      3.535 |                          25.969 |                          2.721 |
| 2.5%   |                      17.374 |                      3.536 |                          24.896 |                          2.415 |
| 5%     |                      17.404 |                      3.545 |                          24.005 |                          2.412 |
| 10%    |                      17.407 |                      3.530 |                          23.520 |                          2.309 |
| 20%    |                      17.394 |                      3.529 |                          23.009 |                          2.213 |
| 30%    |                      17.445 |                      3.634 |                          24.182 |                          2.352 |
| 50%    |                      18.107 |                      4.499 |                          25.225 |                          2.540 |

Twenty percent has the lowest seasonal error in both assessments and the lowest short-morning daily MAE. Compared with 10%, its realistic-mask gain is negligible: daily MAE −0.073%, season error −0.024% relatively (−0.00083 percentage points). The short-morning gains are more promising: daily MAE −2.17%, season error −4.15% relatively (−0.0959 percentage points). Only five of ten species improve their short-morning seasonal error, and four of ten improve their realistic-mask seasonal error.

Year-cluster bootstrap 95% intervals for **20% minus 10%**:

| Assessment      | Daily MAE difference (birds) | Season-error difference (percentage points) |
| --------------- | ---------------------------: | ------------------------------------------: |
| Realistic masks |           [−0.0733, +0.0601] |                          [−0.0249, +0.0253] |
| Short mornings  |           [−1.1230, +0.2586] |                          [−0.2500, +0.0293] |

All four intervals include zero. The realistic-mask seasonal score clearly worsens at 30% and 50%; the 50% short-morning daily score also worsens. Retaining every tiny-coverage observation (0%) worsens daily accuracy in both assessments. There is evidence for keeping a positive coverage floor, but no uniquely optimal cutoff is established.

**Decision (updated at the user’s request):** adopt 20% as the calibrated production default. It has the lowest seasonal error in both assessments and the lowest short-morning daily error. The user prefers the best value from the completed calibration over retaining an arbitrary 10% while seeking a precisely established optimum. The uncertainty intervals and species differences remain limitations, not reasons to delay this practical choice. No further calibration batch is needed; the ten-species panel does not establish performance for pigeons and passerines. Do not select species-specific thresholds from this table. Very low-coverage counts can be informative but sometimes represent bursts that should not determine a day's rate; raising the floor too far discards useful observations and adds systematic excess through production's `extra` rule. The `hidden_only` diagnostic at 20% has short-morning MAE 21.998 and season error 2.163%, compared with the primary scores 23.009 and 2.213%; this quantifies that rule's contribution without changing it.

Validation: the independent numerical-integration test passes; the full suite reports 109 passed and one existing data reconciliation failure (`test_real_release_reconciles`, copied release versus the neighbouring dataset's interim daily table). Whole-repository pre-commit reports existing formatting issues in unrelated tracked files; its unrelated edits were reverted. Formatting and spelling hooks pass on this experiment's files.
