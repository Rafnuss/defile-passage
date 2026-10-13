# Current simple-rate assessment

> Completed experiment record. Its results are preserved; earlier next-step proposals below are superseded by the [consolidated model decision](MODEL_SPECIFICATION.md). Further experimentation is paused.

The development candidate is a 22-coefficient count-rate GAM with a fixed Tweedie working variance power of 1.5. It estimates one hourly rate from annual abundance, a seasonal smooth, three clock-time harmonics, two log-rain slopes, wind u/v and civil-night status. Count means for arbitrary observed intervals sum the hourly rates times actual covered durations. No episode smooth, latent daily integration or count convolution is used. This is a mean model; calibrated predictive intervals and retained-hour conditioning remain unimplemented.

## Matched original benchmark

The test hides every observed hour on a date in the original three seven-day-block folds. It uses the exact original training/test intervals for all 16 species in 2022–2025, asserting matching daily counts and effort. The benchmark is the original production episode architecture refitted on these same recent observations, not a cached fit using its full historical data. There are 48 outer fits and 8,071 held-out species-days. Model smoothing is chosen within each outer training set using retained-data calendar-week folds.

| Held-out full-day task            | Original benchmark MAE | Candidate MAE | Change | Paired week-bootstrap difference, 95% interval |
| --------------------------------- | ---------------------: | ------------: | -----: | ---------------------------------------------- |
| All observed days                 |                 129.68 |        123.25 |  −5.0% | −6.43 [−32.14, +13.66]                         |
| Wet days (mean rain ≥0.1 mm/hour) |                 135.02 |         85.72 | −36.5% | −49.30 [−116.19, −8.75]                        |
| Dry days                          |                 127.57 |        137.95 |  +8.1% | +10.38 [−10.87, +30.19]                        |

MAE is averaged equally across species after computing each species' daily error. Calendar weeks are resampled jointly across species. Fourteen of 16 species improve overall and on wet days; eight improve on dry days. The masks and species have been reused during development, and these bootstrap intervals omit exploratory model-selection uncertainty. The overall improvement is not statistically resolved; the dry-day result does not establish noninferiority.

## Calibration and remaining failures

On 1,259 wet species-days with zero observed birds, the candidate predicts 12,611 birds in total versus benchmark 54,681. On 2,871 dry zero-count species-days, it predicts 26,231 versus benchmark 19,204: dry false passage remains a weakness. Observed hourly counts at ≥3 mm/hour total 1,390 birds; the candidate predicts 1,878, about 35% too high. This criterion improves ordinary wet-day error while worsening heavy-rain total calibration compared with the Poisson-working candidate (1,269). Wet-day Barn Swallow MAE is 1.20 times the benchmark and Redwing 1.13 times; Pigeon dry-day MAE is 1.17 times.

All 48 fits pass numerical checks: maximum gradient 0.00000346 and directional derivative discrepancy 0.0000000318. Median fit time including nine inner fits, final fit and file I/O is 0.176 seconds; maximum 0.240 seconds. The full priority and passerine subprocess batches take 39 and 13 seconds, respectively, when run concurrently. Independent numerical checks cover arbitrary exposure, intact mixed totals, off-optimum derivatives, both working criteria and large counts. Repository tests pass (104 tests).

## Scientific priorities and episode comparison

The user specified ten core large-bird species as the primary target: Black Kite, Common Buzzard, Common Kestrel, Eurasian Sparrowhawk, European Honey Buzzard, Red Kite, Western Marsh Harrier, White Stork, Great Cormorant and Grey Heron. Common Wood Pigeon/Stock Dove and the four passerines remain fully reported in separate secondary groups. Grouping is based on scientific priorities, not a numerical species-exclusion rule. Report median within-species error ratios alongside equal-species absolute MAE: equal species weighting of absolute errors still gives abundant taxa substantial influence.

| Core large-bird full-day task | Original benchmark MAE | Weather-only MAE | Weather + episode MAE |
| ----------------------------- | ---------------------: | ---------------: | --------------------: |
| All days                      |                  46.71 |            41.46 |                 43.14 |
| Dry days                      |                  47.38 |            47.05 |                 48.72 |
| Wet days                      |                  45.05 |            27.23 |                 28.94 |

