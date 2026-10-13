# Working-criterion and smoothing audit

## Scope and decision

Completed a retained-input audit of all forty saved historical seven-day and recent whole-day contexts from the episode/season screens. No model was fitted, no hidden count was used in the diagnostics, and production is unchanged. Keep the 51-coefficient historical weather mean. The next proposed comparison is a single duration-weighting control on this same mean, before adding terms or designing another latent-state model. This audit identifies a real resolution dependence and a smoothing interaction; it does not establish either as the cause of held-out deterioration.

## What the criterion actually does

The saved optimizer minimizes a power-1.5 working quasi-deviance plus penalties. For an intact observation with count y and mean μ, its loss is `2(√μ − √y)²/√μ`; the derivative with respect to μ is `(μ − y)/μ^1.5`. The mean remains the exact sum of hourly rates times recorded exposure. Thus mean aggregation is correct, while the working variance is proportional to `μ^1.5` regardless of interval duration. This is a valid working mean criterion, not a fitted predictive count distribution. Quasi-likelihood can use a mean/variance relationship without specifying a full sampling distribution; see the official [R family documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/family.html) and [mgcv model documentation](https://stat.ethz.ch/R-manual/R-devel/library/mgcv/html/gam.models.html).

For constant hourly observed and predicted rates, a d-hour intact count contributes √d times the one-hour loss, whereas d hourly observations contribute d times that loss. Its score for a common log-rate and expected information obey the same scaling. The ratio is therefore `1/√d`: an eight-hour survey contributes 35% of the weight of eight hourly counts. For a half-hour interval the ratio is 141%; partial intervals are also affected. This is a property of the coded criterion, not a numerical optimization failure. Algebraic checks cover durations 0.25–12 hours, including nonzero residuals, and verify the contrasting linear duration scaling of the Poisson working loss.

Weighting each intact observation's loss by `√d` restores linear duration scaling in this constant-rate example, retaining power 1.5 across rates and adding no mean coefficients. Equivalently, its working variance becomes proportional to `μ^1.5/√d`. This is a diagnostic assumption about how variance accumulates with exposure, not an assertion that successive hours are independent or that flock covariance is negligible. Aggregation still loses within-survey timing information. Variable hourly rates and correlated migration can prevent full equivalence of split and intact data; the weighting control cannot reconstruct missing hourly counts or establish coherent predictive uncertainty.

## Measured support on actual retained data

For each fitted baseline, intercept expected working information is `√μ`. Its duration-weighted counterpart is `√(dμ)`, evaluated at the same saved mean, without refitting. Compute each context's shares first and then average contexts; each species has equal representation within a task. These are diagnostics of intercept information, not all-coefficient leverage, effective sample size or measures of independent observations. Rates, abundance and duration all affect them.

| Retained era in historical-gap contexts | Share of hours | Current information share | Duration-weighted information share |
| --------------------------------------- | -------------: | ------------------------: | ----------------------------------: |
| 1993–2007                               |          33.9% |                     16.6% |                               30.5% |
| 2008–2016                               |          25.3% |                     22.3% |                               28.3% |
| 2017–2021                               |          17.0% |                     25.1% |                               16.8% |
| 2022–2025                               |          23.8% |                     36.0% |                               24.3% |

Early retained intervals are almost entirely longer than one hour; recent intervals are almost entirely at most one hour. In current recent-gap contexts, early years supply 39.0% of hours but 20.6% of current information, versus 35.2% under the hypothetical duration weight. The pattern is therefore present on both tasks. Full species/context/era/duration outputs include observed birds, loss and absolute intercept score; these describe training support only and must not be read as held-out improvement.

Earlier controlled recent coarsening changed aggregate MAE negligibly, and adding historical training left recent group MAE essentially unchanged. Those results remain valid. This audit does not prove that weighting is the historical problem, that increasing early-year influence will improve prediction, or that historical weather effects should replace recent ones.

## Shared smoothing interaction

The same training-selected λ multiplies both seasonal and six-harmonic clock penalties; annual and weather ridges retain strength one. Enlarging the seasonal basis changed λ from 0.1 to 10 in fifteen contexts, left it at 10 in twenty-two, and left it at 0.1 in three. No context changed downward. For those fifteen contexts the unchanged clock penalty was multiplied by 100. This is why the seasonal screen was not an isolated seasonal-shape experiment.

Conditional expected-information EDF are the block traces of `(Jᵀ diag(μ^-1.5) J + λP + ridge)^-1 Jᵀ diag(μ^-1.5) J`, where J is the exact interval-mean derivative matrix. They describe local penalized flexibility at the saved means and selected penalties; they omit smoothing-selection uncertainty and are not an independent assessment of prediction quality.

| Task       | Block  | Baseline median conditional EDF | Richer-season median conditional EDF |
| ---------- | ------ | ------------------------------: | -----------------------------------: |
| Historical | Season |                            6.01 |                                14.86 |
| Historical | Clock  |                            4.45 |                                 4.13 |
| Recent     | Season |                            6.04 |                                15.11 |
| Recent     | Clock  |                            4.71 |                                 4.14 |

The larger seasonal basis did gain considerable flexibility despite the stronger selected penalty. Its failure cannot be explained simply by saying the additional basis was completely suppressed. Clock flexibility decreased at the same time, and per-block penalty normalization is not invariant to basis size. Separating the two smoothing parameters would be a distinct, later control, not evidence already supplied by this audit.

## Proposed next comparison, not yet run

Compare the unchanged small weather model against exactly one modification: multiply observation loss, gradient and Hessian by `√exposure_hours`, with hours as the reference unit. Preserve intact counts, training/hidden masks, all design columns and penalty definitions. Use the existing three-week training-only smoothing grid separately for each arm; the working weight also enters its inner fits. Keep the same daily MAE selection rule. Replay every unweighted baseline and check weighted derivatives independently. Do not combine this with separate clock/season smoothing, change variance power, add episodes or tune duration exponents on these reused targets.

Use the same forty contexts and the seasonal screen's acceptance gates: historical dry MAE, early-era dry MAE and reconstructed-season absolute relative error no worse than the original; historical wet and recent dry/wet MAE no more than 2% worse than paired baseline; median final fit at most five seconds and at most five times baseline. Report each species, median species error ratios, eras, jointly blocked paired intervals and season errors. A passing screen still requires broader gap lengths and short-gap checks; it is not production authorization. A failing screen should be recorded without searching for a favorable duration exponent. Retain separate smoothing as an unresolved hypothesis and decide whether it merits one control based on the completed result.

## Reproduce

Run from the repository root after the saved episode and season fits are available:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/audit_rate_criterion.py > logs/rate-criterion-run.log 2>&1
```

Generated tables are under `logs/rate-criterion/`: `constant_rate_scaling.csv`, `interval_weights.csv`, `mean_weight_shares.csv`, `era_weight_shares.csv`, `smoothing_blocks.csv`, `median_smoothing_blocks.csv` and `smoothing_changes.csv`. No generated files should be committed.

## Completed duration-control follow-up

The user authorized testing damping as well as the square-root correction. [DURATION_WEIGHT.md](DURATION_WEIGHT.md) reports the completed power-0.25 screen and explicit power-0.5 failures. Neither is adopted: the complete damped arm misses historical benchmark gates and worsens recent wet error, while the stronger arm has four timeouts plus recent losses in completed cases. Keep the unweighted mean and establish bounded numerical behavior before another fit experiment; no further powers are being searched.
