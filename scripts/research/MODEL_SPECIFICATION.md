# Consolidated weather-model decision

Decision frozen on 12 October 2026. Further experimentation is paused. This document supersedes earlier descriptions of the “current model”; development history is preserved in [archive/](archive/EXPERIMENT_HISTORY.md).

## Choice and intended use

**Retain the hourly mean-rate GAM with radiation and low cloud as the single weather candidate.** It is `weather_soaring` in saved results and `--variants soaring` in `run_era5_features.py`. It offers the strongest overall dry/wet daily point results among the tested small weather extensions, with only two added coefficients. Rain history gives slightly better recent dry and season-total scores, but neither extension meets the historical replacement criterion, and most of its historical dry gain comes from Honey Buzzard. The direct lift alternative does not improve on radiation/cloud's main point estimates. This is a practical research choice, not proof of a universally superior model.

**Keep the original production model for historical season totals and exports.** It remains more accurate on historical dry gaps, particularly early years, and reconstructed seasonal totals. The selected weather candidate is frozen for research point predictions and comparison; no production migration, automated model switching, or combined weather extension is implemented.

## Observation model and temporal scale

Fit each species separately to raw counts and actual observation duration. For observed interval i, whether an hour, part of an hour or an intact survey:

```text
hourly rate:       r_h = exp(eta_h)                         [birds/hour]
interval mean:    mu_i = sum_h A_ih * r_h                  [birds]
A_ih:             hours of actual observed overlap with UTC hour h
```

An unresolved survey total is one response with this integrated mean; it is never artificially split into observed hourly counts. Exact event times permit Trektellen counts to be grouped by hour, but coverage intervals determine which hours were observed, including hours with zero birds. Survey totals and their hourly subdivisions must not both enter the fit. The mean aggregates exactly under the piecewise-constant hourly approximation; within-hour variation is not modeled.

Absent entries count as zero only inside a recorded interval with established species counting coverage. Rain closures and missing effort remain unknown counts, never structural zeros. Historical core eligibility uses the taxonomy coverage table and the user-approved annual-presence restriction; annual presence is a practical scope rule, not independent proof of systematic recording. The user's passerine zero confirmation applies to complete 2022–2025 surveys only.

## Rate specification

```text
eta_h = intercept + year offset + common seasonal smooth(day of year)
        + three UTC clock harmonics (sin and cos for frequencies 1, 2, 3)
        + b1 * log(1 + rain_mm)
        + b2 * max(log(1 + rain_mm) - log(2), 0)
        + b3 * wind_u + b4 * wind_v + b5 * civil_night
        + b6 * radiation_W_m2 / 200 + b7 * low_cloud_fraction
```

The rain hinge and wind components are divided by training-design standard deviations in the implementation. The common seasonal thin-plate basis has seven coefficients (`k = 8`). All effects, including weather slopes and year offsets, are species-specific; seasonal and clock shapes are shared across years within a species. The 1993–2025 design has **53 coefficients per species**: one intercept, 32 year contrasts, seven seasonal coefficients, six clock coefficients and seven weather/night coefficients. A four-year version of the same specification would have 24 coefficients; the completed historical screen used 53.

Clock harmonics use the UTC-hour midpoint, avoiding daylight-spline extrapolation outside its support. Civil sunrise/sunset normalization is used only to identify hours outside civil twilight (`tau < 0` or `tau > 1`), not as a fitted time coordinate. Calendar day of year supplies seasonality. This choice is stable for arbitrary clock hours, but does not let the within-day curve stretch with day length.

ERA5 precipitation and solar energy timestamped t+1 supply the interval \[t,t+1). Precipitation is converted to mm and solar energy is divided by 3,600 to obtain W/m². Low cloud uses the mean of the instantaneous endpoints. The prepared base design supplies aligned wind components. Radiation and cloud are predictors of passage conditions, not direct measurements of thermal lift.

There is **no episode term, daily latent state, retained-count multiplier, duration weight, rain-history block, hurdle component or species-specific model switching**. Retained observations inform the fitted species/year mean, but do not produce an additional day-specific adjustment to a missing hour.

## Fitting and computation

The retained fitting criterion is the unweighted power-1.5 working mean loss, plus a quadratic penalty:

```text
sum_i 2 * (sqrt(mu_i) - sqrt(y_i))^2 / sqrt(mu_i) + beta' P beta / 2
```

This is a working criterion for point means, not a validated generative count likelihood. It does not force retained raw count totals to balance. Weather/night coefficients and year contrasts receive ridge strength one in their stated units. A shared season/clock smoothing strength is selected from 0.1, 1 and 10 by three training calendar-week folds, minimizing daily MAE; no hidden target counts select smoothing.

BFGS uses a 200-iteration limit and target gradient tolerance 1e-5. Independent maximum-gradient and directional-derivative checks must each be below 0.001. All fits in the completed two-extension screen pass these checks; raw solver precision-loss flags are preserved. The selected model's median final fit takes about 0.16 seconds per species/context and smoothing selection plus fitting about 2.2 seconds in the recorded run. This is not an end-to-end production speed comparison.

## Consolidated evidence

