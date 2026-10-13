# Weather in the trend model and on the Explore page: plan

Agreed with the user, 2026-10-13. Goal: make `RSW` (production's daily GAM plus daily weather
terms, no AR(1) process) the production model, and add a weather section to Explore showing how
each taxon's passage goes with the main weather variables. Interpretability first, accuracy second.

## Decisions

- **Weather is self-contained.** The ERA5 reanalysis at Défilé from the Open-Meteo archive
  (`models=era5`, the point of `LOCATION`), downloaded by `fetch_weather.py` into
  `data/weather/`. Nothing is read from the forecast repo (the research runs did, from its cache).
- **Every term in every taxon's model.** No selection of variables: the model carries the whole
  menu below, and Explore shows a taxon's effect only where it is clear (the display rule below).
  Taxa use the weather differently (soaring raptors, waterbirds, passerines); one set of terms,
  fitted per taxon, lets each show what it responds to. Never a per-taxon choice of terms.
- **Wind in the model as u and v, on the page as direction and speed.** Two linear terms in u and v
  are exactly "a preferred direction and an effect per m/s of wind from it"; a third term, the
  wind speed, says whether strong wind of any direction matters.
- **Fronts are in**: the 24-hour pressure change and the temperature anomaly.

## The terms

Each is a daily value, the time-of-day profile's weighted mean over the day's hours (the hours the
taxon flies), standardised on counted days in the fit; effects are reported back in physical units.

| theme       | term              | hourly value                                               |
| ----------- | ----------------- | ---------------------------------------------------------- |
| rain        | `rain`            | log(1 + mm in the hour)                                    |
| sun         | `sunshine`        | share of the hour with sunshine (ERA5 direct > 120 W/m²)   |
| thermals    | `boundary_layer`  | boundary-layer height (km), the depth of thermal mixing    |
| wind        | `wind_u`, `wind_v` | wind at 100 m toward the east and the north (m/s)         |
| wind        | `wind_speed`      | wind speed at 100 m (m/s)                                  |
| front       | `pressure_change` | sea-level pressure minus 24 hours earlier (hPa)            |
| front       | `temperature_anomaly` | 2 m temperature minus its 1993–2025 mean for the date and hour (°C) |

Low cloud and the rain hinge (above 1 mm) of `RSW` are dropped: low cloud overlaps sunshine, the
hinge is hard to explain. Not available in the archive's ERA5: CAPE, sensible heat flux.

## Tests

1. **Accuracy.** On the realistic masks (new inputs, five draws, ten core species): `P`, `RSW`
   and `W` (the terms above), with the downloaded weather. `W` should be no worse than `RSW`
   (season error, daily MAE, wet and dry days, both eras); it does not have to be better.
2. **Effects.** `W` fitted on all counted days of each taxon; each term's effect as a multiplier
   for a fixed physical contrast, with its 95% interval from the posterior draws:

   | term                  | contrast                                      |
   | --------------------- | --------------------------------------------- |
   | rain                  | 1 mm an hour all day against dry              |
   | sunshine              | a sunny day against an overcast one (1 vs 0)  |
   | boundary layer        | 500 m deeper                                  |
   | wind                  | 5 m/s from the preferred direction (and its direction) |
   | wind speed            | 5 m/s more, any direction                     |
   | pressure change       | 5 hPa rise in 24 hours                        |
   | temperature anomaly   | 3 °C colder than usual for the date           |

3. **Collinearity.** Correlations between the daily terms; where two are above 0.7 their separate
   effects are not shown apart (one combined statement instead).
4. **Stability.** The same effect in 1993–2013 and 2014–2025 (fitted apart), to flag a `caveat`.

## Display rule (to `reliability.py` when it goes to production)

- `show`: the 95% interval excludes no effect and the effect is at least ±10% for its contrast.
- `caveat`: shown, but the two eras disagree (opposite signs, or intervals that do not overlap).
- `hide`: otherwise.

Beside each effect, the counts: birds per counted hour on the counted days grouped by the term
(dry / light rain / rain; wind sectors), so a model effect always sits next to its evidence.
Wording: "associated with, at the same date", never "caused by".

