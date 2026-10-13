# Diagnose the historical training effect

Keep the recent validation observations fixed to the exact ten-core-species, three seven-day masks used for the earlier positive result. No historical observation is validation truth in this experiment. Change training data only, under the unchanged year/season/UTC-clock/rain/wind/night working mean model and variance power 1.5.

## Frozen controls

- `recent`: original recent hourly inputs; reproduce the saved coefficients and selected smoothing.
- `recent_coarse`: aggregate only connected retained hours within their original survey into intact totals. Keep hidden hours unchanged. This isolates the training-resolution effect without changing birds, effort, years or weather.
- `late_history`: original recent inputs plus eligible actual 2014–2021 historical intervals.
- `all_history`: original recent inputs plus eligible actual 1993–2021 historical intervals.

All historical intervals are training observations. No hidden recent count is used for fitting, basis construction, scaling or smoothing selection. Preserve the adopted historical recording scope and unsupported-date exclusions. Rebuild the same specification for each arm, with unit-ridge year offsets for every observed year and the original training-only smoothing grid. The later-versus-full history comparison identifies the incremental influence of 1993–2013, but does not separate recording resolution from historical period within those actual data.

Compare daily missing-count errors paired on the same species-date/fold. Report dry/wet, species/year, median species ratios, total bias, and the change in smoothing and physical weather response. Bootstrap calendar weeks jointly across species. Compare seasonal and clock curves after normalization on common recent coordinates, so an arbitrary basis or intercept change cannot be mistaken for a biological effect. These reused recent development masks diagnose the fitted-data change; they do not supply independent confirmation or historical closure truth.

The exact interval mean is additive, but a Tweedie working loss with power 1.5 is not invariant to aggregating observations. In particular, the equal-rate loss for an interval grows with the square root of its duration, whereas summing hourly losses grows linearly with duration. Coarsening can therefore change fitting weights as well as remove timing information. This is a hypothesis to check with the resolution control, not a prespecified explanation of the historical result.

## Reproduce

```sh
uv run python scripts/research/prepare_history_diagnosis.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 Rscript scripts/research/prepare_historical_transfer.R logs/history-diagnosis/input logs/history-diagnosis/design
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_history_diagnosis.py
```

Generated artifacts are in `logs/history-diagnosis/`. Source hashes and count/exposure audits preserve the frozen comparison. No production change or redesigned candidate is introduced.

## Completed controlled comparisons

All 120 unchanged mean-model fits completed. All 30 recent-only contexts reproduce saved recent coefficients and smoothing within 1e-7; validation counts and hours match across all arms. Group daily missing-count MAE is:

| Training arm                   | All recent days |   Dry |   Wet |
| ------------------------------ | --------------: | ----: | ----: |
| Original recent hourly         |           41.46 | 47.05 | 27.23 |
| Same recent training coarsened |           41.35 | 47.06 | 26.79 |
| Recent + 2014–2021             |           41.11 | 46.47 | 27.47 |
| Recent + 1993–2021             |           41.47 | 46.65 | 28.25 |

There is no group-wide deterioration from adding history. The paired all-history minus recent-only difference is +0.003 birds [−1.03, +0.98] overall, −0.40 [−1.62, +0.84] dry and +1.02 [−0.08, +2.14] wet. Coarsening does not explain the discrepancy on these recent controls. Historical training changes the estimated shapes and weather response, but does not erase the earlier recent predictive advantage.

Species shifts remain relevant: six of ten worsen overall after adding all history, while Red Kite improves 5.31 birds and offsets smaller losses. Honey Buzzard worsens 1.32, White Stork 1.75, Black Kite 1.21 and Grey Heron 1.10 birds overall; Grey Heron's wet MAE rises 9.54 → 13.06. The aggregate stability must not be interpreted as stability for every species. Recent year-specific overall errors change only slightly: 38.79 → 39.18 in 2022, 36.10 → 35.88 in 2023, 40.90 → 40.78 in 2024 and 49.91 → 49.92 in 2025.

The median modeled rain multiplier at 3 mm/hour changes from 0.166 in recent-only fitting to 0.403 with all history, holding time, season and wind fixed. Actual historical training therefore estimates weaker rain suppression. This is an estimated response difference, not evidence identifying whether rainfall accuracy, weather context, recording practice or passage dynamics caused it. Mean normalized seasonal and clock shapes also change; coefficient drift alone does not establish predictive deterioration.

## Input audit and current recent confirmation

The count.csv and survey.csv hashes in the earlier hourly input metadata match the current release; taxonomy.csv changed. The data differences arise from analytical preparation, not established count-file revisions. The earlier hourly test covered a longer season and required fully resolved intervals within civil daylight; the latest historical test restricted dates to the fixed comparison season and accepted intact recent survey totals. Within matching dates, eligible core bird totals rise from 255,288 to 264,092. In particular, 2022 Honey Buzzard rises from 2,014 to 4,482 when unresolved totals enter the model. The matched-window audit is `recent_matched_window_audit.csv`. The old and new total counts cannot be compared without aligning their seasons and eligibility rules.

