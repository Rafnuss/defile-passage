# Proposed daily passage model: design before fitting

## Decision and evidence

The next goal is historical dry-gap and reconstructed-total accuracy while preserving recent and wet-gap gains. Stop expanding shared season bases, changing duration weights, searching smoothing grids or tuning retained-count corrections. The numerical pilot specified here is implemented and completed. The subsequent full-core batch is now attempted, with five numerical failures and a remaining reconstructed-total deficit; see [DAILY_PASSAGE_RESULTS.md](DAILY_PASSAGE_RESULTS.md). The current simple mean and original production model remain references.

The proposed change is a regularized daily deviation from the shared seasonal curve, linked between neighboring dates within a year. Weather and hourly timing still determine the passage rate within each date. This retains the episode idea the user supported, but changes its temporal structure and computational representation. It is not evidence that a new name for an episode effect will solve the problem.

The controlled evidence is specific: removing the original model's episodes raises early dry-gap MAE from 21.52 to 23.28, while removing its long-term timing shift changes it only to 21.54. Adding four broad spline coefficients per year to the weather model improves historical dry MAE from 33.40 to 32.76, but leaves it above original 31.52 and costs 8.76 times the baseline final fit. Richer shared season, duration weighting and independent season/clock smoothing do not close the deficit. These results support testing local multiday variation; they do not establish its physical cause or guarantee that a different episode representation will win. See [HISTORY_DIAGNOSIS.md](HISTORY_DIAGNOSIS.md), [HISTORY_EPISODE.md](HISTORY_EPISODE.md) and [SEPARATE_SMOOTHING.md](SEPARATE_SMOOTHING.md).

## Model and observation scale

Fit each core species separately under the same specification. For year y, calendar date d and canonical clock hour h:

```text
log rate[y,d,h] = intercept + annual_offset[y] + shared_season[d]
                  + daily_deviation[y,d] + clock_profile[h]
                  + weather[y,d,h] + night[y,d,h]

expected_count[i] = sum over covered hours h of fraction[i,h] * rate[y,d,h]
```

Keep the existing seven seasonal columns, six UTC clock harmonics, two rain columns, wind u/v, civil-night indicator and annual contrasts. Exposure remains actual hours. Hourly weather is evaluated with the existing alignment and canonical-hour approximation. Do not return to an unsupported daylight spline or introduce solar normalization, changing weather covariates or within-hour integration in the same experiment.

Complete surveys retain observed zeros. Unobserved dates, incomplete surveys and weather closures receive no zero counts. Unresolved survey totals enter as intact counts against their summed expected means; birds are never allocated into hourly observations. If an interval crosses dates, sum the appropriate date-specific rates before evaluating its count criterion.

The shared season and annual offset already describe average passage and annual level. The daily deviation describes temporary departures around that baseline. This is a predictive decomposition: local weather and departures can be correlated, so the components cannot be identified as causal migration availability and weather inhibition from this fit alone. There is no bird reservoir, accumulation/release mechanism or conservation of birds across a rain closure in this proposal.

## Local temporal structure

Give the daily deviations a stationary AR(1) quadratic penalty separately within each year's fixed analysis window:

```text
rho = exp(-1 / 7)
penalty = [u[first]^2 + sum((u[d] - rho*u[d-1])^2 / (1-rho^2))] / (2*sigma^2)
```

The seven-day correlation scale is a prespecified working assumption for this first design, not an estimated biological constant or a promise of seven-day prediction skill. The endpoint term matters; omitting it would create a different, less constrained process. Use every calendar date, including dates without observations. Adjacent entries mean adjacent dates, never adjacent available surveys. Reset the chain at the start of each year; do not smooth from November to July. Center deviations to sum to zero over the fixed calendar window in each year, separating them from annual level. Retain the original penalties on shared effects. Centering does not remove all shared-season or weather confounding; finite penalties regularize that overlap rather than prove separate biological identification.

