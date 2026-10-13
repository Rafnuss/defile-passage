# Saved-fit diagnosis: convergence and missing-total bias

## Scope fixed before calculation

Audit the completed daily-passage batch without optimizing, changing budgets, selecting parameters or generating a new candidate's fills. Use all 35 accepted outer contexts for bias attribution and all 36 saved selected final checkpoints for numerical diagnosis, including the failed historical Sparrowhawk fit. Four failed inner fits have histories but no saved coefficient vectors: their endpoint curvature cannot be reconstructed without rerunning, which this audit does not do. Preserve that limitation.

For convergence, summarize the last twenty accepted updates in each of the five failed trajectories. At available final checkpoints, re-evaluate the exact working objective/gradient and compare the positive scoring information with independently verified observed curvature. Compute one unapplied scoring direction and its predicted linearized gradient contraction and directional curvature ratio; do not take that step or label it a repaired fit. Retain the largest shared/daily gradient components and exact fitted-gradient reproduction. This separates derivative disagreement from a conservative scoring metric where the saved evidence permits it.

For bias, reconstruct saved predictions exactly. Decompose the change from baseline into (1) changed shared coefficients with the daily deviation set to zero and (2) the daily multiplier at those coefficients. This ordered algebraic decomposition is not a causal attribution and its intermediate mean is not a fitted candidate. Compare retained versus hidden intervals and record weighted daily multipliers and zero-state mean ratios. Use the same accepted targets and denominators throughout; omit the five invalid contexts.

Separate zero, positive and peak observed hidden days. Peak means above each task/species's 90th percentile of observed hidden daily counts; this is a descriptive outcome-defined group, not a prediction rule or training choice. Contributions to relative total bias use each species's full hidden-count denominator, so strata add to the existing equal-species total bias. Save weather/era/species breakdowns and reconstructed-season bias separately.

Assess the scale of the conditional-mode hypothesis using the diagonal inverse of the exact daily curvature, with shared coefficients and selected SD fixed and yearly centering enforced. Actual observations in this audit must couple dates only within their year; verify that before using year blocks. These local Gaussian curvature proxies are not a calibrated posterior, omit coefficient/SD/dispersion uncertainty and cannot prove the size of an integrated predictive mean under the working criterion. Summarize the implied factor exp(variance/2) and its mean-rate-weighted scale on retained/hidden support, without writing adjusted predictions, scoring a corrected candidate or adopting a lognormal correction.

Check observed curvature against finite differences on a synthetic example with zero counts, unobserved runs and cross-date intervals. Check centered variances independently against a dense constrained inverse. Run all saved calculations before interpreting their results. Production and saved model fits remain unchanged. Outputs go to `logs/daily-passage-diagnosis/`.

## Completed diagnosis

All 36 selected final checkpoints are audited without fitting or applying a step; all 35 accepted contexts reproduce their saved hidden means. The four failed inner endpoints remain unavailable, so their curvature is not inferred from a different fit. All overall and weather-specific missing-count biases reconcile with the previous batch to 1e-12. Reconstructed-season summaries are retained separately with their original species/year weighting. These are the same incomplete development targets: seven historical species and 28 recent masks across ten species. They do not establish performance for the five missing contexts or actual unobserved storm closures.

### Numerical failures

All five failed histories take full steps on their last twenty updates while decreasing the objective. Geometric maximum-gradient ratios per update are 0.9241 (recent Heron), 0.9913 (recent Stork), 0.9504 (historical Heron), 0.9691 (historical Marsh Harrier) and 0.9951 (historical Sparrowhawk). This establishes slow endpoint convergence in the saved trajectories, not prediction accuracy or the remaining distance to an optimum.

The failed final Sparrowhawk maximum gradient is 0.006525, dominated by shared term `season_5`; the daily maximum is 0.003497. Independent observed-curvature checks pass: its Hessian-vector discrepancy is 4.27e-9, and the maximum over all 36 checkpoints is 2.58e-8. Along the unapplied scoring direction, observed curvature is 1.9948 times the scoring curvature and the linearized next-gradient magnitude is 0.99475 times the current one. This is consistent with a nearly reflected gradient and very slow contraction near the endpoint, rather than a derivative error or an overly conservative direction. It does not verify an actual additional update or establish this mechanism for the four unavailable inner endpoints. The scoring matrix is positive but need not bound the true curvature. Its numerical gate remains failed.

### Where the missing-total loss arises

The following entries are percentage points of each species's observed count total, averaged equally over species after pooling its completed masks. The shared-only intermediate sets the fitted daily deviations to zero while retaining the candidate's jointly fitted shared coefficients. It is an algebraic decomposition, not a separately fitted model or causal attribution.

| Task/support        | Baseline bias | Change from shared coefficients | Change from daily deviations | Final daily-model bias |
| ------------------- | ------------: | ------------------------------: | ---------------------------: | ---------------------: |
| Historical retained |        −0.80% |                       −25.29 pp |                    +17.96 pp |                 −8.13% |
| Historical hidden   |        −5.05% |                       −25.24 pp |                    +11.60 pp |                −18.68% |
| Recent retained     |        −1.20% |                       −30.25 pp |                    +22.38 pp |                 −9.06% |
| Recent hidden       |        −0.31% |                       −20.30 pp |                     −2.77 pp |                −23.38% |

