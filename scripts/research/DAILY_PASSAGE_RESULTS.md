# Training-selected daily passage: full core screen

## Protocol fixed before fitting

The user authorized the complete ten-core comparison after the [eight-context numerical pilot](ABUNDANCE_REDESIGN.md) passed. Run the same forty contexts: ten historical seven-day masks and thirty recent whole-day masks, all with eligible historical training. Keep the fixed seven-day correlation scale, existing small shared season/hour/weather/year design, intact interval means, unweighted power-1.5 objective, centering constraints and numerical method. The shared smoothing is the paired baseline's retained-training-selected value. No richer basis, additional weather terms, retained-count multiplier, altered variance power or joint smoothing search is introduced.

Choose stationary daily log-deviation SD from 0, 0.25, 0.5 and 1, using the unchanged three calendar-week folds and daily MAE on retained training observations. SD zero is exactly the existing weather model. Refit shared coefficients and all daily deviations in each inner fold; hidden inner counts have no likelihood contribution. The full calendar grid remains, so an unobserved date is never collapsed out. Outer-retained basis construction is preserved from earlier controls and is not rebuilt inside each inner fold. The first minimum in increasing SD order resolves ties. This is a common training-selection rule across species, not outer-score species switching.

Expose SD as an argument to the pilot's existing penalty/fitter, preserving its default 0.5 bit-for-bit. Independent checks verify default replay, analytic quadratic scaling and derivatives at both additional positive SDs before real fitting. The numerical method stays at 100 updates, twenty Armijo halvings, 1e-5 optimization target and independent gradient/directional acceptance below 0.001. Preserve iteration-cap and precision-loss flags even if numerical acceptance passes. Save all 480 inner numerical checks, amplitude scores and histories; save eighty final checks/fits if all contexts complete. Any failed inner fit invalidates its entire context rather than silently dropping that SD from selection. No retries, raised budgets or fallback predictions.

Run independent contexts in processes with a 60-second whole-context limit, as in the pilot, using one BLAS thread. Complete both species-partitioned shards before reviewing accuracy. A timeout or numerical failure remains explicit. Incomplete matched-species diagnostics may be reported, but cannot pass completeness or select a replacement. Never compare a partial nine-species absolute score with a ten-species score as if matched.

Frozen acceptance gates: all forty contexts complete; historical dry MAE, early-era dry MAE and eligible reconstructed-total absolute relative error each no worse than original; historical wet and recent dry/wet MAE at most 2% worse than current weather baseline; median final fitting at most five seconds and five times the paired baseline. Report joint species-block bootstrap intervals, species/year/era errors, signed total bias, selected amplitude, effective degrees of freedom and end-to-end selection time. Effective DF uses the pilot's 32 fixed-seed trace probes for positive SD, with Monte Carlo SE; SD-zero EDF is computed directly from the small working-information matrix.

Reused development masks are exploratory. Passing only permits broader gap-length/attendance tests and then confirmation kept outside tuning. Historical truth covers eligible recorded intervals, not unknown full seasons or actual storm closures. The candidate has conditional point predictions, with no inherited empirical or coherent seasonal uncertainty. Production remains unchanged.

## Completed batch and explicit failures

All forty contexts are attempted without timeouts or optimizer retries. All 480 inner fits are saved: 476 pass numerical acceptance and four exceed the fixed 0.001 gradient limit at the 100-update cap. The four invalid grids prevent their contexts from reaching final fitting. Of the other 36 contexts, one selected final daily fit also fails the gradient limit. Thus 72 final fits are saved, but only 35 contexts supply paired accepted predictions. No failed SD is removed from its grid and no failed context receives a fallback prediction.

| Failed context                                 | Stage |   SD | Inner fold | Maximum gradient |
| ---------------------------------------------- | ----- | ---: | ---------: | ---------------: |
| Recent Grey Heron, outer fold 2                | Inner |    1 |          0 |         0.001302 |
| Recent White Stork, outer fold 2               | Inner | 0.25 |          2 |         0.018277 |
| Historical Grey Heron, outer fold 2            | Inner |    1 |          0 |         0.028725 |
| Historical Western Marsh Harrier, outer fold 2 | Inner |  0.5 |          1 |         0.001590 |
| Historical Eurasian Sparrowhawk, outer fold 2  | Final |  0.5 |          — |         0.006525 |

Independent directional checks remain small even on failed fits, so the exposed failure is incomplete convergence within the fixed budget, rather than an observed derivative disagreement. The four failed inner histories continue taking full, objective-decreasing scoring steps near the cap, with slowly declining gradients. This does not establish how far their predictions are from their optima. Do not raise the cap or relax numerical gates based on these outcomes.

Raw status is distinct from independent acceptance. Among 360 positive-SD inner fits, fifteen reach the iteration cap and three reach the line-search limit; only four exceed numerical acceptance. All 120 SD-zero inner fits pass, including 44 raw BFGS precision-loss statuses. The completed paired panel has 70 accepted final fits; two daily fits retain cap statuses within the acceptance threshold, and thirteen baselines retain precision-loss statuses. Its maximum final gradient is 0.000306 and directional error 3.783e-8. All saved baseline optima and accepted hidden predictions reproduce within the specified equivalence bounds. Synthetic default/scaling/derivative checks and all 104 repository tests pass.

## Partial matched predictive results

These scores cover seven historical species and 28 recent contexts spanning all ten species. Historical Sparrowhawk, Grey Heron and Marsh Harrier are absent; recent Heron and Stork each have two masks instead of three. Every displayed model uses the same completed species/date/mask targets. These are incomplete, selected-by-numerical-success diagnostics: do not compare their absolute scores with the earlier full ten-species tables, claim completion or infer the missing contexts' results.

