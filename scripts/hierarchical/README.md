# Hierarchical gap filling: daily passage, then its course within the day

A separate line of research from `scripts/research/` (the hourly rate model and its branches).
That work established two things this design starts from:

- Hourly weather improves wet-day fills a lot (core wet MAE −36 to −42% against the production
  model), because production has no weather and fills rainy days at the normal rate.
- Every hourly-rate variant reconstructs season totals worse than production (seven-day gaps,
  1993–2021: 15.3–15.9% against 13.27%, all ten core species worse). Lower daily error and better
  totals pulled apart whenever a daily process was fitted inside the hourly objective and filled
  from its mode.

So keep production's structure, which models the day's passage and gets totals right, and put
weather into it at the level it acts on. The final model is explained start to end in [MODEL.md](MODEL.md). Status and results go at the
bottom of this file;
settled calls go to `DECISIONS.md`.

## Model

For taxon s, year y, day d, solar hour h:

```text
daily level     Λ_yd  = exp( a + trend(y) + year(y) + season(d) + shift(y, d)     # production
                             + w_yd · β                                            # daily weather
                             + η_yd )                                              # daily process
intra-day       π_ydh = share of day d's passage in hour h, Σ_h π_ydh = 1
observation     y_obs ~ NegBin( mean = Λ_yd · c_obs , θ ),   c_obs = Σ_h π_ydh · covered(h)
gap fill        draws of (β, η) from the posterior, then production's gamma / flock draws
```

Everything above the weather line is `defile_passage.trend` unchanged. `c_obs` is production's
coverage when π is production's profile.

**What production already has.** Its `episode` block (25 B-spline knots per year, first-difference
plus ridge penalty) is already a latent daily-level process: a smoothed random walk with knots about
five days apart. `fill_draws` already draws its coefficients from the Laplace posterior, so gaps are
filled by conditional simulation, not from a mode. That is likely why its totals hold up. What it
lacks is weather, at either level. The design adds weather and changes the process one step at a time,
so the gain of each is measured.

## Steps

One change per step, each scored on the same masks, so the table of results shows what each change
gains or loses. A step is kept if it improves at least one primary score (below) and the other's
paired bootstrap interval includes zero or better; otherwise it is recorded and dropped.

| Step  | Change from the step before                                                |
| ----- | -------------------------------------------------------------------------- |
| `P`   | production refitted on the same retained data: the reference               |
| `R`   | + daily rain: the research hybrid's two terms (below)                      |
| `RS`  | + daily radiation and low cloud                                            |
| `RSW` | + daily wind u and v                                                       |
| `E`   | early ends: the hours after an early end get less than the profile's share |
| `D`   | daily AR(1) process in place of the episode knots                          |
| `I`   | intra-day level: profile with hourly weather                               |

Each step builds on the best kept one. The order follows the
[missingness audit](MISSINGNESS_AUDIT.md): rain and radiation are what make a day missing, so they
come first; wind does not, and comes after.

Daily weather terms are weighted by the time-of-day profile over the whole day (weights summing to
one), so they exist for days with no count and weight the hours that carry passage. `R` takes the
hybrid of [ORIGINAL_RAIN.md](../research/ORIGINAL_RAIN.md) unchanged, `R1 = Σ_h π_h log(1 + rain_h)`
and `R2 = Σ_h π_h max(log(1 + rain_h) − log 2, 0)`, so its saved result is the check that the step
is rebuilt correctly. `RS` adds `Σ_h π_h radiation_h` and `Σ_h π_h low_cloud_h`, `RSW` the same for
wind u and v. Each term is standardised on training days with a unit ridge, from the same ERA5
cache and alignment (value at t+1 for \[t, t+1)).

`E` was to correct early ends. It is not needed: with production's time-of-day profile (learned
from every day timed to the hour, 2014–2025), the early-end masks are filled without bias (−0.5%)
by every arm ([RESULTS.md](RESULTS.md)). The research benchmark learned its profile from 2022–2025
only, which under-filled 2014–2021 early ends by a third; this line follows production.

## Missing hours and days are not random

Counting stops, or never starts, for reasons tied to passage: rain, a day expected to be poor, an
observer leaving once migration dies down in the afternoon, and shorter counting days in early
years. This matters twice.

**Fitting.** Where missingness depends only on what the model contains (date, time of day,
weather), fitting on the counted data is unbiased for the fills, and putting weather in the model is
what makes rain gaps of this kind. Where it depends on the passage itself beyond those (leaving
because it is quiet), counted hours over-represent good passage: a partly counted day's level and
the late hours' share of the profile come out too high, and so do its fills. This cannot be fixed
by the model's fit alone; it has to be measured, and if it is large, modelled (for example a term
for days that end early).

**Assessment.** Calendar masks hide days at random, so they test mostly ordinary days and few of the
gaps that matter, and real gaps have no truth. Hence:

1. **Audit first (no fitting):** done, [MISSINGNESS_AUDIT.md](MISSINGNESS_AUDIT.md).

