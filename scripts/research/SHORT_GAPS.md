# Retained observations in short-gap filling

The earlier clean test excluded whole target days from fitting and revealed retained counts only at prediction time. This assessment now addresses the practical setup: should retained hours inform the mean fit, and is a further retained-count adjustment useful after that? Freeze the 22-coefficient specification, the three existing calendar masks, and the exact early/middle/late three-interval gaps. No new model terms or species exceptions are introduced. Core large birds remain primary; secondary groups and all species remain visible. This protocol is written before fitting.

Refit the mean model while excluding only missing intervals on target dates, keeping their retained observations in training. Rebuild all outer training-only bases, scales and smoothing. Compare unadjusted and retained-adjusted missing counts against the earlier whole-day-excluded predictions on exactly matching target gaps. Refit the original production architecture on those same partial-day training intervals and missing targets. Its existing retained-count conditioning is part of the benchmark; do not use cached full-day benchmark predictions for this different task.

For operational shrinkage/interval calibration, use only complete non-target days as pseudo-gap calibration cases. In each of three calendar-week groups, remove their pseudo-gap counts while keeping their retained observations in the calibration fit, as in the operational target task. Actual target missing counts are excluded from every fit. Select the pseudo-count from training calibration missing-count errors and cross-select it for residual scores as before. Bases, scaling and smoothing still use the outer training data: these are approximate cross-validation calibration intervals, without independent conformal coverage guarantees. The former whole-day-excluded experiment remains unchanged and separately labeled.

Classify weather from exact missing effort. Assess missing-count MAE, bias, zero missing counts, retained-zero cases, early/middle/late position, retained rain versus gap rain, interval coverage/width/score, species results and shared-calendar-week bootstrap differences. Preserve counted-plus-missing totals and their interval shifts. Original calendar fold labels identify sets of target dates, not short-gap durations. Actual gaps cover approximately two to three real hours. All observations have been used in previous internal assessments; no independent confirmation or validation of unknown weather closures is claimed.