Near a short gap, neighboring observations can inform the deviation. Deep inside a sufficiently long gap, its fitted mode shrinks toward zero and the shared season/year/weather baseline dominates. Observations retained on a partially counted date inform its same daily deviation directly during fitting. Do not apply the existing empirical retained-count multiplier on top. A multiplier common to the day cannot explain independent within-day passage bursts; that remains a limitation.

## Difference from rejected approaches

| Approach                              | Temporal representation                                               | Computational implication                                                                 |
| ------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Current small weather mean            | Same seasonal shape each year, annual level changes                   | 51 dense coefficients; fast reference                                                     |
| Rejected historical episode candidate | Four broad spline coefficients per year                               | 183 dense coefficients; modest accuracy gain, failed runtime gate                         |
| Proposed daily deviation              | One value per calendar date, neighboring-date penalty                 | About 4,092 local values plus 51 shared coefficients; sparse structure must earn its cost |
| Archived hurdle/shared-Gamma model    | Separate occurrence/positive processes, integrated latent daily state | Quadrature/count convolutions; not resumed                                                |

The proposed model has more local unknowns than either retained or rejected spline model. It is simpler in its local rule and possible sparse computation, not smaller in parameter count. Regularization controls its effective flexibility. Do not call it faster, more identifiable or scientifically better until the pilot and comparison establish that. If exploiting sparsity requires layers of bespoke numerical fixes, reject this direction under the user's simplicity requirement.

## Fitting strategy and limits

Keep the unweighted power-1.5 working mean objective, so the first test isolates the temporal representation. Estimate shared coefficients and daily modes jointly. Do not fit deviations to held-out residuals, freeze weather from an all-data fit or fit a separate post-hoc count adjustment. The criterion still does not define a coherent arbitrary-interval count distribution.

The daily penalty has a tridiagonal precision before centering constraints. Observation derivatives are sparse in their date entries, although shared-coefficient interactions are dense and cross-date intervals must be represented. Investigate one bounded sparse penalized scoring method with objective-decreasing steps, using a small shared-coefficient system and sparse date solves. Do not feed thousands of daily columns into the dense BFGS fitter. Do not add quadrature, a second count process, a solver ladder or fallback predictions. The positive working-information matrix is a computational scoring approximation, not the exact objective Hessian; retain independent objective-gradient checks and actual objective descent.

At this stage sparse runtime is a hypothesis. A prototype must state its iteration and line-search limits before running, preserve all failures and stop if the fixed method cannot meet numerical gates. No optimizer tuning based on prediction errors.

Predictions initially use the fitted daily mode and shared coefficients. They are conditional working-mean estimates, not means integrated over uncertainty in the daily state. Do not add a lognormal correction or reuse existing empirical intervals without a separately assessed uncertainty procedure.

## Next executable step: small numerical pilot

After this design step, implement only a numerical/runtime pilot: Common Buzzard (high counts), European Honey Buzzard (previous solver difficulty), Great Cormorant (mixed-scale/flock variability) and White Stork (sparse passage), each on historical fold 2 and recent fold 0. These eight existing contexts diagnose implementation; they are not a new species selection for efficacy.

Use fixed correlation scale seven days and fixed stationary log-deviation SD 0.5. These pilot values are computational test settings, not selected predictive settings. Reuse each baseline's retained-training-selected shared smoothing. Do not inspect held-out count accuracy during this pilot or launch the forty-context efficacy comparison automatically.

Before actual-data fitting, verify analytic gradients, interval sums and the sparse step against a dense small synthetic problem, including observed zero counts, an entirely unobserved run and a cross-date interval. Check centering and no cross-year borrowing. Show that removing daily deviations reproduces the saved baseline. Save wall time, iteration counts, objective descent, derivative error, final gradient and sparse-system dimensions. Inspect regularized information conditioning and retained weather support; a finite penalized solution alone does not establish data identification.

