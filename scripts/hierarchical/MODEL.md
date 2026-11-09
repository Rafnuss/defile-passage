# The hierarchical gap-filling model, start to end

What the final model of this research line (`D`) is, how it is fitted, how it fills the hours and
days not counted, how it was assessed and what was tried on the way. The numbers are in
[RESULTS.md](RESULTS.md), the missingness evidence in [MISSINGNESS_AUDIT.md](MISSINGNESS_AUDIT.md)
and the plan in [README.md](README.md). The same account with typeset equations and figures from
the fits is built by `model_figures.py` (template `model_page.html`, written to
`logs/hierarchical/model_page.html`). Production (`defile_passage.trend`) is unchanged: `D` is
production's model with two changes, and every part it shares with production is imported, not
copied.

## 1. The problem

The Défilé de l'Écluse count records migrating birds hour by hour, but not every hour of every day
of the season. Days are missed (rain, a day expected to be poor, no observer), and counted days
start late and end early. To give a season total, a daily series or a passage date, the birds of
the hours not counted have to be estimated, with their uncertainty.

Two facts shape the model:

- **Gaps are not random.** Missing days follow rain and dark days; observers leave once passage
  dies down. A model that fills a gap with the typical passage of that date over-fills it.
- **Passage is lumpy at every scale.** Some days carry ten times their neighbours; within a day,
  birds come in flocks. Filling must keep both the day-to-day and the within-day variation.

The answer here is hierarchical: a model of each day's passage (its level, from season, year,
weather and a day-to-day process), and below it the day's course over the hours (the time-of-day
profile), through which the counted hours are read.

## 2. Data

**Species.** The ten core species of the research: Black Kite, Common Buzzard, Common Kestrel,
Eurasian Sparrowhawk, European Honey Buzzard, Red Kite, Western Marsh Harrier, White Stork, Great
Cormorant, Grey Heron. One model per species; nothing is shared between species.

**Counts and effort, 1993–2025.** Built from the defile-dataset release (`build_inputs.py`, from
`raw/dataset/`): for each species, every observation, an interval of counted time with its
count of birds in the main direction, and the observation's split into UTC hours. A Trektellen
survey is split into its hours when all of the species' birds in it are timed to one hour.

| era         | years     | what an observation is                                 |
| ----------- | --------- | ------------------------------------------------------ |
| notebook    | 1993–2013 | a day's counted interval and its total (about 8 hours) |
| spreadsheet | 2014–2016 | one hour                                               |
| naturalist  | 2017–2021 | one hour                                               |
| Trektellen  | 2022–2025 | one hour (birds timed to the minute, grouped by hour)  |

`survey_complete` decides a zero: a core species absent from a complete survey was counted at
zero. A **weather stop** is a complete survey in which no bird passed (counting impossible):
its coverage counts with zero birds, as in production (`DECISIONS.md`, 2026-10-09), and it is left
out of the time-of-day profile. Days without a record are unknown, never zeros. The season modelled is
production's window, 18 July to 18 November, cut to the days of the year the species' data span.

**Weather.** ERA5 at Défilé, hourly, from the forecast repository's cache (read as data, no code
shared): rain, surface solar radiation, low-cloud fraction, and the u (east) and v (north) wind
components at 10 m. An hour `[t, t+1)` takes the accumulations reported at `t+1` (rain in mm,
radiation in W/m²) and the mean of the instantaneous values at `t` and `t+1` (cloud, wind).

## 3. Notation

| symbol        | meaning                                                                |
| ------------- | ---------------------------------------------------------------------- |
| `y`, `d`, `s` | year, day of the season (non-leap day of year), five-minute solar slot |
| `π(d, s)`     | time-of-day profile: share of a day's passage in slot `s`, `Σ_s π = 1` |
| `c`           | coverage: the share of the day's expected passage in the time counted  |
| `Λ_yd`        | expected birds of day `d` of year `y` over the whole day (`c = 1`)     |
| `θ`           | negative binomial shape of a day's passage (small: very variable days) |
| `κ`           | within-day (flock) over-dispersion per full day of coverage            |
| `w_yd`        | the day's six daily weather terms                                      |
| `η_yd`        | the daily process (AR(1)) value of day `d` of year `y`                 |

## 4. The time-of-day profile and coverage

A day's counted hours carry a known share of its passage only once the course of passage over the
day is known. The profile `π(d, s)` is production's (`compare_production.training_profile`, the
production estimator applied to the retained observations):

1. **Samples.** Every retained observation timed to one hour (exposure at most one hour, inside one
   UTC hour), 2014–2025, as production uses every day timed to the hour. An hour counted for at
   least half its length, on a day with at least two such hours and birds, gives the ratio of its
   rate to the day's rate over those hours, weighted by the day's birds to the power 0.5.