| Measure on matching completed targets                  | Weather baseline | Daily passage | Original benchmark |
| ------------------------------------------------------ | ---------------: | ------------: | -----------------: |
| Historical dry MAE                                     |            44.73 |         41.60 |              42.33 |
| Early historical dry MAE                               |            32.21 |         26.86 |              28.44 |
| Historical wet MAE                                     |            26.58 |         23.16 |              31.56 |
| Recent dry MAE                                         |            47.68 |         45.23 |              47.77 |
| Recent wet MAE                                         |            29.86 |         27.26 |              44.52 |
| Historical reconstructed-total absolute relative error |           15.95% |        15.10% |             12.94% |

Historical dry daily MAE improves 7.0% against weather, with improvement in all seven completed species and median species ratio 0.957. Only three of seven beat original on historical dry MAE. Recent dry improves 5.2% against weather, with all ten species improving and median ratio 0.900; nine beat original, with Cormorant the exception. These directions are not gains driven by pigeons or one core species. Recent dry MAE improves against weather in each recent year, but remains worse than original in 2024. Middle- and late-era historical dry MAE remain slightly worse than original, despite the early-era gain. Species/year/era tables retain these differences.

Paired blocked bootstrap daily-MAE differences against weather are historical dry −3.12 birds [−6.03, +0.19], historical wet −3.42 [−5.99, −1.24], recent dry −2.46 [−5.29, −0.02] and recent wet −2.60 [−5.28, +0.02]. Against original, historical dry difference is −0.73 [−2.95, +1.92], recent dry −2.55 [−4.94, −0.32] and recent wet −17.26 [−23.52, −11.81]. Historical years and recent calendar weeks are resampled jointly across matched species; incomplete panels and reused masks limit inference.

Reconstructed-total absolute relative error improves against weather for five of seven historical species, but remains worse than original for every one of the seven. The paired historical year-bootstrap difference is −0.86 percentage points [−2.53, +0.77] against weather and +2.16 [+1.03, +3.19] against original. This comparison covers 29 historical years and the seven matched species, not unknown complete-season totals.

Mean signed reconstructed-season relative bias is −7.19% for daily passage, compared with −1.58% weather and −3.50% original, giving each species/year equal weight under the existing season assessment. Separately, species-averaged relative bias on the missing historical counts is −18.68% versus −5.05% weather and −9.83% original. These denominators and year weights differ; neither is a calibrated estimate of unknown true full-season bias. Daily MAE improvement therefore does not resolve the reconstruction objective and comes with substantial underprediction on observed held-out totals.

## Selection, complexity and runtime

Every completed context selects positive SD: historical 0.25 for four and 0.5 for three; recent 0.25 for twelve, 0.5 for twelve and 1 for four. SD zero remained available and all its inner fits passed. This is evidence that the retained-training daily-MAE criterion favors temporal adaptation; it does not establish that this selection rule is suitable for season totals.

Median final fitting is 0.514 seconds versus paired baseline 0.160, with median paired ratio 2.86; maximum accepted final fit is 1.668 seconds. Selection costs median 5.84 seconds, maximum 10.10; selection plus final fitting costs median 6.29, maximum 10.88. These describe completed contexts and exclude some input/diagnostic work. Two fitting processes use one BLAS thread each. No context times out, but fast timing must not conceal the five numerical failures.

Selected total working effective DF ranges approximately 372–1,057. Medians are 544 at SD 0.25, 567 at 0.5 and 1,020 at 1. The daily-state representation is computationally feasible in these cases but statistically much more flexible than the small baseline. All candidate coefficients/states, training scores, numerical statuses, histories and trace Monte Carlo errors remain saved.

## Decision and next bounded work

Do not select this version as a replacement. Completeness fails, and reconstructed-total accuracy fails even on the completed matched panel. Preserve the positive daily-error evidence as exploratory; the numerical failures do not prove the statistical architecture is intrinsically invalid, and the partial results do not establish full-core superiority. Keep current weather and original production references unchanged.

Stop before broader gap/year validation, further amplitude searches, species-specific switches, post-hoc bias multipliers or optimizer-budget increases. The next proposed work is a saved-fit diagnosis of two exposed limitations: slow convergence in the five failed contexts, and why conditional daily-state point predictions selected by daily MAE underpredict missing totals. Conditional-mode versus integrated-mean prediction and the selection target are hypotheses to examine, not established causes or authorization to add latent integration. Specify one bounded correction only if that diagnosis supports it, and distinguish computational repair from a changed prediction target. Do not launch another broad fitting batch automatically.

## Reproduce

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/check_daily_passage.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/batch_daily_passage.py --shard 0 2 > logs/daily-passage/run-0.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/batch_daily_passage.py --shard 1 2 > logs/daily-passage/run-1.log 2>&1
uv run python scripts/research/review_daily_passage.py > logs/daily-passage/review.log 2>&1
```

Create the output directory before redirecting logs. Shards can run concurrently; review only after both finish. The incomplete option adds an explicit completeness gate even when all fits finish. All generated data remain under ignored `logs/`.

The proposed saved-fit audit is now complete: [DAILY_PASSAGE_DIAGNOSIS.md](DAILY_PASSAGE_DIAGNOSIS.md). Numerical failures and accepted-fit underprediction are distinct. The ordered shared/daily decomposition, peak-day errors and retained weighted score identify a count-balance problem that lower daily MAE does not resolve. No additional fits or corrected fills are produced; the decision above remains unchanged.