Thirty new recent fits and matched original-model refits use the current accepted mixed intervals and the same seven-day calendar masks. The original's hourly profile is trained only on retained recent observations; no hidden observation enters it. Results are:

| Current recent task | Original | Weather mean | Change |
| ------------------- | -------: | -----------: | -----: |
| All days            |    46.93 |        42.05 | −10.4% |
| Dry                 |    47.85 |        47.39 |  −1.0% |
| Wet                 |    44.68 |        29.03 | −35.0% |

Eight of ten improve overall, five improve dry and all ten improve wet. Thus the earlier recent advantage survives the updated input definition. This is another exploratory comparison, not independent confirmation or direct validation of unobserved weather closures.

## Where the historical loss occurs

A thirty-fit historical control removes rain and wind, preserving the same seasonal/time basis, year offsets, observations and smoothing protocol. All historical one-, three- and seven-day masks give:

| Historical task | Original | Weather mean | Same small model without weather |
| --------------- | -------: | -----------: | -------------------------------: |
| All days        |    29.03 |        29.90 |                            31.33 |
| Dry             |    29.92 |        31.89 |                            32.08 |
| Wet             |    25.39 |        21.70 |                            28.27 |

Weather helps the small model on history too, including a small dry improvement. Removing weather is not a solution. The historical overall loss against the original is approximately 3.0%, with wet improvement and dry deterioration; it is a different validation population, not evidence that adding history destroyed recent predictions.

For 1993–2007 dry positive-count days, mean error is 40.14 original versus 45.55 weather. For dry zero-count days it is 1.89 versus 2.73. Losses therefore include missed positive passage, not only spurious predictions on zero days. Residuals on consecutive hidden dates cluster more for the weather model: median within-species correlation of asinh(count) − asinh(prediction) is 0.460 versus 0.315 in the earliest era. This descriptive correlation alone cannot identify a missing model component.

## Direct benchmark time ablation

To distinguish changing long-term passage timing from within-year episodes, refit four original-model variants on the same ten-species seven-day historical task: full, without the year × season shift, without episodes, and without both. Reestimate remaining coefficients, smoothing and dispersion under the original rules. No weather mean model is changed. All ten full-model predictions reproduce the saved benchmark within 1e-6. The forty benchmark fits support this early-era dry comparison:

| Original-model variant, 1993–2007 dry seven-day gaps |   MAE |
| ---------------------------------------------------- | ----: |
| Full                                                 | 21.52 |
| Without passage-timing shift                         | 21.54 |
| Without within-year episodes                         | 23.28 |
| Without both                                         | 23.10 |
| Weather mean, same task                              | 24.45 |

The episode component explains part of the original's early dry-gap advantage; the long-term shift has little effect on this particular task. Other differences remain, including seasonal flexibility, count criterion and uncertainty averaging. This does not prove that a weather-plus-episode candidate will win, nor that measured local weather can never explain these episodes.

## Revised decision

Retain the simple weather model as a promising development candidate. The recommendation to move directly to a wholesale redesign was premature. It remains better on recent data and historical wet gaps; actual early historical dry gaps expose a specific limitation in capturing residual temporal passage variation.

The bounded historical episode comparison is completed in [HISTORY_EPISODE.md](HISTORY_EPISODE.md). A four-coefficient-per-year candidate improves historical dry MAE 1.9% and preserves recent group gains, but fails its prespecified historical gain and relative runtime gates. The shared seasonal control is also completed in [HISTORY_SEASON.md](HISTORY_SEASON.md): increasing seasonal capacity slightly worsens historical dry and season-total accuracy under the unchanged fitting rules. Keep the small weather model primary; adopt neither extension. Pause further smooth additions and assess the working criterion and mixed-interval weighting before another model. These results do not negate the original-model ablation evidence or establish that all episode structures fail.

All 180 mean fits pass the unchanged numerical thresholds (maximum gradient 0.0000229; derivative discrepancy 0.0000000299). All 104 repository tests and formatting checks pass. The forty original-model time ablations are separate from those mean-fit numerical checks. Production remains unchanged.

Follow-up reproduction:

```sh
uv run python scripts/research/prepare_history_followup.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 Rscript scripts/research/prepare_historical_transfer.R logs/history-diagnosis/current-recent/input logs/history-diagnosis/current-recent/design
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_historical_counts.py --root logs/history-diagnosis/current-recent
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_simple_panel.py --input logs/history-diagnosis/historical-clear/design --out logs/history-diagnosis/historical-clear/fits --variants year_clear --variance-power 1.5
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/diagnose_benchmark_time.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/review_history_diagnosis.py
uv run python scripts/research/review_history_followup.py
```
