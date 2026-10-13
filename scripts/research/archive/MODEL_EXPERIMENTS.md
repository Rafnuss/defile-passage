> Archived development record, frozen on 12 October 2026. Statements about active models and next steps below describe earlier work. The current decision is [MODEL_SPECIFICATION.md](../MODEL_SPECIFICATION.md); no further experiments are scheduled. Commands assume the repository root.

# Weather-aware gap filling: specification and experiment history

## Current retained model (12 October 2026)

The active development model is the 22-coefficient weather-only mean model, not the archived hurdle/shared-Gamma experiments below. Its hourly log rate contains an intercept, three year contrasts, seven seasonal basis coefficients, six 24-hour UTC Fourier coefficients, log rain and its hinge at 1 mm/hour, wind u/v and civil-night status. Expected interval counts sum rates times actual covered hours. The fitting criterion uses fixed Tweedie working variance power 1.5, training-week-selected smoothing and unit penalties on linear weather/year/night coefficients. No episode or latent-state likelihood is retained.

A separate empirical prediction layer now estimates full-day and short-gap count intervals from training-only out-of-fold residuals. For short gaps, one training-selected pseudo-count shrinks the retained count/expected-count ratio toward one before multiplying the missing mean. This is an empirical update, not a Bayesian daily-state posterior. Full-day means remain unchanged. Core-species short-gap MAE improves 15.8%; nominal full-day 95% intervals have 95.2% observed coverage on reused internal holdouts. Wet passerine undercoverage, conservative short wet intervals and full-day mean bias remain explicit.

Historical core scope is verified for the ten species from 1993 under the adopted taxonomy start and annual-record criterion. The same weather mean has 51 coefficients over 1993–2025. The bounded four-coefficient-per-year episode screen improves historical dry accuracy slightly and preserves recent group gains, but does not close the original benchmark's early dry or season-total advantage and is not adopted. See [HISTORY_EPISODE.md](../HISTORY_EPISODE.md) for the protocol and results.

Increasing the shared seasonal basis to k=20 is also rejected: it remains fast but slightly worsens historical dry and season-total accuracy under the existing fitting rules. The seven-coefficient common season remains retained; see [HISTORY_SEASON.md](../HISTORY_SEASON.md).

See [SIMPLE_RATE_RESULTS.md](../SIMPLE_RATE_RESULTS.md) for mean-model assessments and [SIMPLE_RATE_UNCERTAINTY.md](../SIMPLE_RATE_UNCERTAINTY.md) for prediction formulas, calibration, artifacts and limitations. Production is unchanged; joint multi-day uncertainty, historical predictive calibration and independent confirmation remain open.

## Archived model experiments

The material below records earlier approaches and their limitations. Its likelihoods, current-fit statements and simulation procedures describe those archived experiments, not the retained model above.

## Time and observation units

Calendar day of year describes the migration season. Within-day timing uses the daylight coordinate `tau = (time − civil dawn)/(civil dusk − civil dawn)`, where civil dawn/dusk correspond to solar altitude −6°. These are civil-twilight bounds, rather than literal sunrise and sunset. Weather remains attached to real UTC clock hours. Exposure is measured in real hours; a normalized daylight coordinate never replaces exposure. The current fits evaluate covariates at the observed interval midpoint. Within-hour integration of the time smooth remains outstanding.

Counts are constructed independently of bird-entry timestamps: complete, in-scope observed hours can contain zero birds. Missing observation hours and documented weather closures are unknown. The user's passerine zero confirmation covers complete 2022–2025 surveys. Historical passerine absence is not zero evidence.

## Shared daily hurdle likelihood

For species-specific parameters and observed interval i on date d, let e_i denote hours observed, x_i the training-only weather/time GAM design, and g_d a shared daily multiplier:

```text
g_d ~ Gamma(shape=a, rate=a)
h_i = e_i exp(x_i alpha)
mu_i = e_i exp(x_i beta)
r_i = e_i kappa
P(Y_i > 0 | g_d) = 1 − exp(−g_d h_i)
Y_i | Y_i > 0, g_d ~ zero-truncated NB(mean=g_d mu_i, size=r_i)
E(Y_i | g_d) = [1 − exp(−g_d h_i)] g_d mu_i / [1 − NB(0; g_d mu_i, r_i)]
```

The gate and positive-count component share the daily multiplier and have separate coefficients. Both receive the fixed training-only GAM penalty. The episode term is absent. The Gamma shape a is borrowed from the matching training-only Gamma/flocks fit; kappa, alpha and beta are jointly optimized. Thus the daily shape and smoothing penalties are not jointly estimated under this hurdle likelihood.

For a whole-day gap, average conditional expectations over the Gamma prior. For a partial-day gap, average over the daily-state posterior obtained from retained counts. Zero-only retained counts yield `g_d | retained ~ Gamma(a, rate=a+sum h_retained)`. Zero-only training dates likewise have an exact marginal likelihood `(a/(a+sum h_i))^a`. Dates containing positive retained/training counts use numerical integration, whose order sensitivity is explicitly assessed.

Predictive simulations draw the coefficient vector once for all hours, draw a common daily state for each date, and sample occurrence and positive counts. Daily simulated counts sum those same hourly draws. The coefficient covariance uses marginal likelihood information plus penalties and is checked numerically. Its Gaussian approximation conditions on a, kappa and smoothing; it can produce implausible tails where positive-count rates are weakly constrained. Interval coverage, width and interval score must be assessed together.