Forty fixed contexts cover ten core species: ten historical seven-day-gap tasks and thirty recent whole-day tasks. Weather models train on eligible 1993–2025 data. MAE is an equal-species mean of daily absolute errors in birds per masked recorded day; lower is better. “Wet” means exposure-weighted covered-interval mean rain of at least 0.1 mm/hour.

| Measure                                      | Original benchmark | Basic hourly weather | Selected radiation/cloud | Rain history | Direct lift |
| -------------------------------------------- | -----------------: | -------------------: | -----------------------: | -----------: | ----------: |
| Historical dry MAE                           |              31.52 |                33.40 |                    32.96 |        33.02 |       33.48 |
| Early historical dry MAE                     |              21.52 |                24.45 |                    23.89 |        23.93 |       24.43 |
| Historical wet MAE                           |              24.31 |                20.77 |                    19.92 |        20.57 |       20.06 |
| Recent dry MAE                               |              47.85 |                47.71 |                    47.55 |        47.53 |       47.73 |
| Recent wet MAE                               |              44.68 |                29.91 |                    28.85 |        29.37 |       29.27 |
| Reconstructed-season absolute relative error |             13.27% |               15.83% |                   15.75% |       15.56% |      15.78% |

The selected candidate reduces historical wet MAE about 18% and recent wet MAE about 35% relative to original. Historical dry MAE is about 4.6% worse and early historical dry about 11% worse. Reconstructed-season error increases by 2.48 percentage points; every core species has higher seasonal error than original. Against basic hourly weather, adding radiation/cloud improves wet MAE about 4.1% historically and 3.5% recently; recent dry improvement is only 0.34%, with a paired interval crossing zero. The major gain is weather-sensitive wet-gap prediction, not a solution to historical reconstruction.

Historical original-model comparisons use the matched historical benchmark. The recent original benchmark was trained on recent data only, whereas the weather models use historical training; that comparison describes the tested pipelines, not an isolated causal effect of adding weather. Reconstructed-season truth covers eligible recorded intervals with masked counts replaced, not the unknowable full season including unobserved closures.

Sources: `logs/era5-features/soaring/{group_scores,era_scores,season_scores,paired_scores,paired_season_scores}.csv`, the corresponding `rain_history/` tables, and `logs/era5-lift/{comparison_scores,comparison_season_scores}.csv`. Full protocols and species analyses remain in [ERA5_FEATURES.md](ERA5_FEATURES.md) and [ERA5_LIFT.md](ERA5_LIFT.md).

## Limitations that prevent production replacement

1. **Historical totals and ordinary dry days remain worse.** Daily point accuracy and annual reconstruction are different objectives. Residual local migration availability is a possible limitation despite year offsets and common seasonality; neither the tested episode extension nor daily states solved the total-error problem at acceptable simplicity and performance.
2. **Severe rain closures have little validation truth.** There are no historical target days with covered-interval mean rain ≥3 mm/hour and only ten recent species-day observations. Radiation/cloud slightly worsens the 1–3 mm/hour band despite aggregate wet gains. Missing storm days cannot validate a hard-zero rule, and coarse ERA5 rain may miss local intensity.
3. **Species gains vary.** Honey Buzzard supplies about 62% of the historical dry improvement over basic weather; excluding it diagnostically leaves only a 0.59% gain. Wet improvements are stronger for Buzzard and Red Kite, while Honey Buzzard wet predictions worsen. Core raptors, storks and other large birds define the primary panel; pigeons and passerines do not decide the choice.
4. **Short-gap conditioning remains unresolved.** Recent empirical retained-hour adjustments were tested on earlier specifications. Their gains and coverage do not transfer automatically to this model or historical partial surveys. The selected model has no residual within-day dependence and no local update from retained counts.
5. **Predictive uncertainty is unfinished.** No calibrated count distribution or coherent joint hourly/day/season predictive intervals are implemented for this selected specification. Earlier empirical or hurdle-model intervals are not its uncertainty estimates.
6. **Assessment is exploratory and scope-limited.** Many development comparisons reused masks. Earlier years have less coverage and different recording practices; recent missingness is concentrated in weather closures. Independent confirmation, historical recording scope and genuinely unobserved storm/recovery totals remain unresolved. New years without observed counts also lack an estimated year offset.

## Development closure

No new fits, variable searches, station downloads or correction trials are scheduled. Preserve this small specification and its saved evidence. The unmet requirements above are conditions for any future production reconsideration, not an instruction to start another round of tests. The original five-goal status is in [GAP_FILL_PLAN.md](GAP_FILL_PLAN.md).

## Direct original-plus-rain follow-up (13 October 2026)

The user requested one bounded hybrid test after consolidation. Adding two jointly fitted daily rain covariates to the original GAM improves wet-day MAE but worsens historical dry MAE from 31.52 to 32.39, recent dry MAE from a freshly matched 47.88 to 51.20, and reconstructed-season error from 13.27% to 13.59%. Do not adopt it; the model choice above remains. [ORIGINAL_RAIN.md](ORIGINAL_RAIN.md) records the specification, full comparison and a correction to recent benchmark profile fitting. The original recent benchmark values in the earlier table are saved historical results, not the corrected fresh controls.
