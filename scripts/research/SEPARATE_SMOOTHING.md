# Separate seasonal and hourly smoothing

## Protocol fixed before fitting

Test one change to the retained small weather mean: independent seasonal and clock smoothing strengths. Keep the seven-column seasonal basis, six clock harmonics, weather/night effects, annual offsets, intact interval counts, exact hourly expected-count aggregation, unweighted power-1.5 working criterion and all forty assessment contexts unchanged. There are still 51 rate coefficients. No richer basis, episodes, retained-count update, duration weights or latent state is added.

Split the existing penalty into its seasonal and clock blocks and require their exact sum to reproduce the original matrix. Weather/night and annual ridge penalties remain one. Select each smoothing strength from 0.1, 1 and 10: nine pairs, with the three common-strength baseline pairs included. Use the existing three calendar-week folds and daily MAE criterion on retained training observations only. A deterministic first minimum resolves ties. This tests the existing small model's penalty coupling, not a simultaneous change in model capacity or training score. The richer seasonal basis remains rejected and is not retried here.

Use the bounded BFGS research solver with unchanged numerical gates, without retries or fallback predictions. Save and check all 1,080 inner fits plus eighty final fits. Replay the forty saved baseline optima with objective relative error below 1e-7, component-rate relative error below 1e-5 and hidden prediction agreement within absolute/relative 1e-5, consistent with the completed solver-equivalence check. Save raw solver status, iterations and independent gradient/directional checks; acceptance requires both errors below 0.001. Numerical acceptance is distinct from the optimizer's raw success flag.

Assess ten core species on historical seven-day gaps and three recent whole-day masks with eligible historical training. Review accuracy only after the batch finishes. Frozen gates: historical dry, early-era dry and reconstructed-season absolute relative errors each no worse than the original benchmark; historical wet and recent dry/wet MAE at most 2% worse than the paired weather baseline; median final fit at most five seconds and five times baseline. Report training-selection time separately because the nine-pair grid triples inner fit count. Report species, year, era, jointly blocked bootstrap differences and completeness. Do not tune the grid, score or terms after reviewing these targets.

These are reused exploratory masks, not independent confirmation. The recent original model trains on recent inputs only and is contextual; both weather candidates use the same historical training. Historical reconstructed-total truth covers eligible recorded intervals, not unknown full-season counts or unobserved storm closures. The mean model still has no coherent arbitrary-interval predictive count distribution. Production remains unchanged.

If this control fails the historical gates, stop local smoothing/weighting screens and explain a fundamental abundance-model redesign before further fitting. Passing permits broader historical gap-length/attendance validation and then confirmation kept outside further tuning; it does not authorize production adoption.

## Completed results

All forty paired contexts finish. All 1,080 inner fits and eighty final fits pass the unchanged gradient and directional checks; maximum errors are 0.000178 and 3.79e-8 respectively. Forty baseline replays pass the saved-objective, component-rate and hidden-prediction checks. Raw statuses remain explicit: 715 fits report success and 445 report precision loss despite passing independent numerical acceptance; no fit reaches the 200-iteration cap (maximum 98). All 104 repository tests and formatting checks pass.

| Measure                                   | Weather baseline | Separate smoothing | Original benchmark |
| ----------------------------------------- | ---------------: | -----------------: | -----------------: |
| Historical dry MAE                        |          33.3996 |            33.3990 |            31.5247 |
| Early historical dry MAE                  |          24.4454 |            24.4503 |            21.5174 |
| Historical wet MAE                        |          20.7723 |            20.7418 |            24.3063 |
| Recent dry MAE                            |          47.7117 |            47.6411 |            47.8494 |
| Recent wet MAE                            |          29.9104 |            29.8891 |            44.6804 |
| Historical season absolute relative error |           15.83% |             15.79% |             13.27% |

Historical dry change is effectively zero (−0.002%). Paired year-bootstrap difference versus baseline is −0.0006 birds [−0.0346, +0.0295]; versus original it remains +1.8743 [+0.6740, +3.1542]. Historical wet difference is −0.0305 [−0.0731, +0.0096]. Recent dry difference is −0.0707 [−0.1634, +0.0078] and recent wet −0.0213 [−0.0813, +0.0361]. None of these small candidate-minus-baseline differences is resolved by the exploratory paired intervals. Historical wet and recent overall/wet advantages over the original remain visible; this change does not solve the historical dry/total deficit.

Training selection chooses unequal strengths in 24 of 40 contexts, including six of ten historical contexts. Across all contexts the selected (season, clock) pairs are (0.1, 0.1): seven; (0.1, 10): nine; (10, 0.1): fourteen; (10, 1): one; (10, 10): nine. Thus selection does use the added freedom, but it produces little held-out benefit. Historical dry MAE improves for three species, worsens for three and stays unchanged for four; recent dry improves for three, worsens for five and stays unchanged for two. The largest recent absolute gain is White Stork (−0.70 birds); the historical aggregate is essentially unchanged across the core panel. Detailed species/year/era outputs are retained.

Median final fitting time is 0.155 seconds versus 0.151 baseline; the median paired ratio is 1.001. Candidate selection plus final optimization takes median 5.49 seconds, maximum 8.15, excluding data reading and final diagnostic/output work. This is not a final-fit slowdown, but the nine-pair selection costs more than a shared-strength search. The candidate passes speed and historical-wet/recent-dry/recent-wet gates and fails all three historical-original gates: dry, early dry and reconstructed totals.

## Decision and next development goal

Do not adopt independent smoothing or extend validation of this failed replacement. Retain the small unweighted common-smoothing weather mean as a research reference, alongside the unchanged production benchmark. The tested penalty coupling is not the main explanation for the historical deficit. This does not prove that every possible penalty or seasonal specification is equivalent, and is not a reason to search a larger grid on reused targets.

Stop local smoothing, duration-weighting and correction-function experiments. The next goal is a simpler explanation and explicit design for historical abundance reconstruction, before another candidate fit. The current shared seasonal curve plus annual intercept assumes the same seasonal shape each year; the original temporal-component ablations and modest episode gain give some evidence that within-year departures matter. They do not establish that year-varying seasonality alone will close the gap, and the tested 183-coefficient episode implementation remains rejected.

A redesign should distinguish baseline seasonal passage from weather modulation, allow only a small and explicitly regularized amount of year-specific temporal variation, and retain exact interval-mean aggregation. First specify how this differs from the rejected episode candidate and what it simplifies relative to the original benchmark. Require a small runtime/identifiability pilot and a frozen historical dry/season versus wet/recent assessment before broad fitting. No architecture, new fit, hybrid prediction switch, uncertainty transfer or production replacement is selected here. Historical short-gap conditioning and joint seasonal uncertainty remain open after a satisfactory mean model; their earlier recent-only results do not establish historical performance.

## Reproduce

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_separate_smoothing.py --shard 0 2 > logs/separate-smoothing/run-0.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_separate_smoothing.py --shard 1 2 > logs/separate-smoothing/run-1.log 2>&1
uv run python scripts/research/review_history_season.py --root logs/separate-smoothing --candidate weather_separate > logs/separate-smoothing/review.log 2>&1
```

Create `logs/separate-smoothing` before redirecting logs. The two independent shards can run concurrently; review only after both exit successfully. All generated data, fits and assessment tables stay under ignored `logs/`.