## Mixed-scale likelihood bridge

The current exposure-scaled hurdle law above does not define a distribution consistent under arbitrary splitting of an interval. Step 5 introduces a separate canonical-hour process; it requires a refit before operational use.

For a full clock hour let p be its occurrence probability, mu its NB mean, r its NB size, and P0 the NB zero probability. Its probability-generating function is:

```text
G(z) = 1 − p + p [NB_PGF(z; mu,r) − P0] / (1 − P0)
NB_PGF(z; mu,r) = [1 + (mu/r)(1−z)]^(−r)
```

Observing fraction q of that clock hour binomially thins its canonical count, replacing z by `1−q+qz`. This preserves NB size rather than multiplying it by exposure, and changes the partial-hour occurrence probability consistently. An interval spanning different clock hours multiplies their conditional PGFs, preserving each hour's weather. Integer probabilities are extracted numerically; a shared Gamma daily state is integrated after multiplying likelihoods for the day's observed intervals. A coarse survey total is used intact, without allocating its birds to hours.

This bridge assumes constant within-hour intensity. Disjoint observations sharing one clock hour require joint multinomial allocation from the same latent hourly count. The present likelihood helper supports independent clock-hour sets; that joint likelihood and a full coherent-model refit remain outstanding. Historical scope and matched production assessment are also outstanding. No new production model has been selected.

## Stabilized and pooled candidate (12 October 2026)

The shared hourly likelihood now uses posterior-centered log-Gamma integration for positive dates, checked at orders 31 and 63. Exact zero-only formulas remain. Forward prior/zero-conditioned moments integrate the near-zero constant analytically and the residual under Gamma(shape+1), avoiding missing near-zero mass at large hazards. Flat retained-positive posterior draws use refined log-state CDF inversion.

For the pooled candidate, the positive coefficient penalty is `S + 24 X_centered' diag(exposure) X_centered / sum(exposure)`, with exposure-weighted centering. This shrinks positive log-rate variation toward a species baseline; it does not shrink the intercept. The gate penalty is unchanged. Daily shape and smoothing remain conditional rather than jointly estimated. The current acceptance status is in [GAP_FILL_PLAN.md](../GAP_FILL_PLAN.md).

## Constrained coherent mixed-scale refit

`fit_coherent_intervals.py` applies the canonical-hour law above and estimates `log h = X alpha_frozen + delta_gate0 + delta_gateRain log1p(rain)` and `log mu = X beta_frozen + delta_count0 + delta_countRain log1p(rain)`, penalizing the four delta coefficients with a standard-normal prior. Each held-out-year context uses its training-only GAM and pooled shared-state coefficients. NB size is fixed per canonical hour rather than scaled by the observed fraction; partial-hour counts are binomially thinned. Intact survey totals contribute their actual summed-count likelihood, integrated over the same daily state as other observations on that date.

The full GAM, shape and dispersion refit remains future work. Predictive intervals for this constrained refit condition on those frozen components and include only calibration coefficient, daily-state and count uncertainty. Constant intensity within each clock hour remains an assumption. Accepted recent inputs have no shared species-clock-hour components; future overlapping observations require joint allocation probabilities. Historical scope remains unverified and no historical absence zeros are fitted.

## Time-effect refit on expanded coverage

`fit_coherent_intervals.py --refit-time` estimates all coefficients of `s(tau)` and `ti(tau,doy)` separately for occurrence and positive counts, together with the gate/count intercept and rain corrections. Other training-only GAM effects, smoothing penalties, daily Gamma shape and NB size remain fixed. The old time contribution is removed from each offset before fitting the new coefficients; these are fitted time effects rather than added duplicates. Canonical-hour bases remain the original training bases, now estimated using actual mixed-scale coverage, including observed zeros outside civil daylight.

The positive-rate variance penalty is computed over actual training coverage, weighted by clock-hour fractions. It includes the cross term with the frozen seasonal/weather offset, so it penalizes variation in the complete positive log-rate rather than just the new time contribution. Held-out years contribute neither counts nor coverage weights to this penalty. No hard night/rain zero rule is imposed and intact survey counts are not allocated into hours.

The first assessment uses `--draws 0` to isolate point-prediction changes. These saved fits explicitly mark uncertainty unavailable, and omit interval columns. Old candidate intervals cannot be carried over to this model. Once the time specification passes point calibration and numerical checks, covariance and predictive uncertainty must be recomputed for the refitted coefficients before operational use.

The first coefficient-only time pilot retained a severe Cormorant night prediction despite improvement. `--extended-time` therefore replaces the old time bases with cubic regression splines whose civil-daylight support spans [-1,2], retaining denser knots inside [0,1]. It also rebuilds the time-by-season tensor using that support. Constraints and season bases use training rows only; no held-out counts or exposure weights enter fitting. Other GAM contributions are preserved after removing their old time terms. New time coefficients start at zero rather than an ill-conditioned projection from daytime-only data. Smoothing weights remain borrowed from the original training fits; their joint estimation is still outstanding.

The count convolution now separates exact zero mass from positive polynomial coefficients before FFT convolution. This prevents a dominant zero probability from numerically erasing rare positive counts. When the numerical NB singularity leaves no representable saddlepoint, radius-one coefficient extraction remains valid; small totals requiring inactive full hours use log-domain convolution. Direct two-hour probabilities and rare-event checks verify this path.