For core species, the unchanged weather-only model improves MAE 11.2% overall and 39.6% on wet days, with approximately unchanged dry-day MAE (0.7% improvement). Eight of ten improve overall; all ten improve on wet days. The median species MAE ratio is 0.907 overall, 1.006 dry and 0.717 wet. Exploratory paired week-bootstrap intervals for the absolute difference versus original are [−8.58, −2.12] overall, [−3.64, +2.87] dry and [−23.10, −12.84] wet. These intervals describe the reused development masks; they are not independent confirmation.

The seasonal smooth and annual offset already model expected abundance. The episode experiment tests remaining within-year temporal departures beyond those terms and weather, not the absence of an abundance model. It adds seven centered spline coefficients per year with roughness and amplitude shrinkage, producing 50 coefficients. Baseline smoothing is selected first using the original 22-coefficient model; episode strength is then selected on the same training-only week folds from 10, 100 and 1000. This deliberately bounded experiment does not jointly optimize smoothing or establish the best possible episode structure.

Adding episodes increases core-species MAE by 4.1% overall, 3.6% dry and 6.3% wet relative to the weather-only candidate. The core median species ratios versus original also worsen slightly: 0.930 overall, 1.012 dry and 0.733 wet. The largest added dry errors are Cormorant, Red Kite and Buzzard. Episodes improve White Stork, Black Kite and Grey Heron dry MAE slightly. Secondary-group overall MAE improves from 572.10 to 510.21 for pigeons and 103.30 to 94.47 for passerines. Thus the pooled 16-species overall MAE improves from 123.25 to 114.36 while the core group worsens: the pooled summary would favor the wrong choice for the stated primary target. Wood Pigeon dry MAE improves from 1379.41 to 1204.35, still slightly above the original 1174.32.

All 48 episode fits pass numerical checks, with median 0.428 seconds and maximum 0.645 seconds including 18 inner fits, final fitting and I/O when dense linear algebra is limited to one thread. Maximum gradient is 0.00000305 and derivative discrepancy 0.0000000269. The first default-thread batch suffered CPU oversubscription and was stopped; this was an execution issue rather than evidence about model accuracy. Heavy-rain predicted totals rise from 1878 to 1968 against 1390 observed. This variant provides no general rain-calibration improvement.

## Decision and next gate

Retain the 22-coefficient weather-only candidate as the primary development model for core large birds. Do not add episodes universally on this evidence or introduce species-specific model switches chosen from reused test errors. Preserve the episode alternative as a secondary-group diagnostic; this one low-rank, penalized trial does not disprove residual temporal correlation or rule out other episode specifications. Annual seasonal contrasts were also already assessed without resolving the tradeoff.

Freeze the primary specification and scientific assessment groups before validation on additional contiguous day/storm masks. Keep all species visible, report core and secondary groups separately, and include median species ratios, bias, positive-day errors and zero-day predictions. Develop predictive uncertainty and sparse-weather support after this gate. Artificially hidden counted days only validate observed intervals; unobserved closures have no known dawn-to-dusk truth, and no hard-zero rain rule is established. The daylight benchmark does not validate nighttime fills. Year terms require retained observations in that year; wholly unobserved years remain a different task. Production is unchanged.

## Reproducible artifacts

See [SIMPLE_RATE_PLAN.md](SIMPLE_RATE_PLAN.md) for preparation and earlier rejected candidates. Run the existing gap-design preparation, then `run_simple_panel.py --variants year_weather --variance-power 1.5` into `logs/simple-gaps-tweedie-{priority,passerines}`. Review with `review_simple_gaps.py --prefix simple-gaps-tweedie --out logs/simple-gaps-tweedie-review`. The output contains paired daily truths/predictions, species errors and totals, shared-week bootstrap, zero-day scores, heavy-rain totals, saved fit diagnostics and the benchmark-comparison figure. Coefficients, feature names, scales and bases are saved alongside the model inputs/outputs. `check_simple_rate.py` runs the independent numerical checks.