## Then production

The weather block from `weather_design.py` into `trend.py` (no AR(1)), the weather table in the
cache key, a `trend` method version bump, a new `weather` block in the export (a contract change
with defileViz), drawn first in `explore_viewer.py`; tests; a `DECISIONS.md` entry that replaces
"Daily ERA5 weather at Défilé ... dropped for Explore".

## The broad panel (2026-10-13)

Asked by the user: every taxon, more weather, until patterns show. Guards fixed before looking: one
second menu chosen in one go (`W2`: `W` plus yesterday's rain, the 24-hour temperature change and
low cloud), odd years find and even years confirm, taxa grouped by family before looking
(`flight_groups.tsv`), every cell reported. `weather_panel.py` fits `W` and `W2` on production's own
daily frame of each of the 72 species with a trend (all, odd and even years);
`weather_patterns.py` makes the tables and the heat map (`weather_heatmap_W.png`).

- **Accuracy:** `W2` does not improve on `W` on the realistic masks (season 3.56% against 3.54%,
  daily MAE 17.6 against 17.4; differences -0.04 to +0.07 points and -0.26 to +0.59).
- **Rain** lowers passage in every group but the aerial insectivores (clearly in 23 of 32
  passerines, 9 of 14 soaring birds); replicated in 19 taxa.
- **Sunshine** raises the soaring birds' passage (10 of 14, median x2.2) and lowers some
  waterbirds' (Grey Heron, Great Egret, Eurasian Curlew).
- **Wind direction** is the most replicated term (24 taxa) and splits the groups: soaring birds
  pass with wind from N-NE (5-58°, the bise, a tailwind), passerines with wind from the SE (90-160°),
  aerial insectivores with wind from the W (244-270°, ahead of fronts). Strong wind of any
  direction lowers passage, except for aerial insectivores.
- **Fronts:** a pressure rise raises passerines (14 of 32) and aerial insectivores (6 of 7), which
  the ten core species did not show; a cold day raises soaring birds (7 of 14) and falcons (3 of 4)
  a little.
- **Deeper mixing** raises a few soaring birds (5 of 14) and lowers swifts and some passerines,
  who may then fly out of sight: a count's effect is passage and detection together.
- **Second menu:** yesterday's rain raises the soaring birds' passage (8 of 14, 5 replicated: the
  birds held back by rain pass the day after). Low cloud and the 24-hour temperature change mostly
  re-share effects with sunshine and the anomaly (sunshine x2.2 -> x2.6 for soaring birds with low
  cloud in) and are rarely replicated.

Proposal: production terms = `W` plus yesterday's rain; low cloud and the temperature change left
out. On the page, wind as a rose, with the contrasts capped where a taxon has few days in strong
wind (5 m/s from SW gives x71 for Alpine Swift: an extrapolation).

## Decided and mocked up (2026-10-13)

The user agreed to the proposal and the groups. `W3` = `W` plus yesterday's rain: on the
realistic masks season 3.53%, daily MAE 17.4 (against `W` -0.07 to +0.04 points and -0.33 to
+0.22; against `P` -1.24 to -0.35 points), the best arm and as fast as `P`. The mock-up of the
page section, `weather_mockup.py` (`logs/hierarchical/panel/weather_mockup.html`), from the panel's
`W3` fits:

- **Per species**, each term as a bar (the multiplier for its contrast, 95% interval, log scale
  x1/4 to x4) beside the counted days in three classes of the term (birds over the usual for the
  date and year, and the number of days); the terms not clear listed in one line.
- **Wind** as a rose: a 5 m/s wind from each of eight sides against calm (direction and speed
  together), a petal faded when not clear or with fewer than 20 counted days from that side, and
  one sentence with the preferred direction.
- **By group**: per term, the species shown with more or less passage; the mean preferred wind.
- **Classes** (to go to `reliability.py`): `show` when clear on all years and both halves (odd,
  even years) point the same way; `caveat` when a half points the other way; `hide` otherwise;
  a `confirmed` badge when each half is clear on its own.
