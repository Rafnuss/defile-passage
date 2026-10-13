# Count-balanced daily passage control

## Frozen protocol before fitting

The user authorized the next comparison after the saved-fit diagnosis. Change the working variance power from 1.5 to 1, retaining the 51 shared predictors, interval aggregation, full calendar daily states, annual centering, seven-day AR(1) correlation and SD grid 0/0.25/0.5/1. Fit a matching no-state reference and training-selected daily candidate. Keep retained-training week-fold daily MAE selection, existing shared smoothing and numerical ridge/AR penalties unchanged. This isolates the working-criterion change under fixed penalty conventions; its different curvature changes effective regularization, so it does not isolate variance weighting at equal effective flexibility. Basis/preprocessing construction remains outer-retained rather than being rebuilt inside inner folds, as in the preceding screen. Do not simultaneously change selection to a seasonal score or search additional penalties.

The power-1 loss is `sum(mean − count + count * log(count/mean))` with the zero-count term defined as zero. Its unpenalized intercept equation is `sum(mean − count) = 0`. This balances retained expected counts at a numerical optimum but cannot guarantee hidden totals, unbiased migration estimates or a Poisson sampling distribution. The earlier mean-only Poisson dry-day limitations remain relevant. No Poisson intervals, occurrence probabilities or integrated latent-state means are inferred.

Keep the existing 100-update daily scoring cap, twenty Armijo halvings, 1e-5 gradient target, independent acceptance below 0.001 and exact yearly centering below 1e-9. For this new criterion only, use the same sparse scoring direction with a single analytic directional-curvature scale before its existing line search: start at `min(1, gradient·direction / directional_curvature)` for positive curvature, otherwise 1. This addresses curvature mismatch without a second optimizer or larger budget. Existing power-1.5 default fits must replay unchanged. Record scale, raw status, gradient and derivative checks. Save every inner coefficient endpoint and out-of-fold daily prediction, including failed fits, before checking context acceptance. No failed amplitude may be dropped.

First run independent synthetic checks: both criterion gradients, directional curvature against gradient differences, no-state equivalence, constrained sparse/dense agreement, count balance, empty runs, zero counts and cross-date intact counts. Then a numerical-only pilot runs both final no-state and fixed-SD-0.5 daily fits on eight fixed contexts: historical Buzzard, Sparrowhawk, Honey Buzzard, Stork and Heron; recent Buzzard fold 0, Stork fold 2 and Heron fold 2. These cover the available failed endpoint, difficult sparse/high-count cases and both historical/recent support. Check numerical acceptance, count balance, baseline replay and median final speed at most five seconds and five times the matching no-state reference. Do not inspect hidden accuracy. No retries or budget adjustments. This pilot is not a species efficacy selection.

Only if the fixed numerical pilot passes, attempt all forty frozen ten-core contexts with a 60-second whole-context process limit, one BLAS thread and two species-partitioned shards. Complete the batch before accuracy review. Preserve all failures. Report original benchmark, existing power-1.5 no-state/daily fits and new power-1 no-state/daily fits on explicitly matching targets; incomplete old daily comparisons remain seven historical species and 28 recent contexts. Do not compare unmatched absolute scores.

Acceptance requires all forty new contexts complete, historical dry/early-era dry and reconstructed-total absolute relative error no worse than original, historical wet/recent dry/recent wet MAE at most 2% worse than the retained power-1.5 weather reference, and median final time at most five seconds and five times the new paired no-state fit. Report missing-count and reconstructed-season signed bias, species/year/era differences, working effective DF, selected SD and full selection time. Reused masks remain development diagnostics. Passing would justify broader validation, not production adoption or uncertainty transfer. Failure ends this control without further power/penalty searches or correction multipliers.

## Completed numerical gate and full batch

The synthetic checks pass for both powers: independent gradients and directional curvature, constrained sparse/dense solves, no-state objective equivalence, independent dense optimum, zero/cross-date counts, unobserved calendar runs and raw count balance. The original default synthetic checks also pass, and the default power-1.5 fitter agrees exactly with its explicit unchanged settings on the synthetic case. Existing default criterion, step policy and output location remain available; new flags select power 1 and a separate output directory.

The fixed numerical pilot passes all sixteen fits across eight contexts. Median daily final fit is 0.229 seconds and median paired ratio 1.15. Maximum gradient is 0.000130, derivative discrepancy 7.26e-8 and retained count imbalance 0.000122 birds. A raw line-search status remains on recent Heron within the independently specified acceptance threshold; raw BFGS precision-loss statuses are also preserved. No hidden accuracy was inspected at this gate.