## Additional frozen-mask sensitivity assessment

The accepted 22-coefficient model has now been refitted and compared against the original architecture on new count-independent masks for one-, three- and seven-day gaps, covering 4,191 species-days. Every eligible date already appeared in earlier development holdouts, so these are new masks rather than independent observations. See [the frozen protocol and completed results](GAP_VALIDATION.md).

Core-species MAE is 40.16 versus 46.76 overall (−14.1%), 45.19 versus 46.93 dry (−3.7%) and 26.91 versus 46.34 wet (−41.9%). All 48 numerical checks pass at median 0.175 seconds per context. Core overall MAE improves at each gap length and within each year. Nine of ten core species improve overall and wet, but only four improve dry; median dry species ratio is 1.013 and the paired dry bootstrap crosses zero. Wet core totals remain 24.5% high, with Honey Buzzard a wet-day error exception. Dry zero-day predictions remain slightly worse. Secondary passerines and dry pigeons still have worse MAE than original. Retain the frozen model for core development, without a universal deployment claim. Predictive uncertainty, short-gap conditioning and historical scope remain open.

## Empirical uncertainty and retained-hour additions

The mean model remains fixed. Training-only out-of-fold residuals now give empirical 80%/95% count intervals; one training-selected pseudo-count controls how retained-hour counts adjust the missing mean. On 2,508 core short-gap cases, MAE falls 15.8% overall, 15.4% dry and 19.4% wet; every core species improves overall. Core full-day 95% coverage is 95.2%, with lower interval score than the matched original refit (294.4 versus 356.5). Adjusted short-gap intervals cover 96.7% at nominal 95% and are conservative, particularly for wet gaps. Wet passerine full-day undercoverage remains. Full-day point predictions are unchanged and core short-gap total bias is slightly worse despite the MAE gain. These empirical intervals are not a joint arbitrary-scale count distribution or independent confirmation. See [SIMPLE_RATE_UNCERTAINTY.md](SIMPLE_RATE_UNCERTAINTY.md) for the completed protocol, species results and executable workflow.

## Practical short-gap comparison with the original model

The [completed operational short-gap assessment](SHORT_GAPS.md) now includes retained hours in the actual mean fit and recalibrates the retained update with the same observation setup. All 48 fits pass; median mean-fitting time is 0.187 seconds. On exactly matching gaps, including retained hours in fitting improves core MAE 2.3%, and the further update improves another 14.0% (11.33 to 9.75). Core error improves for every species overall relative to the unadjusted weather fit. The original architecture is refitted on the same partial-day inputs and gives MAE 9.97 overall; the adjusted weather model is comparable, with a paired difference interval crossing zero, only four species improving versus original, and slightly higher wet MAE (5.12 versus 5.07). Core missing total bias worsens after the update (+5.5% versus +3.2%; original +1.0%), so lower per-gap MAE is not enough to establish better totals. Keep the small update as a research option, without new model terms, post-hoc weather switches or production replacement. See the full assessment for zero-count, early/middle/late, retained-coverage and rain-contrast diagnostics.

## Adjustment-function diagnosis

[ADJUSTMENT_FUNCTIONS.md](ADJUSTMENT_FUNCTIONS.md) records the requested species/year/event decomposition and a bounded comparison of simple adjustment rules, with all GAMs unchanged. Cormorant contributes 1,388 of 1,604 net excess birds, mostly baseline morning error; the adjustment's net additional 659 birds comes mainly from Buzzard/Red Kite. A fixed pseudo-count already gives varying evidence weight `R/(R+s)`; relative coverage is a separate hypothesis. A bounded response lowers core MAE from 9.75 to 9.38 and pooled bias from +5.5% to −1.4%, but wet totals become 11.4% low and Honey Buzzard/Stork underprediction worsens. No universal replacement is selected. Selecting the existing rule by MSE does not solve its bias. Next inspect within-species/year time and abundance calibration rather than layering new correction functions.
