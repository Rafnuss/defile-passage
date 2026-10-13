# Original model plus rain

User-requested bounded follow-up, 13 October 2026. Production remains unchanged. This reopens one comparison after consolidation; it does not restart the earlier model-search queue.

## Prespecified comparison

Keep the original negative-binomial daily GAM, including its trend, year levels, shared season, changing phenology and year-specific episodes. Add exactly two species-specific coefficients, fitted jointly with every original coefficient:

```text
count_d ~ NegativeBinomial(c_d * exp(eta_original,d + b1 R1,d + b2 R2,d), theta)
R1,d = sum_s profile_d,s * log(1 + rain_d,s)
R2,d = sum_s profile_d,s * max(log(1 + rain_d,s) - log(2), 0)
```

The original five-minute solar passage profile supplies weights summing to one over the full day. Each slot takes ERA5 rain from its corresponding UTC hour, using the previously checked accumulation convention. Both covariates are divided by their standard deviations on retained fitted days only. Each rain coefficient has fixed Gaussian prior precision one in those standardized units. Original smoothing parameters and negative-binomial dispersion are re-estimated by the existing Laplace/IRLS machinery. There is no additional smoothing grid, weather switch, correction multiplier or sign constraint. Positive rain slopes, if fitted, must be reported rather than silently truncated.

Full-day weather summaries are available for counted and uncounted dates; hidden counts never enter profile fitting, rain scaling or parameter selection. Rain effects are learned from counted weather conditions, with episodes still representing residual temporal structure. These effects need not be separately identifiable biologically.

Use the frozen forty contexts: ten historical seven-day tasks and thirty recent whole-day tasks, covering all ten core species. For a fair addition-to-original test, retain the original training scope: eligible historical plus recent observations in historical contexts, recent observations only in recent contexts. Refit the original control on identical observations and check saved benchmark reproduction. The historical control reproduces the consolidated scores at the displayed precision. The old recent runner cached a species profile across folds; the new comparison uses a separate retained-only profile in each fold for both arms, so the fresh control is the recent reference. Compare the saved 53-coefficient hourly radiation/cloud candidate on the same target days, recognizing its broader historical training in recent contexts.

The primary decision is whether adding rain improves historical and recent wet-day error while preserving historical dry, early historical dry, recent dry and reconstructed-season accuracy versus original. Report all point estimates, paired year/week bootstrap differences, species/year/era results and runtime. Do not tune from these outer results. The seasonal measure replaces hidden recorded counts within eligible historical recorded totals; it is not validation of unknown full-season totals.

## Reproduction