Numerical acceptance remains gradient and directional error below 0.001. Pilot median final fitting time must be at most five seconds and five times the paired current-model baseline, with a 60-second whole-context execution limit. Use the same thread settings for both. State counts and effective flexibility must be reported alongside runtime, rather than hiding complexity behind a sparse implementation. A failure stops this design; do not silently relax gates.

## Numerical pilot implementation protocol

The user authorized the numerical pilot after reviewing this design. Implement one sparse penalized scoring method with at most 100 updates, at most twenty halvings per update and Armijo decrease constant 1e-4. The optimization target is maximum constrained gradient 1e-5; independent numerical acceptance remains 0.001. Initialize shared effects at zero except the exposure-based intercept, with daily deviations zero, rather than obtaining a free warm start from the paired baseline. No model/optimizer retries or tolerance changes. Each context runs in its own process with the prespecified 60-second limit; complete the eight-context batch before inspecting results, preserving failures.

Eliminate daily values with sparse LU and exact year-centering constraints, then solve the 51-dimensional shared-coefficient Schur system. The actual objective gradient is projected onto the centered daily subspace, and numerical derivatives check that same constrained objective. Use positive working information for scoring and verify objective decrease; do not label it an exact Hessian or posterior covariance. Estimate total working effective degrees of freedom with 32 fixed-seed Rademacher trace probes and report their Monte Carlo standard error. Report scaled shared-Schur and conditional daily-information conditioning separately; neither proves causal identification of weather and passage.