2. **Realistic masks**, drawn on counted days outside the lockbox, with known truth. Two kinds,
   each mimicking one mechanism the audit measured:

   - **Day masks** (1993–2025): hide whole counted days with the chance of a real missing day,
     fitted on the season record: era, month, weekend, daylight rain and radiation, and the local
     passage (counts of the days either side against the level of the days 2–7 away, as in the
     audit). Runs of two and more days follow the real run lengths. Since 1993–2013 holds most real
     missing days, the masks do too.
   - **Early-end masks** (2014–2025, days timed to the hour): end a full day early at an hour drawn
     from the real ends, with a chance that rises with rain in the three hours before and falls
     with the counts in those hours, both fitted on real early ends. Late-start masks the same way
     without the counts (the audit found none). The 1993–2013 days are one interval each and get no
     hour masks.

   The chance models set which days and hours are hidden; their intercepts are shifted so that each
   draw hides 10% of each era's eligible days and ends 30% of the eligible full days early, more
   than the real share (8% of days in 1993–2013, under 2% since), to have enough targets in every
   era. Five independent draws, scores averaged over them. These are the primary assessment; calendar masks stay as a second
   view. Gaps with no counting at all (storm closures) still have no truth, and no mask can supply
   it.

## Data and comparison

- Inputs: built from the defile-dataset release by `build_inputs.py` (`logs/hierarchical/inputs/`,
  ten core species, 1993–2025, survey counts with hourly components; `survey_complete` decides a
  zero and weather stops are zero passage), aggregated to production's daily frame (`y`, `c`,
  `extra`). Until 2026-10-13 the research's frozen inputs were used (`logs/history-episode/design/`,
  weather stops left out); the reference arms still replay those.
- Weather: hourly ERA5 at the site from the Open-Meteo archive, downloaded by `fetch_weather.py` into
  `data/raw/weather/` (since 2026-10-13; before, the forecast repo's cache, same values). The
  weather plan (`WEATHER_PLAN.md`): arm `W` of `run_steps.py`, its era split `We`, and the
  page's effects from fits on all counted days (`weather_effects.py`); the broad panel of every
  species with a trend (`weather_panel.py`, `weather_patterns.py`, groups in `flight_groups.tsv`) and the page mock-up (`weather_mockup.py`). No
  fitting code is shared with `scripts/research/`; production code is imported, not copied.
- **Reference arms**, scored with the same code on the same masks: the research's hourly weather
  mean (`weather_soaring`), the daily-passage AR(1) branch, and the hybrid (which is step `R`).
  On the calendar masks their saved predictions are re-scored with the scores below; on the
  realistic masks each is refitted with that mask's days held out. They are not steps of the
  ladder and are not tuned again.
- Calendar masks: the research's historical masks, phases of `(doy − 3 + 4 (year − 1993)) % 21`:
  one day (phase 0), three days (5–7), seven days (12–18), plus the recent seven-day masks
  (2022–2025).
- **Lockbox, set aside now:** historical phases 1–4 and 8–11 (two four-day masks). These dates were
  only ever training data, never scored. They are scored once, for the model chosen at the end, and
  never used to choose or tune. Realistic masks drawn for development avoid these dates.

## Scores

The goal is the best reconstruction of seasonal and daily totals. Ten core species, weighted
equally; realistic masks first, calendar masks second.

Primary:

1. **Season totals:** absolute relative error per species-year of the reconstructed total (counted
   plus filled), then averaged; signed bias beside it.
2. **Daily totals:** MAE of hidden daily totals; signed bias beside it.

Also reported: wet and dry days separately; 80% / 95% coverage of hidden daily, weekly and season
totals from the draws; per species, era and year; median species ratio; paired bootstrap over years
(historical) and weeks (recent), shared across species; fit time.

There are no pass/fail gates against production: the aim is the best model, and every step is
compared with the one before and with `P`. After the last kept step, the lockbox is scored once for
it and for `P`, and that result informs the decision on production.

## First steps

1. The missingness audit. Done.
2. Re-score the saved calendar-mask predictions of production, the hybrid, the hourly weather mean
   and the daily-passage branch with the scores above (point scores only: the saved predictions
   have no draws). No fitting.
3. The realistic masks: fit the two chance models, draw five masks, check that each matches its
   era's real share of missing days and hours, and against the real gaps in weather, month and
   time of day.
4. A numerical pilot on four species (Common Buzzard, Honey Buzzard, Great Cormorant, White Stork),
   no accuracy read:
   - `P` replays the saved production benchmark within Monte Carlo error;
   - `R` replays the saved hybrid;
   - draws: mean over draws of a hidden total matches the exact lognormal-NB expectation on
     synthetic data with known parameters;
   - fit time per taxon.
5. `P`, `R` and the reference arms on the realistic masks: the first row of the results table.

## Status

- 2026-10-13: design written.
- 2026-10-13: missingness audit done ([MISSINGNESS_AUDIT.md](MISSINGNESS_AUDIT.md)). Missing days
  follow rain and dark days (radiation as strong as rain) and sit in quiet spells; for soaring
  raptors, counting ends early once passage dies down.
- 2026-10-13: step order (radiation before wind, `E` for early ends) and realistic masks revised
  from the audit; old models added as reference arms.
- 2026-10-13: old models re-scored on the calendar masks; realistic masks drawn; pilot passed;
  `P` → `R` → `RS` → `RSW` → `D` all kept on the realistic masks (season error 4.25% → 3.58%,
  daily MAE 23.4 → 17.5), `E` not needed ([RESULTS.md](RESULTS.md)).
- 2026-10-13: `I` (hourly weather in the profile) no gain, dropped; `De` (early-era rain) not
  adopted; τ grid to 30 days; intervals calibrated (the apparent over-coverage is discreteness).
  Final model `D`. Lockbox scored once: daily MAE 29.2 → 26.6 (−3.9 to −1.2), wet days 26.1 → 17.4,
  season error 8.49% → 8.23% (−0.71 to +0.10 points). Production unchanged.