All forty efficacy contexts are attempted without timeouts or retries. All 480 inner fits pass the original numerical gates: maximum gradient 0.000758 and derivative discrepancy 9.57e-8. All inner coefficient endpoints and out-of-fold daily predictions are saved, and their amplitude scores and selected minima are independently verified. Of 360 positive-SD inner fits, 355 reach the gradient target and five retain line-search-limit statuses within acceptance. Of 120 no-state inner fits, 81 retain BFGS precision-loss statuses within acceptance.

All eighty final fits are saved. Every selected daily final fit passes; one matching no-state fit, recent Great Cormorant outer fold 2, fails at maximum gradient 0.001380 with a BFGS precision-loss status. Its derivative discrepancy is 5.61e-8. This invalidates that paired context; no retry, relaxed threshold or fallback prediction is used. The 39 accepted paired contexts contain all ten historical species and 29 recent masks across all ten species. Maximum gradient among the 79 independently accepted final fits is 0.000330 and derivative discrepancy 8.13e-8. The failed context remains available for numerical inspection, but cannot establish accepted paired accuracy.

Retained counts balance to within 0.001 birds for all saved final endpoints, including the failed one. This numerical conservation is the intended change in the fitting equation; it is not hidden-count conservation. Median completed daily final fit is 0.195 seconds, maximum 0.638, and median paired runtime ratio is 1.13. Median selection plus final optimization is 2.96 seconds, maximum 4.71. The 100-update and 60-second budgets are unchanged.

## Matched predictive results

The first table uses the same completed targets for every method: all ten historical species and 29 recent masks. The old reference is the retained power-1.5 weather mean; the new no-state reference uses the power-1 criterion with exactly the same shared predictors and fixed penalty conventions.

| Measure                                                | Retained weather mean | New count-balanced mean | New count-balanced daily | Original benchmark |
| ------------------------------------------------------ | --------------------: | ----------------------: | -----------------------: | -----------------: |
| Historical dry MAE                                     |                 33.40 |                   33.51 |                    31.80 |              31.52 |
| Early historical dry MAE                               |                 24.45 |                   24.73 |                    20.26 |              21.52 |
| Historical wet MAE                                     |                 20.77 |                   20.87 |                    18.36 |              24.31 |
| Recent dry MAE                                         |                 48.17 |                   48.80 |                    47.36 |              47.96 |
| Recent wet MAE                                         |                 29.68 |                   30.08 |                    28.43 |              44.07 |
| Historical reconstructed-total absolute relative error |                15.83% |                  15.32% |                   15.85% |             13.27% |
| Historical signed reconstructed-total bias             |                −2.00% |                  −2.36% |                   −8.35% |             −4.22% |

The daily candidate improves historical dry MAE 4.8% and historical wet MAE 11.6% against retained weather, with an early-era dry gain. Eight of ten species improve historical dry error against retained weather and six against original; median species ratios are 0.944 and 0.979 respectively. Middle-era historical dry MAE is 36.19 versus original 34.68, and late-era dry MAE 56.76 versus original 54.32. The early improvement does not extend uniformly through history.

On recent dry targets, eight of ten species improve against retained weather and seven against original. Median species ratios are 0.924 and 0.931. Recent dry MAE is better than retained weather in 2022–2024 but worse in 2025; it remains worse than original in 2024 and 2025. All recent comparisons use the same 29 masks; they must not be compared directly with earlier thirty-mask absolute scores.

Joint species-block bootstrap daily-MAE differences against retained weather are historical dry −1.60 birds [−4.41, +1.63], historical wet −2.41 [−5.14, −0.43], recent dry −0.81 [−4.35, +2.58] and recent wet −1.26 [−4.25, +1.55]. Historical dry difference against original is +0.28 [−1.79, +2.96]. Recent wet difference against original is −15.64 [−22.13, −9.78]. Reused development masks and the missing paired recent context limit these exploratory intervals.

Historical reconstructed-total error remains worse than original for every one of the ten core species. The paired historical-year bootstrap difference is +2.58 percentage points [1.60, 3.63]. Daily states also worsen total error relative to the matching count-balanced no-state mean (15.85% versus 15.32%), improving only three species and tying one. Changing the fitting equation therefore does not repair the reconstruction objective, despite retained count balance and better daily MAE.