The shared reference falls for every completed historical species and eight of ten recent species on hidden support. Daily deviations compensate more on retained observations than on hidden observations, especially on recent whole-day gaps. All seven historical species have a more negative hidden bias than their baseline; all ten recent species underpredict, with Grey Heron −58.7% and Honey Buzzard −43.4% the largest recent deficits. This is a core-species issue, without pigeons or passerines in the audit. It is not only a failed-fit issue: these bias calculations use numerically accepted contexts.

The retained unpenalized intercept score is essentially zero (maximum absolute value 0.000119), despite raw retained-count deficits of 8–9%. The fitted equation is `sum((mean − count)/sqrt(mean)) = 0`, not `sum(mean − count) = 0`. Thus the working objective can satisfy its first-order condition while failing raw count conservation. Penalties and daily flexibility can change this balance; the decomposition alone cannot assign the loss to one mechanism or prove a change of criterion would repair held-out totals.

### Daily MAE and total reconstruction favor different behavior

Peaks are the observed held-out days above each task/species's 90th count percentile. These outcome-defined groups are descriptive; no fitted choice depends on their membership.

| Task/count group          | Baseline MAE | Daily-model MAE | Baseline contribution to total bias | Daily-model contribution |
| ------------------------- | -----------: | --------------: | ----------------------------------: | -----------------------: |
| Historical zero           |         4.92 |            3.59 |                            +8.22 pp |                 +5.45 pp |
| Historical other positive |        39.87 |           32.29 |                           +22.63 pp |                +14.30 pp |
| Historical peak           |       209.54 |          214.39 |                           −35.89 pp |                −38.44 pp |
| Recent zero               |         9.37 |            6.69 |                            +8.36 pp |                 +4.93 pp |
| Recent other positive     |        37.48 |           30.41 |                           +22.08 pp |                 +6.38 pp |
| Recent peak               |       185.08 |          205.75 |                           −30.74 pp |                −34.69 pp |

The daily candidate improves zero and ordinary-positive day errors, but worsens peak-day errors. Most of the additional net deficit comes from reducing the baseline's compensating excess on nonpeak days; peak underprediction also worsens. Therefore the lower daily MAE is real on these targets, and the poorer totals are also real. Neither can stand in for the other. The original benchmark also misses peaks: its peak contributions are −37.16 pp historically and −34.39 pp recently. Its better net total balance partly reflects more compensating nonpeak excess, not universal peak recovery.

The deterioration spans historical eras: hidden-count bias is −21.21% for 1993–2007, −14.21% for 2008–2016 and −25.18% for 2017–2021. Dry hidden bias is −16.51% historically and −25.72% recently; wet bias is −21.21% historically and −0.38% recently. Recent wet aggregate balance does not imply species-level calibration. These group-specific denominators differ from the additive count-stratum contributions above. Reconstructed-season bias remains −7.19% and absolute relative error 15.10%, versus original −3.50% and 12.94%, using the earlier matched seven-species assessment.

### Conditional-mode hypothesis remains incomplete

With coefficients, SD and objective scale fixed, the local centered Gaussian curvature proxy implies mean-rate-weighted factors averaging 1.0377 historically and 1.0726 recently on hidden support, versus 1.0115 and 1.0181 on retained support. Its scale is smaller than the observed 19–23% missing-count deficits. This weakens the specific explanation that the fixed-coefficient local Gaussian mode-to-mean difference alone accounts for the entire deficit. It does not rule out larger uncertainty effects: these proxies omit shared-coefficient uncertainty, SD/dispersion uncertainty and non-Gaussian behavior, and the working objective is not a calibrated probability distribution. No corrected daily fills, accuracy scores or automatic lognormal multiplier are produced.

## Decision and next bounded step

Keep the weather reference and original production model. Do not promote the daily candidate, increase its fitting cap, tune another amplitude grid or add post-hoc count multipliers. A numerical repair alone cannot resolve a total bias already present among accepted fits, and training selection by daily MAE alone does not protect reconstructed totals.

Before another broad screen, specify one count-balanced working-criterion control with the same hourly mean aggregation and existing predictor/state structure. A fixed power-1 (Poisson working) criterion is a simple candidate because its unpenalized intercept score balances retained raw counts. This is not a claim of Poisson dispersion, calibrated uncertainty or guaranteed hidden-count conservation. Earlier mean-only Poisson experiments did not establish acceptable dry-day performance; the proposed question is whether count balance changes the jointly fitted daily-state tradeoff. Compare a matching no-state reference to separate a criterion effect from a state effect, preserve the current SD-selection rule for isolation, and retain total error and dry/wet MAE as separate acceptance gates. Any later change of selection target must be a separate control, not bundled into this comparison.

First demonstrate a single bounded numerical method for that specified criterion on representative difficult contexts, with saved inner endpoints and unchanged independent checks, before efficacy assessment. The present scoring-curvature mismatch motivates inspecting an objective-consistent step scale rather than raising iteration budgets; no new optimizer or repaired fit is implemented here. This is a proposed experiment, not an accepted replacement or an authorization to start another batch.

## Reproduction and verification

From the exploration repository, use one BLAS thread and run `uv run python scripts/research/check_passage_diagnostics.py`, then `uv run python scripts/research/diagnose_daily_passage.py`, then `uv run python scripts/research/review_passage_diagnosis.py`. The audit reads saved design/fit tables under `logs/history-episode/` and `logs/daily-passage/`; it writes generated results under `logs/daily-passage-diagnosis/`. The synthetic observed Hessian matches independent finite differences, and centered conditional variances match a dense constrained inverse. Repository tests and formatting checks are recorded alongside the audit. Production and source fitting code are unchanged.
