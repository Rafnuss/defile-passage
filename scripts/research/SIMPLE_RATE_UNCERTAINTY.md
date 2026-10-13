# Simple uncertainty and retained-hour experiment

Freeze the accepted 22-coefficient mean model and existing 1/3/7-day masks. This experiment adds no predictors or latent-state likelihood and does not refit production. Use the saved outer fits unchanged. Obtain three calendar-week-fold out-of-fold predictions from outer retained observations at that fit's selected smoothing strength. Bases/scales and smoothing have already been estimated from the outer training set; these are cross-validation calibration predictions, not an independent split-conformal sample. No exact exchangeable conformal coverage guarantee is claimed for temporally correlated migration data.

Full-day prediction intervals use empirical quantiles of `abs(count - mean) / (mean + 1)^0.75` from training-only out-of-fold day totals. The 0.75 exponent follows the retained working variance power 1.5; adding one stabilizes low means. Produce central symmetric count intervals at nominal 80% and 95%, truncated at zero and rounded outward to integer count bounds. These are calibrated predictive intervals for the specified observed-effort totals, not confidence intervals for the hourly mean and not a coherent joint simulation across days. Empirical residuals reflect training prediction error, including some estimation error, but do not explicitly propagate coefficient or smoothing uncertainty.

For partial days, hide three adjacent observed intervals in the longest uninterrupted effort run, requiring at least six intervals. Rotate between the beginning, middle and end of that run by season-day modulo three. Choose the gap from effort and calendar only. Intervals may be partial hours; preserve exact exposure. Reveal all other observed intervals on the withheld date only at prediction time. Mean coefficients have never used any counts from that date. This cleanly isolates the benefit of retained-hour adjustment; it differs from an operational fit that might also include retained hours in coefficient estimation. This task compares adjusted versus unchanged weather-model missing counts, without claiming a matched original-model short-gap benchmark.

Multiply the missing mean by `(retained count + s) / (retained mean + s)`. Select `s` from 1, 10, 100, 1000 and infinity by missing-count MAE on training out-of-fold partial days. Infinity means no adjustment. This is one empirical shrinkage rule, not a Gamma-Poisson posterior or a fitted shared day distribution. For calibration residuals, select `s` excluding the calibration row's calendar-week fold; use all outer training calibration rows to select the final test value. Select no species rule from outer test errors. Calibrate separate score distributions for unchanged and adjusted short-gap predictions. Intervals for the observed-effort day total add retained counts to both missing-count bounds; expected day totals preserve the same identity.

Classify full-day weather from all held-out effort and short-gap weather from the missing effort only, using the same ≥0.1 mm/hour exposure-weighted threshold. Assess held-out daily and missing-hour error, interval coverage and width, interval score, zero-count cases and wet/dry calibration by species and scientific group. Report full-day nominal gap lengths separately. Keep core large birds primary, secondary species visible, and runtime explicit. Existing reused-data caveats and unknown-closure scope apply. If calibration fails, report it instead of adding a likelihood/integration stack or treating nominal intervals as operationally calibrated.