Scripts are `daily_passage_model.py`, `check_daily_passage.py`, `run_daily_passage_pilot.py` and `batch_daily_passage_pilot.py`. Synthetic checks pass before actual-data fitting, including independent dense KKT agreement. The pilot deliberately writes no hidden-count predictions, accuracy scores or predictive intervals. Generated diagnostics, state estimates and retained-hour weather support go to `logs/daily-passage-pilot/`.

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/check_daily_passage.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/batch_daily_passage_pilot.py > logs/daily-passage-pilot/batch.log 2>&1
```

## Completed numerical pilot

All eight fixed contexts finish without timeouts or retries and pass all nine prespecified numerical/completeness/runtime gates. All baseline objective and component-rate replays pass, and removing daily deviations reproduces the working objective exactly. Maximum constrained gradient is 0.0001475, directional error 1.992e-8 and yearly centering error 5.49e-14. Every accepted update decreases the objective. Seven fits reach the optimizer's 1e-5 target; historical Common Buzzard reaches the unchanged 100-update cap at gradient 0.0001475, which still passes the separately prespecified 0.001 acceptance limit. Preserve that cap status; do not call all eight optimizer-target successes or increase its budget.

| Context                    | Final seconds | Ratio to paired baseline | Updates | Total working effective DF |
| -------------------------- | ------------: | -----------------------: | ------: | -------------------------: |
| Historical Common Buzzard  |         1.515 |                     9.73 |     100 |                        819 |
| Historical Honey Buzzard   |         0.666 |                     3.86 |      42 |                        483 |
| Historical Great Cormorant |         0.334 |                     2.37 |      22 |                        992 |
| Historical White Stork     |         0.540 |                     4.11 |      34 |                        507 |
| Recent Common Buzzard      |         0.642 |                     3.33 |      31 |                      1,045 |
| Recent Honey Buzzard       |         0.629 |                     3.44 |      38 |                        606 |
| Recent Great Cormorant     |         0.373 |                     2.71 |      23 |                      1,212 |
| Recent White Stork         |         0.617 |                     4.70 |      36 |                        602 |

Median final fitting time is 0.623 seconds versus 0.148 for the paired baseline; median paired ratio is 3.65. The gate is the median paired ratio, not a per-species fivefold limit: historical Buzzard exceeds fivefold and remains visible. Maximum final fit is 1.515 seconds and maximum whole-context time 2.132 seconds, including reading, baseline fit, numerical checks, effective-DF and information diagnostics. Timings use one process and one BLAS thread; simultaneous repository tests may add timing noise. All eight share 51 global coefficients plus 4,092 daily values, with 4,059 free daily values after the 33 yearly constraints. Conditional daily information has only 12,210 nonzero entries.

Total working effective DF ranges from 483 to 1,212, with trace-estimation Monte Carlo standard errors 2.07–3.15. This is appreciably more effective flexibility than the small model's 51 available coefficients; sparse runtime does not make the proposed model statistically small. The fixed SD 0.5 is a pilot setting, not a selected predictive setting. Overfitting is an unresolved risk, and the zero-deviation candidate must remain available in training selection.

Scaled shared-Schur condition numbers are approximately 734–8,289; conditional daily-information eigenvalue ratios are approximately 252–540. No sparse/dense agreement, objective-descent or derivative pathology is exposed, but the shared effects are not orthogonal and finite penalized conditioning does not establish data or causal identification. Retained data contain both dry and wet hours in all 264 context-year combinations, with observed hourly rain reaching 7.6 mm. This shows nonempty weather support, not balanced heavy-rain support or identified effects during unobserved closures. Per-year support is saved rather than assigning counts to those closures.

The independent synthetic checks additionally verify the multi-right-hand-side influence calculation against the dense constrained system. All 104 repository tests pass. No held-out count accuracy, missing-count totals, predictive intervals or forty-context efficacy results are computed in this pilot. The next proposed experiment is the training-selected full core comparison below, with the implementation and numerical budgets frozen. Numerical/runtime success permits that experiment; it does not select the model or change production.

Run `uv run python scripts/research/review_daily_passage_pilot.py` to regenerate the numerical report and `logs/daily-passage-pilot/acceptance.csv` from saved diagnostics.

## Efficacy assessment after the passing pilot

Freeze the implementation before efficacy fitting. Keep the seven-day correlation scale fixed. Select stationary deviation SD from 0, 0.25, 0.5 and 1 using the existing retained-training calendar-week folds and daily MAE, with SD zero exactly the current weather model. This is species-level training selection under one common rule, not a species switch selected from outer test errors. The shared smoothing remains the paired baseline's training-selected value to isolate the temporal control; no joint smooth search or new variance power is added.

All inner folds must refit both shared coefficients and daily deviations using only their retained counts; neighboring hidden dates have no count contributions. Shared preprocessing follows the existing outer-retained design rule and must be stated explicitly. Save every training score and numerical failure. Review outer accuracy once after all forty contexts finish.

Keep the same ten core species and historical seven-day/current recent masks for this exploratory screen. Require historical dry, early-era dry and reconstructed-total errors no worse than original; historical wet and recent dry/wet MAE at most 2% worse than current weather baseline; final runtime within the pilot gates. Report species/era/year, signed total bias, jointly blocked uncertainty, effective temporal flexibility and end-to-end selection time. Reused masks can reject a candidate but cannot supply independent confirmation. Passing requires broader gap-length/attendance tests, then confirmation excluded from tuning. Joint seasonal uncertainty, early partial-day conditioning and production adoption remain later gates.

## Full-core follow-up result

The user-authorized efficacy batch is now attempted under the fixed protocol. Thirty-five of forty contexts supply accepted paired predictions; four inner grids and one selected final fit fail numerical acceptance. The partial matched panel improves daily MAE, including dry gaps, but reconstructed-total error remains 15.10% versus matched original 12.94% and signed season bias becomes more negative. Numerical completeness and season-total gates block adoption. Preserve the pilot as a numerical feasibility result, not evidence that the proposed model is accepted. Next proposed work is saved-fit convergence and bias diagnosis, without another broad fit or automatic increase in budgets. Full results, failures and matched scope: [DAILY_PASSAGE_RESULTS.md](DAILY_PASSAGE_RESULTS.md).