Run preparation, `prepare_simple_rate.R`, `run_simple_panel.py --variants year_weather --variance-power 1.5` and `compare_production.py --folds 0 1 2` using `short-gaps-input-{panel}`, `short-gaps-design-{panel}`, `short-gaps-{panel}` and `short-gaps-benchmark-{panel}` for both panels. Then run:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/assess_simple_uncertainty.py --prefix short-gaps --out logs/short-gaps-uncertainty --operational
```

Keep numerical libraries single-threaded and do not inspect running fits. Production remains unchanged. A further adjustment is accepted only as a research addition if its completed matched assessment supports it; no iterative patches are planned in this experiment.

## Completed matched assessment

All 48 operational mean fits pass the unchanged numerical checks. Median time is 0.187 seconds per fit including training-only smoothing selection; maximum 0.251 seconds. Maximum mean-fit gradient is 0.0000245 and derivative discrepancy is 0.0000000217. Training-only operational calibration also completes all 48 contexts, including 144 calibration fits. No new optimizer, predictor or latent distribution was added. Matching assertions cover counts and actual missing exposure across all five prediction methods for 4,035 species-day gaps, including 2,508 core cases (1,985 dry and 523 wet). Gaps match the earlier assessment exactly; they span 2.02–3.00 real hours.

| Core short-gap model                                        | Overall MAE | Dry MAE | Wet MAE |
| ----------------------------------------------------------- | ----------: | ------: | ------: |
| Whole date excluded, no update                              |       11.59 |   12.97 |    6.37 |
| Whole date excluded, retained update                        |        9.76 |   10.98 |    5.14 |
| Retained hours included in fit                              |       11.33 |   12.68 |    6.21 |
| Retained hours in fit, plus update                          |        9.75 |   10.97 |    5.12 |
| Original production architecture, matched partial-day refit |        9.97 |   11.26 |    5.07 |

Using retained hours in the mean fit alone improves overall MAE 2.3% versus excluding the day, with all ten core species improving. The further retained update improves another 14.0% overall, 13.5% dry and 17.5% wet. All ten core species improve overall and dry; eight improve wet. The median species MAE ratio versus the unadjusted operational fit is 0.836 overall. Exploratory shared-week bootstrap differences for the additional update are −1.58 [−2.48, −0.58] overall, −1.71 [−2.82, −0.41] dry and −1.09 [−1.99, −0.17] wet. Thus the retained update remains useful even when retained hours have already informed the global mean fit; the simple seasonal/time coefficients do not absorb all daily residual activity.

Against the original model, adjusted core MAE is only 2.2% lower overall, 2.6% lower dry and 1.1% higher wet. Paired differences are −0.22 [−0.77, +0.33] overall, −0.29 [−0.90, +0.32] dry and +0.06 [−0.93, +1.01] wet. Only four of ten species improve overall versus original and the median species ratio is 1.007. This establishes comparable aggregate performance, not superiority or formal noninferiority to the original short-gap model. Without the update, the weather model is 13.7% worse overall than original, and only one core species improves.

## Where retained information helps

The additional update reduces core MAE for early gaps from 11.20 to 10.98, middle gaps from 14.59 to 11.98 and late gaps from 8.22 to 6.04. There are 932 early, 782 middle and 794 late cases. Positions occur on different dates and should not be interpreted as a controlled causal comparison of gap timing. Relative to original, adjusted early/late MAE is lower but middle MAE is higher (11.98 versus 11.10).

When retained and missing hours are both dry (1,747 cases), the update reduces MAE from 13.01 to 11.35. When retained hours are wet but missing hours dry (238), it reduces MAE from 10.26 to 8.22. When both are wet (440), it reduces MAE from 6.53 to 5.22. When retained hours are dry but the missing gap wet (83), it slightly worsens MAE from 4.83 to 4.96, although original is worse at 6.44. These subsets use separately exposure-weighted rain over retained and missing intervals. They are diagnostics, not justification for a post-hoc weather switch.

For retained-zero days (1,150 cases), species-balanced MAE falls from 3.12 to 1.98 after the update, but original remains better at 1.36. For missing-zero gaps, predicted passage/MAE falls from 4.23 to 2.95, still above original 2.12. Retained zero counts should inform a lower rate without forcing missing counts to zero. Results for less than half the effort retained cover only 28 core cases and do not establish performance for sparse within-day coverage. Above three-quarters retained, there are 1,630 cases; the middle retained-coverage band has 850. The simple update improves both larger bands.

Core missing totals are 29,332 observed, 30,277 predicted without the update (+3.2%), 30,936 with it (+5.5%) and 29,620 from original (+1.0%). The update improves daily allocation while worsening aggregate bias, especially dry totals: 28,195 against 26,574 (+6.1%; original +0.3%). Wet totals are close: 2,741 against 2,758 (−0.6%; original +7.2%). Do not treat lower MAE as proof of better seasonal totals.

## Uncertainty and secondary species

Operational adjusted core short-gap nominal 80%/95% intervals cover 86.3%/96.6%, versus original 90.9%/96.0%. Their mean widths are 16.9/35.0 birds versus original 25.6/51.2. The 95% interval score is approximately equal, 89.94 versus 90.22; the 80% score is worse, 53.01 versus 48.60. Wet-gap 95% interval score is also worse, 57.70 versus 45.67, despite 97.3% coverage. Do not judge uncertainty solely by narrower intervals or aggregate coverage. These are still approximate cross-validation-calibrated marginal intervals.

Pigeon overall MAE is 68.75 after the update versus 127.91 without it and original 82.38; passerines are 25.77 versus 27.62 and original 26.80. For passerines, the update improves dry MAE but worsens wet MAE versus the unadjusted operational fit (56.04 versus 54.18); secondary groups do not set the core decision. Two of 48 training contexts select the explicit no-update option, with the remaining strengths selected from the existing pseudo-count grid. No choice uses outer missing-count errors.

## Decision

Retained observations should inform short-gap filling. Include their observed intervals in the mean fit and retain the small, training-selected update as a research prediction option: it improves core-species error beyond merely including those hours in fitting. Keep the 22-coefficient architecture and do not add episodes or new conditional weather rules from these masks. This extension approximately recovers the original model's aggregate short-gap accuracy while retaining the previously assessed full-day weather model; short-gap superiority, total calibration and universal interval calibration are not established. Production remains unchanged, and the original remains the operational reference.

The immediate follow-up is to address the discrepancy between per-gap error and total bias before operational use, using a clearly stated prediction target rather than another predictor. Independent observations, longer/shorter and very sparsely retained gaps, and joint season-total uncertainty remain unvalidated. All tests are internal on previously used observations, not unknown closure truths.

The small selector shared by preparation and assessment is `short_gap_mask` in `simple_rate_prediction.py`; independent checks verify effort breaks and count independence. `assess_simple_uncertainty.py --operational` calibrates on complete non-target pseudo-gap days with retained hours in their fitting data. `review_short_gaps.py` saves exact matched predictions, group/species scores, totals, position/weather/coverage/zero/year strata with sample sizes, and paired week-bootstrap comparisons under `logs/short-gaps-review/`. Saved fit coefficients and calibration states remain available. Repository tests (104), independent prediction checks and formatting checks pass.

After the operational assessment, run `OPENBLAS_NUM_THREADS=1 uv run python scripts/research/review_short_gaps.py` for the complete matched comparison. `uv run python scripts/research/check_simple_prediction.py` runs the independent prediction/mask checks. The preparation and fit commands use the same documented scripts as the full-day workflow, with the `short-gaps` paths above; the benchmark review reads the two panel outputs directly without a manual concatenation step.

## Follow-up: bias sources and alternative adjustment functions

The user requested species/year diagnosis and questioned the pseudo-count and coverage dependence. [ADJUSTMENT_FUNCTIONS.md](ADJUSTMENT_FUNCTIONS.md) separates baseline bias (+945 core birds) from the adjustment increment (+659): most net excess is Cormorant morning prediction, while most adjustment-added excess is Buzzard/Red Kite. Fixed `s` already varies the ratio weight as expected retained count changes. Training-only comparisons of constant, coverage and bounded response rules do not establish a universally better replacement. Bounded response improves core MAE and pooled bias but worsens some species totals and underestimates wet passage. Keep the existing adjustment and bounded alternative distinct; no production change or post-hoc correction is made.
