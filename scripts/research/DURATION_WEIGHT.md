# Duration weighting with a prespecified damped alternative

## Protocol fixed before fitting

The user requested damping as well as the previously proposed duration control. Test observation weights `duration_hours^0.25` and `duration_hours^0.5` against the unchanged power-1.5 weather mean. One hour has weight one; eight hours have weights 1.68 and 2.83 respectively, rather than eight. Half-hour weights are 0.84 and 0.71. Apply weights to loss, gradient and Hessian for intact counts. Do not normalize weights by each training sample's mean, so the hourly reference and penalty units stay fixed across folds. This changes the relative data-to-penalty strength as well as the relative weights of observations; reselect the existing common smoothing parameter on training inputs only.

Keep the same forty episode/season contexts: ten core species on historical seven-day gaps and three recent masks, all with eligible historical training. Preserve all 51 design columns, exact interval aggregation, annual/weather ridges and the shared seasonal/clock penalty matrix. Replay forty unweighted fits and hidden predictions within 1e-7. Weighted inner fits use the same three calendar-week folds and smoothing grid 0.1/1/10; daily MAE selects smoothing. Neither power is selected on held-out targets or varied by species/year/weather. No seasonal expansion, episodes, retained-count correction, new variance power or independent smooth parameters are added.

Assess both powers separately under the same frozen gates as the seasonal screen: historical dry MAE, early-era dry MAE and eligible reconstructed-season absolute relative error no worse than original; historical wet and recent dry/wet MAE at most 2% worse than paired weather baseline; median final fit at most five seconds and five times baseline. Report species scores and median species ratios, historical eras, jointly blocked paired bootstrap intervals and runtime. If both pass, prioritize the damped power for broader validation; if neither passes, reject both without searching further powers on reused targets. A passing screen permits wider one-/three-day and short-gap validation, not production replacement or a predictive-distribution claim.

Numerical checks include independent off-optimum and fitted-gradient checks with unequal durations/zero counts, the analytic constant-rate optimum for all three powers, exact all-one-weight/default replay, and directional checks on every final fit. Counts remain intact and absent hours remain unknown. The duration assumption is a working variance control, not proof that migration/flock variance is additive; see [RATE_CRITERION.md](RATE_CRITERION.md).

## Reproduce

These are the initial unrestricted batch commands; the square-root arm can stall. For a bounded fresh run, use the completion script shown at the end after `mkdir -p logs/duration-weight`. It starts all pending contexts, including when there are no saved fits.

```sh
uv run python scripts/research/check_duration_weight.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_duration_weight.py --shard 0 2 > logs/duration-weight/run-0.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_duration_weight.py --shard 1 2 > logs/duration-weight/run-1.log 2>&1
uv run python scripts/research/review_history_season.py --root logs/duration-weight/power-0.25 --candidate weather_weighted > logs/duration-weight/review-0.25.log 2>&1
uv run python scripts/research/review_history_season.py --root logs/duration-weight/power-0.5 --candidate weather_weighted > logs/duration-weight/review-0.5.log 2>&1
```

The existing paired reviewer now accepts root/candidate arguments; its default seasonal-screen behavior and output column names remain unchanged. Generated per-context fits and complete assessment tables are under `logs/duration-weight/power-0.25/` and `power-0.5/`. All generated artifacts remain uncommitted. Production is unchanged.

## Completed results and numerical failure

The damped power 0.25 completes all forty contexts. Every baseline coefficient/hidden prediction replays within 1e-7; all forty damped final fits pass gradient/directional checks. The final solver and thresholds remain unchanged. This is a complete ten-core-species comparison, including Honey Buzzard, with no species switches or excluded failures.

| Measure                                   | Baseline | Damped duration weight | Original |
| ----------------------------------------- | -------: | ---------------------: | -------: |
| Historical dry MAE                        |    33.40 |                  33.29 |    31.52 |
| Early historical dry MAE                  |    24.45 |                  24.24 |    21.52 |
| Historical wet MAE                        |    20.77 |                  20.80 |    24.31 |
| Recent dry MAE                            |    47.71 |                  48.25 |    47.85 |
| Recent wet MAE                            |    29.91 |                  30.68 |    44.68 |
| Historical season absolute relative error |   15.83% |                 15.68% |   13.27% |