Run with single-thread numerical libraries:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/assess_simple_uncertainty.py
```

Outputs are generated under `logs/simple-uncertainty/` and include calibration rows, selected strengths, predictions, coverage/error scores and timing. Production is unchanged. Historical mixed scales, unseen-year forecasting, joint multi-day uncertainty and independent confirmation remain outstanding.

## Completed assessment

The experiment completes all 48 contexts, including 144 training-only calibration refits, at median 0.330 seconds per context (maximum 0.498; summed processing time 16.54 seconds, excluding interpreter startup and final summary output). Maximum calibration-fit gradient is 0.0000865, below the unchanged 0.001 threshold. All 4,191 full-day predictions agree with the saved frozen mean predictions. Of these dates, 4,035 have enough uninterrupted effort for the short-gap test, including 2,508 core species-days. Selected three-interval gaps cover 2.02–3.00 actual hours, mean 2.69. Observed retained counts and their interval shifts reconcile exactly. Independent synthetic checks cover zero retained counts, no-adjustment limits, integer intervals, conservation and held-out prediction under shared daily activity.

| Core missing-count task | Unadjusted MAE | Retained-adjusted MAE | Change | Paired week-bootstrap difference, 95% interval | Species improving |
| ----------------------- | -------------: | --------------------: | -----: | ---------------------------------------------- | ----------------: |
| All short gaps          |          11.59 |                  9.76 | −15.8% | −1.83 [−2.81, −0.83]                           |             10/10 |
| Dry short gaps          |          12.97 |                 10.98 | −15.4% | −1.99 [−3.17, −0.68]                           |             10/10 |
| Wet short gaps          |           6.37 |                  5.14 | −19.4% | −1.23 [−2.14, −0.37]                           |              9/10 |

Median species MAE ratios are 0.818 overall, 0.817 dry and 0.817 wet. Shared-calendar-week bootstrap intervals are exploratory and omit model-selection uncertainty. These results compare two predictions from the same frozen weather mean model, not the original production short-gap architecture. All means on fully missing days remain unchanged because there are no retained counts to use.

Core full-day nominal 80%/95% intervals cover 81.8%/95.2% of counts. Calendar-week bootstrap intervals for those observed coverage proportions are [78.9%, 84.2%] and [93.7%, 96.6%]. Full-day 95% coverage is 95.0% dry and 96.0% wet. By nominal outer gap length it is 96.0%, 95.6% and 94.9% for single-, three- and seven-day gaps; those are marginal daily intervals, not coverage of summed multi-day totals. Across individual core species, full-day 95% coverage ranges from 92.6% (Black Kite) to 97.4% (White Stork).

The original matched production refit's core full-day 95% coverage is 97.0%, mean width 305.0 and interval score 356.5. The empirical weather intervals give width 155.1 and interval score 294.4 while retaining 95.2% observed coverage. At 80%, empirical versus original coverage is 81.8% versus 86.3%, width 80.9 versus 125.8 and score 197.9 versus 210.2. Interval score is lower when a method balances width and misses more successfully; narrowness alone is not an acceptance criterion. Both comparisons reuse development observations and differ in mean model as well as interval construction.

For core adjusted short gaps, nominal 80%/95% coverage is 85.9%/96.7%, and mean widths are 16.7/35.0 birds versus unadjusted 19.7/39.8. The 95% interval score improves from 113.2 to 87.2. Wet short-gap coverage is conservative, 90.6%/97.7%; do not describe the nominal 80% intervals as precisely calibrated. Retained-zero cases reduce mean missing predictions from 2.52 to 1.25 birds and MAE from 2.33 to 1.39. These are pooled row-level diagnostics, while the main comparisons weight species equally. Despite better MAE, total core missing predictions move from 30,171 to 30,553 against 29,332 observed: short-gap aggregate bias is slightly worse (+4.2% versus +2.9%).

Secondary results remain separate. Short-gap MAE falls from 135.92 to 70.05 for pigeons, and from 29.97 to 24.69 for passerines; the passerine overall improvement has a bootstrap interval crossing zero. Adjusted dry pigeon 95% coverage is 93.6%, below nominal. Full-day wet passerine 95% coverage is only 90.4% (Barn Swallow 87.7%, Chaffinch 88.7%, Meadow Pipit 90.4%, Redwing 94.6%), so the same full-day calibration is not established for that group. Do not add post-hoc weather/species corrections from these test errors.

Retain the empirical intervals and single-parameter retained-count adjustment as small research additions for core-species assessment. They do not solve full-day wet mean bias, independent validation, joint multi-day/season-total uncertainty, wholly unseen years, arbitrary-scale predictive distributions or historical recording scope. No production export is changed. The original five-step tracker remains authoritative: this is partial progress on daily-state use and predictive uncertainty, not completion of every item.

`simple_rate_prediction.py` exposes the two small prediction operations. Each `{key}_calibration.npz` contains full-day scores, unadjusted/adjusted short-gap scores and the training-selected strength; the original fit/design artifacts supply the unchanged hourly means. Given missing/retained means summed over the specified effort and an observed retained count:

```python
state = np.load('logs/simple-uncertainty/Red_Kite_fold0_calibration.npz')
point = retained_prediction(missing_mean, retained_mean, retained_count, float(state['strength']))
lower, upper = count_interval(point, state['retained_adjusted_scores'], 0.95)
day_point = retained_count + point
day_lower, day_upper = retained_count + lower, retained_count + upper
```

This example assumes NumPy and the functions from `simple_rate_prediction` are imported. For a fully missing observed-effort day, use the original mean and `full_scores`; do not apply these short-gap scores as universal calibration for any duration. Re-run `review_simple_uncertainty.py` to verify conservation, compare original full-day intervals, bootstrap coverage and compute paired adjustment scores. Outputs also retain per-species/weather/length and zero-count diagnostics. Tests pass (104 repository tests), independent prediction checks pass, and formatting checks pass.

## Follow-up with retained hours included in fitting

The default workflow and its results above remain the clean whole-day-excluded experiment. The script also supports `--prefix short-gaps --out logs/short-gaps-uncertainty --operational`, using newly prepared partial-day mean fits. In that mode, pseudo-gap calibration excludes only missing intervals while retaining counted hours in the calibration fit, uses complete non-target days only, and exports short-gap score states without full-day calibration states. This prevents the former whole-day-excluded calibration from being silently reused as operational calibration. See [SHORT_GAPS.md](SHORT_GAPS.md) for exact matching, original short-gap benchmark, results and outstanding total-bias limitations.