2. **Surface.** The ratios are smoothed over day of season (1 July–2 December) and `τ`, the share
   of the day's light elapsed (0 at civil dawn, 1 at civil dusk), with 16 splines in `τ`: dawn and
   dusk keep their place as the days shorten.
3. **Profile.** The surface is read at each five-minute solar slot, times the slot's daylight
   fraction, and normalised to sum to one each day.

The **coverage** of an observation is `c_obs = Σ_s m_obs,s π(d, s)`, `m_obs,s` the fraction of slot
`s` it counted. A day's coverage is the sum over its retained observations. A day with `c < 0.1`
says nothing about its rate (a few minutes can hold one flock): it is not fitted, and its birds are
added to the day's total as they are (`extra`).

## 5. The daily model

For each species, the count `Y_yd` of the retained observations of day `d` of year `y`:

```text
Y_yd ~ NegBin( mean = c_yd · Λ_yd , shape θ )

log Λ_yd = a                                  intercept
         + trend(y)                           smooth trend over years
         + year(y)                            each year's own level
         + season(d)                          the season's shape
         + shift(y, d)                        a slow change of the season's timing or width
         + Σ_j β_j w_j,yd                     daily weather (six terms)
         + η_yd                               daily process: AR(1) over days, within each year
```

The negative binomial is a day's gamma-distributed rate seen through a Poisson count: day-to-day
variation beyond everything in `log Λ` is in `θ`.

**Smooth components** (production's, unchanged; P-splines: cubic B-splines with difference
penalties, each with its own smoothing parameter):

| component     | basis                                | penalty                                  |
| ------------- | ------------------------------------ | ---------------------------------------- |
| `trend(y)`    | 12 B-splines over the years          | second differences                       |
| `season(d)`   | 20 B-splines over the window's days  | second differences                       |
| `shift(y, d)` | tensor product, 6 (years) × 8 (days) | second differences along each axis (two) |
| `year(y)`     | one coefficient per year             | ridge (a random effect)                  |

Every smooth sums to zero over its grid (a centring constraint), so each level has one owner: the
intercept, then `year` for a year's level, and `trend` and `season` for the main effects of
`shift` (an interaction only). All coefficients also carry a tiny ridge (1e-4).

**Daily weather.** Six terms per day, each a profile-weighted mean over the whole solar day, so
that they exist for days with no count and weight the hours that carry passage:

```text
w_j,yd = Σ_s π(d, s) · f_j( weather of the UTC hour holding slot s )

f: log(1 + rain mm)            rain
   max(log(1 + rain) − log 2, 0)   rain above 1 mm in the hour (a second slope)
   radiation (W/m²)
   low-cloud fraction
   wind u, wind v (m/s)
```

Each is standardised on the days with a count (mean 0, sd 1) and has a fixed N(0, 1) prior: a
ridge, no smoothing parameter of its own. Median effects per sd (ten species, five mask draws):
rain −0.22, above 1 mm +0.06, radiation +0.13, low cloud +0.08, wind u −0.03, wind v −0.21 (a north
wind, v < 0, raises passage).

**The daily process `η`.** It replaces production's `episode` block (25 B-splines a year with
first-difference and ridge penalties, knots about five days apart). One value per window day and
year (about 124 a year), with a stationary AR(1) prior:

```text
η_y,d = ρ η_y,d−1 + ε,   sd(η) = σ,   ρ = exp(−1/τ)
prior precision (1/σ²) R(ρ),   R the unit-variance AR(1) precision (tridiagonal)
centred: Σ_d η_y,d = 0 within each year (Z' R Z on the k − 1 free values), so the year's level
stays with year(y)
```

Years are independent; the process restarts each season. It is what lets a hidden day borrow from
its neighbours: a gap in a run of good days is filled high, in a lull low.

## 6. Fitting

All coefficients `b` (about 100 dense, plus 33 blocks of about 123 daily values) are Gaussian a
priori given the hyperparameters: the smoothing parameters `λ` (season, trend, two shift, year,
daily), `θ` and `τ`.