Missing-count relative bias, a different denominator and weighting from reconstructed-total bias, is −22.98% historically and −17.27% recently for the new daily model. Its count-balanced no-state reference is −5.75% and −0.73%. Historical dry/wet missing bias is −19.92%/−28.47%; recent dry/wet is −21.26%/+11.79%. Count conservation on retained intervals does not carry over to hidden intervals under the jointly fitted conditional daily states.

## Direct comparison with the previous daily candidate

This separate panel includes only contexts accepted by both daily screens: seven historical species and 27 recent masks across ten species, 34 contexts in total. The missing recent Cormorant pair changes this panel from the earlier 35-context screen. Every row below uses exactly matching targets; do not compare its absolute scores with the full historical table above.

| Measure on shared accepted targets                     | Previous power-1.5 daily | New power-1 daily |
| ------------------------------------------------------ | -----------------------: | ----------------: |
| Historical dry MAE                                     |                    41.60 |             42.84 |
| Historical wet MAE                                     |                    23.16 |             23.48 |
| Recent dry MAE                                         |                    45.67 |             47.16 |
| Recent wet MAE                                         |                    26.82 |             28.33 |
| Historical reconstructed-total absolute relative error |                   15.10% |            15.77% |
| Historical missing-count bias                          |                  −18.68% |           −18.01% |
| Recent missing-count bias                              |                  −23.88% |           −18.92% |

The new criterion modestly improves historical signed missing bias and more clearly improves recent signed missing bias, while worsening daily errors and historical absolute total error. Recent overall paired MAE difference is +1.49 birds [+0.43, +2.68] and wet difference +1.50 [+0.44, +2.66] against the previous daily candidate. Historical dry difference is +1.24 [−0.07, +2.69]. This control does not identify a superior replacement for the previous daily model. Its fixed penalty conventions and changed criterion curvature also prevent treating it as a comparison at equal statistical flexibility.

## Selection and decision

Historical selected SD counts are 0: one, 0.25: four, 0.5: one and 1: four. Accepted recent counts are 0: one, 0.25: sixteen, 0.5: one and 1: eleven. The daily candidate's median working effective DF is 918, with positive-SD ranges about 364–1,230 at SD 0.25, 542–741 at SD 0.5 and 721–1,104 at SD 1. These working DF estimates have Monte Carlo error and differ with training support; the state representation remains flexible despite fast computation. The two SD-zero selections have about 47–50 DF.

Completeness, overall historical dry noninferiority to original and reconstructed-total accuracy gates fail. Early-era dry, historical wet/recent dry/recent wet protection against retained weather and both speed gates pass. Retain the power-1.5 weather research reference and the original production model. Do not retry the Cormorant fit merely to complete a scientifically failing control, search additional powers or penalties, add a count multiplier or promote daily conditional-mode fills for reconstructed totals.

The evidence supports a narrower conclusion than the earlier hypothesis: the power-1.5 weighted score allowed retained count imbalance, but removing that imbalance does not resolve held-out bias. The daily-state representation and its training selection/prediction target remain implicated; this experiment does not isolate which of them is responsible. Recent wet gains and early historical dry gains remain useful positive evidence.

The next proposed step is a saved out-of-fold prediction audit of whether daily-MAE amplitude selection conflicts with held-out yearly/block-total accuracy and signed bias. The new inner predictions permit this without fitting another model. Use only those retained-training validation counts, keep the zero-state option, and do not choose a new rule from outer hidden outcomes. First establish whether a total-aware selection target could plausibly address the problem; another full model batch is not yet justified. Historical partial-day validation, joint seasonal uncertainty and independent confirmation from the original five goals remain open.

## Reproduction and checks

Run `uv run python scripts/research/check_count_balanced_passage.py` and the archived `check_daily_passage.py`, then `pilot_count_balanced_passage.py`. After its fixed numerical gate passes, run `batch_daily_passage.py --out logs/count-balanced-passage --variance-power 1 --shard 0 2` and the matching `--shard 1 2` as separate processes. Run `review_daily_passage.py --out logs/count-balanced-passage`, then `review_count_balanced_passage.py`. Use one BLAS thread for numerical work. Outputs are generated under `logs/count-balanced-passage/` and the numerical pilot under `logs/count-balanced-pilot/`; no generated data are committed. All 104 repository tests pass. Explicit new-file and repository-wide formatting checks plus `git diff --check` are required before completing the change. Production is unchanged.

The proposed training-fold audit is now complete and the daily-passage branch is closed: [PASSAGE_SELECTION_WRAPUP.md](PASSAGE_SELECTION_WRAPUP.md). Yearly-total minima select no daily state in all forty contexts. No further fitting follows this control.
