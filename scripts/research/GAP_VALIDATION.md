# Frozen internal gap validation

The accepted development specification is `year_weather`, 22 coefficients, Tweedie working power 1.5 and the existing training-only smoothing selection. No model changes or species switches will be chosen during this assessment. The ten core large birds remain primary; pigeons and passerines are separate secondary groups. This protocol is written before fitting these masks.

Use the existing eligible complete-survey observations for 2022–2025, preserving scope restrictions and hourly empty intervals. All dates already appeared in development holdouts: this is a gap-placement sensitivity assessment, not independent confirmation. Actual weather closures remain unknown, never training zeros.

Define phase `(doy - 3 + 4 * (year - 2022)) % 21`. Withhold phase 0 for isolated-day gaps, phases 5–7 for three-day gaps and phases 12–18 for seven-day gaps. The three masks are disjoint and common across species, independent of bird counts and weather. Dates without eligible observations supply no validation truth, so nominal contiguous calendar gaps need not contain uninterrupted survey effort. Shifted seven-day gaps differ from the original week boundaries. No dry migration peaks are selected using held-out counts; all selected dates contribute, including any peaks they contain.

Refit the original production episode architecture on the exact same retained intervals for each mask, including training-only profile estimation. Compare counts over observed held-out effort; they are not guaranteed complete dawn-to-dusk totals. Freeze the candidate even if these tests worsen. Assess overall, dry and wet daily MAE, median species MAE ratios, shared-calendar-week bootstrap differences, total bias, zero/positive days, gap lengths and heavy-rain calibration. Bootstrap intervals are descriptive internal uncertainty and omit model-selection uncertainty; weekly clusters can split seven-day gaps.

Run from the repository root with `OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1`:

```sh
uv run python scripts/research/prepare_gap_validation.py
Rscript scripts/research/prepare_simple_rate.R logs/gap-validation-input-priority logs/gap-validation-design-priority --all
Rscript scripts/research/prepare_simple_rate.R logs/gap-validation-input-passerines logs/gap-validation-design-passerines --all
uv run python scripts/research/run_simple_panel.py --input logs/gap-validation-design-priority --out logs/gap-validation-priority --variants year_weather --variance-power 1.5
uv run python scripts/research/run_simple_panel.py --input logs/gap-validation-design-passerines --out logs/gap-validation-passerines --variants year_weather --variance-power 1.5
uv run python scripts/research/compare_production.py --input logs/gap-validation-input-priority --out logs/gap-validation-benchmark-priority --folds 0 1 2
uv run python scripts/research/compare_production.py --input logs/gap-validation-input-passerines --out logs/gap-validation-benchmark-passerines --folds 0 1 2
```

Concatenate both benchmark `production_held_out_days.csv` files to `logs/gap-validation-benchmark.csv`, then run:

```sh
uv run python scripts/research/review_simple_gaps.py --prefix gap-validation --design-prefix gap-validation-design --reference logs/gap-validation-benchmark.csv --out logs/gap-validation-review
```

No production export changes. Predictive uncertainty, retained-hour conditioning and historical scope remain later tasks, contingent on these results.

## Completed assessment

All 48 candidate contexts pass unchanged numerical thresholds. Median fitting time is 0.175 seconds including training-only smoothing selection and I/O; maximum 0.329 seconds. Maximum gradient is 0.0000231 and derivative discrepancy 0.0000000234. Both production benchmark panels complete. The review asserts matching counts and exposure for all 4,191 held-out species-days, including 2,608 core species-days. Masks hide 398 species-days for single days, 1,224 for three-day gaps and 2,569 for seven-day gaps.

| Core large birds  | Original MAE | Candidate MAE | Change | Paired week-bootstrap difference, 95% interval | Species improving |
| ----------------- | -----------: | ------------: | -----: | ---------------------------------------------- | ----------------: |
| All selected days |        46.76 |         40.16 | −14.1% | −6.59 [−11.35, −2.39]                          |              9/10 |
| Dry               |        46.93 |         45.19 |  −3.7% | −1.74 [−4.88, +1.75]                           |              4/10 |
| Wet               |        46.34 |         26.91 | −41.9% | −19.43 [−30.91, −10.05]                        |              9/10 |

The median species MAE ratios are 0.921 overall, 1.013 dry and 0.701 wet. Dry-day improvement is therefore an aggregate result, not a consistent species-level gain or demonstrated noninferiority. Honey Buzzard wet MAE is 4.4% worse; wet predicted counts are 910 against 315 observed (original 978). Western Marsh Harrier overall MAE is slightly worse (3.57 versus 3.52).

Core MAE is lower at all tested nominal gap lengths: 35.54 versus 39.84 for one day (−10.8%), 41.06 versus 46.11 for three days (−11.0%) and 40.45 versus 48.15 for seven days (−16.0%). Those are different date sets, so differences between lengths do not estimate a causal effect of gap length. Overall macro MAE is lower within each of 2022–2025; these are within-year gap tests with retained annual observations, not unseen-year validation.

Core selected-day totals are 134,298 predicted against 132,182 counted (+1.6%; original 138,647, +4.9%). Dry totals are 111,889 against 114,176 (−2.0%; original −15.3%). Wet totals remain high: 22,409 against 18,006 (+24.5%; original +132.6%). Across wet zero-count core days, 2,651 birds are predicted versus the original 5,772; across dry zero-count core days the candidate is worse, 5,262 versus 4,793. Positive core-day totals are 106,627 versus 114,176 dry, and 19,758 versus 18,006 wet. Close aggregate totals must not hide these compensating errors or species-specific biases.

Heavy-rain (≥3 mm/hour) core predictions are 135 against 196 observed across 338 held-out intervals. The all-species total is 921 against 605 across 542 intervals, an excess concentrated in secondary species. These small samples do not support a hard-zero rain rule or a new universal stronger rain effect.

Secondary groups remain visible: pigeons overall MAE is 457.16 versus 491.18 (−6.9%), but dry MAE is 590.26 versus 478.33 (+23.4%); passerines overall MAE is 111.56 versus 108.90 (+2.4%) and wet MAE 201.34 versus 188.14 (+7.0%). These results do not support universal deployment across groups.

Keep the unchanged 22-coefficient model for core-species development. No further predictors, episode terms or species switches were introduced. The next development task is a small uncertainty and retained-hour assessment, keeping zero-day and wet calibration visible; independent confirmation needs new observations. No production replacement is made.

Outputs: `logs/gap-validation-review/` contains paired days, group bootstrap scores, per-species weather/length/year/zero-positive scores, heavy-rain counts and numerical diagnostics. `logs/gap-validation-{priority,passerines}/year_weather/` saves coefficients and fits. Scope restrictions are inherited unchanged. Repository tests pass (104) and formatting checks pass.