Historical dry improves for eight of ten species, but by only 0.3% in equal-species MAE; the median species ratio is 0.9986. Early historical dry improves 0.20 birds and still misses the original by 2.73. Recent dry worsens for eight of ten species; median ratio 1.0119. Thus the direction is not a single-species artifact. Recent wet worsens 2.6%, exceeding the frozen 2% point limit. The candidate fails all three historical-original gates and the recent wet gate.

Paired jointly blocked bootstrap differences versus baseline are −0.11 [−0.25, +0.03] historical dry, +0.03 [−0.12, +0.17] historical wet, +0.54 [+0.25, +0.84] recent dry and +0.77 [+0.49, +1.13] recent wet. These reused development masks support a recent loss but do not resolve the tiny historical gain. Median damped final fit is 0.159 seconds, maximum 0.217, versus baseline median 0.160; the median paired runtime ratio is 0.992. It fails accuracy, not final fitting speed.

The square-root power 0.5 completes thirty-six contexts covering nine core species. It stalls inside SciPy's exact trust-region inner solve in all three recent Honey Buzzard masks and its historical seven-day mask. The first stalled batch was interrupted after more than ten minutes; a native process sample and interruption traceback identify `IterativeSubproblem.solve` / `estimate_smallest_singular_value`. The configured outer maximum of 100 optimizer iterations does not bound this inner calculation. This is a numerical failure under the tested solver, not proof that the weighted statistical criterion is intrinsically invalid.

After diagnosing the stall, finish pending contexts in separate processes with a 60-second whole-context limit (`finish_duration_weight.py`), preserving completed damped fits and every solver/criterion/threshold. This execution limit was added in response to the stall, before reviewing accuracy, rather than being part of the initial protocol. All four Honey Buzzard contexts time out again; record them in `failures.csv` and the stronger arm's `missing_contexts.csv`. No solver ladder, changed tolerance, fallback prediction, hidden-count choice or imputation of failed means is used. All thirty-six completed stronger final fits pass the existing checks; their median 0.158-second final time describes only converged cases and must not conceal the stalled inner fits.

On its matched nine-species subset, stronger weighting changes historical dry MAE 31.48 → 31.28 (−0.6%), historical wet 19.93 → 19.96 (+0.1%), recent dry 50.65 → 51.89 (+2.4%) and recent wet 29.55 → 31.30 (+5.9%). Seven of nine improve historical dry and only two improve recent dry; median ratios 0.9971 and 1.0228 respectively. Season error improves 14.78% → 14.47%, still above matched original 12.46%. These are partial diagnostics, not ten-species scores and not directly comparable with the ten-species absolute MAE table above. The stronger candidate cannot pass the added completeness check. The recent deterioration is present among the other nine species even without the failed Honey Buzzard cases.

## Decision and next step

Reject damped weighting on the prespecified accuracy gates. Do not adopt square-root weighting: it has four numerical failures and its completed cases also show small historical gains with larger recent losses. Keep the unweighted small weather mean. Duration-dependent influence is real, but this control does not establish it as the main source of the historical dry/season deficit. Do not search more exponents, introduce species-specific powers, or increase model complexity to rescue this result.

Separate season/clock smoothing remains an untested hypothesis; it should not be presented as a demonstrated fix. Before another fitting screen, establish a bounded numerical solver strategy for this same small objective. The exact solver's internal stall is now an explicit limitation despite fast median final fits and previously successful baselines. That is a computational issue to resolve, not a reason to add statistical terms or revive the rejected latent-state machinery. No replacement is selected and no additional fitting experiment is launched here.

The generalized reviewer permits explicitly requested incomplete diagnostics and adds a mandatory completeness gate, so partial scores cannot pass acceptance. Its default seasonal behavior reproduces all ten saved result tables byte-for-byte. The standalone weighted check verifies Hessians by independent finite differences as well as gradients and known optima; all 104 repository tests pass. Generated runtime/numerical tables retain the completed contexts and failures separately.

To finish/review a bounded run that encountered stalls:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/finish_duration_weight.py > logs/duration-weight/finish.log 2>&1
uv run python scripts/research/review_history_season.py --root logs/duration-weight/power-0.25 --candidate weather_weighted --allow-incomplete > logs/duration-weight/review-0.25.log 2>&1
uv run python scripts/research/review_history_season.py --root logs/duration-weight/power-0.5 --candidate weather_weighted --allow-incomplete > logs/duration-weight/review-0.5.log 2>&1
```