1. **Posterior mode.** Penalised IRLS (Fisher scoring with step halving) for the negative binomial
   with log link, offset `log c`. The information matrix is solved by blocks: the dense columns,
   and one block per year for the daily process (production's `Factor`), so a fit costs
   `O(years · k³)`, not `O((years · k)³)`.
2. **Smoothing parameters.** Extended Fellner–Schall updates (Wood and Fasiolo 2017), a fixed point
   of the Laplace marginal likelihood: each `λ` is scaled by
   `(tr(Q⁻¹S) − tr(H⁻¹S)) / (b'Sb)`, the degrees of freedom its prior allows minus those the data
   use, over the wiggliness it is asked to explain. `σ²` of the daily process is one of them.
3. **`θ`.** Its maximum likelihood given the fitted means to start, then alternated with the
   smoothing parameters as the maximiser of the Laplace marginal likelihood (up to five rounds).
4. **`τ`.** The whole fit is run for τ = 2, 4, 7, 14, 21, 30 days and the one with the highest
   Laplace marginal likelihood is kept. Chosen: 7 days for the soaring raptors, 14 for Black Kite
   and Great Cormorant, 14–21 for Grey Heron, 14–30 for White Stork.
5. **Posterior.** `b ~ N(b̂, H⁻¹)` with `H` the penalised information; where a species is counted
   but never seen, the information is evaluated at no less than 0.1 birds a day, so the posterior
   does not become flat there (production's `MIN_RATE`).

No hyperparameter is chosen on held-out counts.

**Within-day dispersion `κ`.** Production's `hour_dispersion`: on days timed to the hour, given the
day's birds, the birds of its counted four-hour blocks are Dirichlet-multinomial with weights
`κ ×` the profile's share counted in each block; `κ` by maximum likelihood.

A fit takes about 1–2 minutes (six τ, a few cores), against 1.5 s for production.

## 7. Filling the gaps

For each posterior draw (1000 in production, 500 in the assessment):

```text
b*            ~ N(b̂, H⁻¹)                                coefficients
μ_yd          = exp(X_yd b*)                              expected birds over a full day
rate_yd       ~ Gamma(θ + Y_yd, θ/μ_yd + c_yd)            the day's rate given its counted birds
m_yd          = c_total − c_yd                            coverage not counted
passage       ~ Gamma(κ m_yd, κ / rate_yd)                its passage, with flocks (mean rate · m)
birds missed  ~ Poisson(passage)
day total     = Y_yd + extra_yd + birds missed
```

A day counted in part is filled from its own counted birds (the gamma posterior of its rate) as
much as from the model; a day not counted at all draws its rate from the model alone. The season
total of a year is the sum of its day totals in each draw; its mean and quantiles come from the
draws. In production `c_total = 1` (the whole day); in the assessment it is the coverage of the
hidden observations, whose counts are the truth.

## 8. Why the gaps can be filled this way

Filling from a model fitted to the counted hours is unbiased if the gaps depend only on what the
model contains (missing at random given the covariates). The audit tested this:

- **Missing days** depend on rain (odds ×1.9 per sd), radiation (×0.44 per sd), era, month and
  weekday. Rain and radiation are now in the model. Once they are, the passage of the neighbouring
  days no longer predicts a missing day.
- **Early ends** follow quiet hours (hazard −0.78 per sd of the last three hours' passage). The
  day's counted birds enter the fill through `rate | Y`, and with production's profile the hidden
  tails of early ends are filled without bias (−0.5% to −1.9% of their birds).
- **What the data cannot show:** a day never counted has no truth. Wet days of 1993–2013 that
  were counted for six hours or more were mostly days birds flew; the uncounted ones probably had
  fewer. This is why the rain effect is shared across eras (section 11).

## 9. Assessment

**Realistic masks** (`realistic_masks.py`): hide counted days and hours the way real gaps happen,
so their truth is known. Five draws.

- *Day masks*, 1993–2025: a logistic model of a real missing day (era, month, weekend, daylight
  rain and radiation, whether the day before is missing) fitted on every season day, applied to
  the days counted for six hours or more; its intercepts shifted so that each era hides 10% of
  them.
- *Early-end masks*, 2014–2025: a discrete-time hazard of a real early end (era, month, time of
  day, rain in the hour and the three before, the passage of the last three hours) on the
  afternoon hours of full days; shifted so that 30% of them end early.
- Days of the lockbox are never hidden.

**Scores**, ten species weighted equally, averaged over draws:

1. *Season totals:* `|Σ (predicted − counted) over the hidden part| / the year's counted total`,
   per species-year; and its signed mean (bias).
2. *Daily totals:* mean absolute error of the hidden part of each day; and the relative bias.
3. Also: wet and dry days, day and early-end masks, eras, calibration of the draws' tails.

Each step is compared with the step before and with production by a paired bootstrap over years
(all species and draws resampled together). **Keep rule:** a step is kept if it improves one of
the two primary scores and the other's interval includes zero or better.

**Lockbox:** the research's historical calendar phases 1–4 and 8–11 (two four-day masks in every
21 days, 1993–2021), set aside before any fit and scored once, for the final model and production.

## 10. Results

| step  | change                                    | season error | daily MAE | kept        |
| ----- | ----------------------------------------- | ------------ | --------- | ----------- |
| `P`   | production                                | 4.25%        | 23.4      | reference   |
| `R`   | + daily rain (two terms)                  | 3.71%        | 19.2      | yes         |
| `RS`  | + radiation and low cloud                 | 3.71%        | 18.3      | yes         |
| `RSW` | + wind u and v                            | 3.63%        | 17.9      | yes         |
| `D`   | daily AR(1) in place of the episode knots | 3.61%        | 17.5      | yes: final  |
| `I`   | hourly weather in the time-of-day profile | 3.60%        | 17.5      | no: no gain |

Production over-fills hidden wet days by 65%; `D` by −6%. Draws are calibrated in the upper tail
(count above the 90% quantile on 10.6% of hidden days, above 97.5% on 2.4%); the lower tail cannot
be read on counts that are mostly zero.

**Lockbox**, scored once:

|                | season error          | daily MAE    | wet days MAE | dry days MAE |
| -------------- | --------------------- | ------------ | ------------ | ------------ |
| production     | 8.49%                 | 29.2         | 26.1         | 30.0         |
| `D`            | 8.23%                 | 26.6         | 17.4         | 28.8         |
| difference 95% | −0.71 to +0.10 points | −3.9 to −1.2 |              |              |

Daily totals are confirmed better; season totals are better on average (eight species of ten) but
not established.

## 11. What was tried and not kept

- **An early-end correction (`E`).** Not needed: with production's profile, early ends are filled
  without bias. A profile learned from 2022–2025 only (the research benchmark's) under-filled the
  2014–2021 early ends by a third.
- **Hourly weather in the profile (`I`).** Within a day, birds do pass in the dry hours and with the
  north wind (`γ`: rain −0.17, wind v −0.25 per sd), but the daily terms and the daily process
  already carry it: no gain.
- **A rain effect of its own for 1993–2013 (`De`).** It gains on 2014–2025 days only, and would fill
  the real, uncounted wet days of 1993–2013 with a rain effect learned from the counted ones, which
  were selected for passage. Not adopted: a judgement, recorded in `DECISIONS.md`.
- **The research's hourly weather mean.** Season 4.19%, daily MAE 20.6 on the realistic masks;
  over-fills early ends by about a quarter.
- **The research's daily-passage AR(1).** As accurate as `D` (3.7%, 17.8) but biased lower, no
  intervals, and 6 of 50 fits fail its own convergence checks.
- **Production plus rain alone (the hybrid, `R`)** had been rejected on calendar masks, which hide
  mostly dry days; on realistic masks it is the largest single gain.

## 12. Limitations and open questions

- Real gaps without counting (storm closures, uncounted wet days) have no truth; the masks can only
  hide counted days, which are less extreme (27% of masked days over 5 mm of rain, against 65% of
  real missing days).
- The weather effect differs by era on the masks (1993–2013 wet days filled 31% low, 2014–2025 wet
  days 21% high); whether that is a real change or selection is not settled.
- Ten species only; passerines and pigeons were not part of this line.
- Adopting `D` in production changes the build time (1–2 minutes a taxon) and the meaning of the
  exported `episodes` (the daily process replaces the episode curves): both repositories would
  change together.

## 13. Reproduce

From the repository root (`logs/`, `raw/`, `interim/` and `output/` are generated; ERA5 needs `pyarrow`):

```bash
uv run --with 'pyarrow<20' python scripts/hierarchical/audit_missingness.py > logs/hierarchical/audit.log
uv run python scripts/hierarchical/realistic_masks.py > logs/hierarchical/masks.log
uv run python scripts/hierarchical/pilot_replay.py > logs/hierarchical/pilot.log
uv run --with 'pyarrow<20' python scripts/hierarchical/run_steps.py --arms P R RS RSW D I De > logs/hierarchical/steps.log
uv run python scripts/hierarchical/run_reference_hourly.py > logs/hierarchical/reference.log
uv run python scripts/hierarchical/run_reference_daily.py > logs/hierarchical/reference-daily.log
uv run python scripts/hierarchical/score_steps.py --references H De > logs/hierarchical/scores.log
uv run python scripts/hierarchical/rescore_calendar.py > logs/hierarchical/rescore.log
```

The lockbox (once): `run_steps.py --arms P D --draws 0 1 --masks logs/hierarchical/lockbox --out logs/hierarchical/lockbox-steps`, then `score_steps.py --steps logs/hierarchical/lockbox-steps --references`.

| file                   | role                                                             |
| ---------------------- | ---------------------------------------------------------------- |
| `common.py`            | paths, core species, lockbox phases, mask application            |
| `audit_missingness.py` | why days and hours are missing                                   |
| `realistic_masks.py`   | the masks                                                        |
| `weather_design.py`    | daily weather terms and the AR(1) block on production's design   |
| `run_steps.py`         | profile, coverage, weather, fits and fills per species and mask  |
| `score_steps.py`       | scores, bootstrap, keep rule                                     |
| `pilot_replay.py`      | numerical checks against the saved research results              |
| `rescore_calendar.py`  | the old models' saved predictions, re-scored                     |
| `run_reference_*.py`   | the research's hourly and daily-passage models on the same masks |