Run from the repository root, with existing frozen inputs and weather snapshot. The runner supports independent species shards via `--shard INDEX COUNT`.

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_original_rain.py > logs/original-rain-run.log 2>&1
uv run python scripts/research/review_original_rain.py > logs/original-rain-review.log 2>&1
```

Results and fitted coefficients are retained under `logs/original-rain/`. Production code and exports are unchanged.

## Limits

This is a daily extension, not exact integration of a nonlinear hourly rain response: `exp(weighted log rain effect)` differs from averaging hourly rates. Rain during counted versus missed portions of a day is not handled separately. The original profile, coverage cutoff and daily count aggregation remain, including their partial-day assumptions. This first comparison therefore assesses whole-day gaps, not short-gap improvement. The two extra coefficients do not make the original model smaller or necessarily faster.

Rain and episodes can explain overlapping variation. Severe-rain closures still lack observed count truth; ERA5 remains spatially coarse. The reused assessment masks provide exploratory evidence, not independent confirmation. Coefficient draws are used to reproduce the original point-prediction convention; no calibrated predictive intervals or joint seasonal uncertainty are claimed for this hybrid.

## Results

All forty contexts completed for both arms. The comparison uses the fresh, matched original control; the historical original values reproduce the consolidated benchmark at the displayed precision. Recent original values change slightly because of the profile correction described below.

| Measure                                                 | Matched original | Original + rain | Retained hourly radiation/cloud |
| ------------------------------------------------------- | ---------------: | --------------: | ------------------------------: |
| Historical daily MAE, all days                          |            30.06 |           29.58 |                           30.32 |
| Historical dry-day MAE                                  |            31.52 |           32.39 |                           32.96 |
| Early historical dry-day MAE                            |            21.52 |           22.36 |                           23.89 |
| Historical wet-day MAE                                  |            24.31 |           18.53 |                           19.92 |
| Recent daily MAE, all days                              |            47.00 |           44.58 |                           42.12 |
| Recent dry-day MAE                                      |            47.88 |           51.20 |                           47.55 |
| Recent wet-day MAE                                      |            44.85 |           28.43 |                           28.85 |
| Historical reconstructed-season absolute relative error |           13.27% |          13.59% |                          15.75% |

Rain improves historical wet MAE by 23.8% and recent wet MAE by 36.6%. However, historical dry MAE worsens 2.8%, early historical dry 3.9%, and recent dry 6.9%. No core species improves historical dry error; only one improves recent dry error. Wet error improves for eight of ten species historically and all ten recently. Season error worsens by 0.32 percentage points, with only Black Kite and Common Buzzard improving. This is a much smaller seasonal loss than the hourly candidate, but it is still a loss against original.

Joint year/week bootstrap differences (hybrid minus matched original, birds/day) are historical dry +0.87 [0.32, 1.44], historical wet −5.78 [−8.05, −3.63], recent dry +3.32 [0.71, 6.47], recent wet −16.42 [−22.26, −11.33]. Aggregate daily changes have intervals spanning zero. The wet advantage over the hourly candidate also has intervals spanning zero. These intervals describe reused development masks and do not establish independent confirmation.

The wet gain comes with a dry loss even though rain covariates are zero on rain-free days: jointly fitting rain changes the intercept, seasonal/year/episode coefficients, smoothing and dispersion. Suppressing rainy fitted means can raise the fitted weather-free level. That is a plausible explanation of the tradeoff, not a completed component-by-component attribution.

**Decision: do not adopt this hybrid as the general replacement.** Keep original production and the previously selected hourly research candidate. Do not introduce a wet/dry switch or search more rain penalties from these targets. The direct addition shows that rain is informative within the original architecture, but retaining episodes does not automatically protect dry-day accuracy.

### Benchmark and numerical notes

The first historical replay was exact. A repeated batch with uniform CSV type inference differs by at most 0.045 birds on historical targets and fails the stricter `1e-6` replay assertion; the failed status is explicitly saved, without relaxing that threshold. Displayed error scores and the rejection conclusion are unchanged. The old recent runner (`run_historical_counts.py`) stored profiles by species alone, so its first fold's profile was reused in later folds. That permits hidden-hour counts in later folds to influence the profile. The present runner rebuilds every profile using only that fold's retained hours; both original and hybrid use it. Consequently the recent original dry/wet scores are 47.88/44.85 rather than the previously reported 47.85/44.68. The primary hybrid comparison uses these fresh controls; the saved hourly candidate already estimates its time design from retained inputs. Historical assessment remains unaffected by this fold-cache issue in the selected one-fold task. Saved earlier results remain preserved, with this qualification; the old cached-profile runner is not used by the hybrid.

All forty fitted main rain slopes are negative. However, the hinge permits the response to turn upward above 1 mm/hour: its combined slope is positive in 17/40 contexts, including three historical species. These are fitted response shapes, not evidence that severe rain increases migration; they add a substantial extrapolation limitation. Saved slopes and their original-unit combined derivatives are in `rain_coefficients.csv`. No monotonicity constraint was imposed in this test.

The original solver's default stopping rule is based on penalized likelihood change, not the weather-model gradient threshold. Raw posterior scores are retained for both arms and reach 0.18 for original and 0.51 for hybrid. They must not be presented as passing the hourly model's 0.001 score threshold. Independent final-step diagnostics reach a 0.027 change in fitted log mean for hybrid and 0.019 for original, so strict numerical acceptance is not established; no optimizer search or numerical fallback is introduced. Median final fit time is 0.21 seconds for hybrid versus 0.18 for original (optimization only). Synthetic tests verify unchanged original columns/penalties, fixed rain precision and recovery of a known rain response. No new predictive-uncertainty claim follows.

Saved evidence: `logs/original-rain/{group_scores,era_scores,year_scores,species_scores,total_bias,paired_scores,season_scores,season_species_scores,baseline_replay,diagnostics}.csv`.
