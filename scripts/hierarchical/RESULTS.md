# Results

The ladder of the [design](README.md), scored as the README says, 2026-10-13. Commands are in each
script's docstring; outputs are under `logs/hierarchical/`.

## 1. The old models on the research's calendar masks

`rescore_calendar.py`: the saved point predictions, re-scored with this line's scores on the
targets every model shares (historical 1993–2021, one fold; recent 2022–2025, three folds). No
fitting. Species weighted equally; season error is the hidden part's error over the year's counted
total.

| model                                | historical season | bias  | daily MAE | recent season | bias  | daily MAE |
| ------------------------------------ | ----------------- | ----- | --------- | ------------- | ----- | --------- |
| production (`P`)                     | 12.9%             | −3.5% | 40.1      | 11.9%         | −0.3% | 46.9      |
| hybrid: production + rain (`R`)      | 13.3%             | −2.3% | 39.5      | 12.2%         | +1.4% | 44.5      |
| hourly weather mean                  | 16.0%             | −1.6% | 41.1      | 10.0%         | −0.3% | 42.5      |
| hourly weather mean, radiation/cloud | 15.8%             | −1.7% | 40.3      | 10.1%         | −0.2% | 42.1      |
| hourly weather + episode             | 15.7%             | −1.7% | 40.3      | 10.2%         | −1.4% | 41.7      |
| daily-passage AR(1)                  | 15.1%             | −7.2% | 37.9      | 12.3%         | −7.8% | 40.0      |

(7726 historical and 4534 recent targets shared by all six.) Against production, the hybrid's
season difference is +0.4 points historically (95%: −0.1 to +1.4) and its daily MAE −0.7 (−1.5 to
+0.2); on wet days it is far better (MAE 31.6 → 23.6), on dry days slightly worse (42.3 → 43.5).
The hourly models are 2–8 points worse on historical seasons and about 2 better on recent ones.
The daily-passage model has the lowest daily MAE and under-predicts by 7–8% of season totals and
19–23% of daily totals. The earlier conclusions hold on these masks; what changes is the masks.

## 2. Realistic masks

`realistic_masks.py`, from the [audit](MISSINGNESS_AUDIT.md). Five draws, each hiding 10% of the
eligible days of every era (about 245 days) and ending 30% of the eligible full days of 2014–2025
early (about 155 days). Day masks are chosen by the fitted chance of a real missing day (rain,
radiation, era, month, weekend, the day before missing); early ends by the fitted hazard of a real
early end, which falls with the passage of the last three hours (−0.78 per SD).

| hidden days              | rain (mm) | >5 mm | radiation (W/m²) | November |
| ------------------------ | --------- | ----- | ---------------- | -------- |
| real missing days        | 10.7      | 65%   | 147              | 27%      |
| all eligible days        | 1.7       | 11%   | 275              | 10%      |
| masked days (five draws) | 4.0       | 27%   | 220              | 18%      |

The masks lean towards wet, dark and late days as real gaps do, but can only hide days that were
counted for at least six hours, so they are less extreme than real gaps. Masked early ends match
the real ones: 3.1 against 3.7 hours before dusk, quiet last hours (passage index −0.18 against
−0.15). The local passage of the days either side of a day did not predict a real missing day
once weather and runs were in the model (−0.005 per SD), so it plays no part in the day masks.

## 3. Numerical pilot

`pilot_replay.py`: `P` and `R` rebuilt here, run on the research's own masks with its data and its
point prediction, replay the saved production and hybrid to within 2·10⁻⁶ of their totals (eight
species-tasks). `fill_draws`' mean, used for scoring here, matches the same expectation within
Monte Carlo error (−3% to +1%). On a synthetic frame with known parameters, θ is recovered (2.05
for 2) and the draws' hidden total is 1.003 of its expectation.

## 4. The ladder on the realistic masks

`run_steps.py`, `score_steps.py`: ten core species, five draws, 19 555 hidden day-parts. Season
error is the absolute relative error of each species-year's hidden part over its counted total.
Intervals in brackets: 95% paired bootstrap over years of the difference.

| step                                | season error | season bias | daily MAE | daily bias | 80% / 95% daily | 80% season |
| ----------------------------------- | ------------ | ----------- | --------- | ---------- | --------------- | ---------- |
| `P` production                      | 4.25%        | +0.37%      | 23.4      | +17%       | 90% / 98%       | 90%        |
| `R` + rain                          | 3.71%        | −0.78%      | 19.2      | −5%        | 89% / 97%       | 88%        |
| `RS` + radiation/cloud              | 3.71%        | −0.77%      | 18.3      | −7%        | 89% / 97%       | 87%        |
| `RSW` + wind                        | 3.63%        | −0.80%      | 17.9      | −8%        | 89% / 98%       | 87%        |
| `D` daily AR(1)                     | 3.61%        | −0.89%      | 17.5      | −9%        | 89% / 98%       | 88%        |
| `H` hourly weather mean (reference) | 4.19%        | −0.22%      | 20.6      | +2%        | —               | —          |

- **`R` is kept.** Season error −0.54 points against `P` (−1.09 to −0.21), daily MAE −4.2 (−5.4 to
  −2.8). The gain is on wet days (MAE 30.2 → 20.0; `P` over-fills them by 65%) and on 2014–2025
  (season 5.3% → 4.1%); dry days are unchanged.
- **`RS` is kept.** Daily MAE −0.9 against `R` (−1.3 to −0.4), season unchanged (−0.07 to +0.06
  points).
- **`RSW` is kept.** Season −0.08 points against `RS` (−0.14 to −0.01), daily MAE −0.4 (−0.9 to
  −0.01).
- **`E` is dropped as unneeded.** With production's profile every arm fills the early-end masks
  without bias (−0.5% to −1.9% of their birds). The research benchmark's profile (2022–2025 only)
  had under-filled them by a third in 2014–2021; the first run here used it and found −23%.
- **The hourly weather mean (`H`)** is between `P` and `R`: season 4.19% (against `P` −0.46 to
  +0.29 points), daily MAE 20.6. It over-fills the early ends by 22–26%.
- **The daily-passage AR(1) (`A`)**, on the 44 of 50 fits that pass its own convergence checks, ties
  with `RSW`: season 3.69% against 3.68%, daily MAE 17.8 against 18.0 (differences −0.13 to +0.17
  points and −0.7 to +0.2), with a lower bias (season −0.13 to −0.48 points against `RSW`) and no
  intervals.

The 80% interval of a hidden day holds its count 89–90% of the time; this is discreteness, not
width (section 8).

Season error by species (`P` → `D`): nine of ten improve, Grey Heron holds (6.0% → 6.0%); the
largest gains are Common Buzzard 3.8% → 2.4%, Red Kite 3.4% → 2.1%, Sparrowhawk 3.3% → 2.3%,
Great Cormorant 3.1% → 2.3%, Black Kite 3.3% → 2.6%.

Median coefficients per SD of the daily term (`RSW`): rain −0.22 and above 1 mm +0.06, radiation
+0.12, low cloud +0.08, wind u −0.04, wind v −0.20 (a north wind, v < 0, raises passage).

### A watch point: the weather effect differs by era

On the 1993–2013 day masks the weather steps under-fill wet days (`R` −32% of their birds, `D`
−31%, `P` +18%), while on 2014–2025 they still over-fill them (`R` +33%, `D` +21%, `P` +144%). One rain coefficient for
all years splits the difference. An era-specific rain effect would score better on these masks,
but it may be learning the preferential sampling the audit found: a wet notebook day was counted
for six hours or more mostly when birds were flying, so the counted wet days of those years show a
weak rain effect that the real, uncounted wet days would not. The masks can only hide counted
days, so they cannot tell the two apart; the decision needs that caveat.

## 5. Step `D`: a daily AR(1) process in place of the episode knots

`D` is `RSW` with one value per window day and year, a stationary AR(1) prior centred over each
year, its variance by Fellner–Schall and its correlation `exp(−1/τ)` by the Laplace marginal
likelihood over τ = 2, 4, 7, 14, 21, 30 days (`weather_design.py`). Nothing is chosen on held-out
counts. (A first run with τ up to 14 chose the edge for four species; the grid was extended, and
the numbers here are from the extended grid.)

| step  | season error | season bias | daily MAE | daily bias |
| ----- | ------------ | ----------- | --------- | ---------- |
| `RSW` | 3.63%        | −0.80%      | 17.9      | −8%        |
| `D`   | 3.61%        | −0.89%      | 17.5      | −9%        |

- **Kept.** Daily MAE −0.4 against `RSW` (−0.72 to −0.23), season error −0.02 points (−0.07 to
  +0.04). It gains on wet days (MAE 19.0 → 18.4) and on 1993–2013 (22.3 → 21.5).
- **It lowers the fills a little more.** Season bias −0.89% against −0.80% (difference −0.16 to
  −0.03 points): a daily process pulls a hidden day towards its neighbours, which around wet days
  are low too.
- **τ:** 7 days for the raptors (Common Buzzard, Red Kite, Honey Buzzard, Sparrowhawk, mostly
  Kestrel and Marsh Harrier), 14 for Black Kite and Great Cormorant, 14–21 for Grey Heron, 14–30
  for White Stork. The first grid (to 14) gave 3.58% and 17.45: the same within noise.
- **Cost:** about 2 minutes a fit with six τ (four processes sharing the machine) against 1.5 s.
- It matches the research's daily-passage model in accuracy (season 3.6% against 3.7%, daily MAE
  17.5 against 17.8, on the 44 fits that model completes) and keeps production's draws and
  intervals.

## 6. Step `I`: the time-of-day profile moved by the hour's weather

`I` is `D` with each day's profile `π_dh ∝ profile(doy, h) · exp(x_dh · γ)`, `x_dh` the hour's
standardised rain (log and above 1 mm), radiation, low cloud and wind; `γ` from the retained hours
timed to the hour (a multinomial of each day's birds over its counted hours, so the day's level
cancels), unit ridge. Every observation's coverage `c` then depends on its hours' weather.

Median `γ` per SD: rain −0.17 (and +0.05 above 1 mm), radiation +0.04, low cloud −0.02, wind u
0.00, wind v −0.25: within a day, birds pass in the dry hours and with the north wind.

**Dropped: no gain.** Against `D`, season error −0.06 to +0.05 points, daily MAE −0.24 to +0.22;
wet days 18.4 → 18.1 (−0.77 to +0.10), early ends unchanged. The daily weather terms and the daily
process already carry what the hour's weather adds.

## 7. Diagnostic `De`: rain terms of their own for 1993–2013

`De` is `D` with the two rain terms repeated for 1993–2013 only. Its early-era rain effect is
weaker (median +0.17 per SD on top of the shared −0.35), the modern one steeper (−0.35 against
−0.22).

Against `D`: season error −0.07 to +0.06 points, daily MAE −0.32 (−0.58 to −0.05), all of it in
2014–2025 (15.7 → 15.1); in 1993–2013 the daily MAE is not better (21.5 → 21.7). It lowers the
season bias of 2014–2025 (−0.30% → −0.68%).

**Not adopted, although it passes the keep rule on daily MAE.** It gains where the masks are blind:
it learns a weak rain effect for the early years from the wet days that were counted for six hours
or more, which the audit shows were the days birds flew. 88% of real missing days are in
1993–2013, mostly wet and uncounted; `De` would fill them with that weak effect, too high. `D`'s
shared effect is the safer estimate for them. A judgement, recorded as such.

## 8. Interval calibration

The 80% intervals looked too wide (89–90% coverage), but that is discreteness: most hidden day-parts
hold few birds, the 10% quantile is then 0, and a count of 0 is never below it (count below q10:
0.02% of days). The upper tail is calibrated: count above q90 on 10.6% of day-parts (target 10%),
above q97.5 on 2.4% (target 2.5%) for `D`; wet days 9.9%, dry 11.1%, early ends 12.2%. Nothing to
change. `score_steps.py` now reports each tail on its own.

## 9. Final model and lockbox

**Final: `D`.** Production's daily GAM (trend, year, season, shift) with six daily weather terms
(rain, rain above 1 mm, radiation, low cloud, wind u and v; profile-weighted over the day,
standardised, unit ridge) and a daily AR(1) process in place of the episode knots; production's
profile (all days timed to the hour), coverage, `kappa` and `fill_draws`.

**Lockbox, scored once** (`run_steps.py --masks logs/hierarchical/lockbox`; historical calendar
phases 1–4 and 8–11, 1993–2021, never scored or used before; 623 and 632 counted days hidden,
4 days in 21 each, all ten species):

|                  | season error          | season bias    | daily MAE    | daily bias | above q90 | 80% season |
| ---------------- | --------------------- | -------------- | ------------ | ---------- | --------- | ---------- |
| `P` production   | 8.49%                 | +0.07%         | 29.2         | −4%        | 9.7%      | 91%        |
| `D` final        | 8.23%                 | +0.49%         | 26.6         | −3%        | 9.4%      | 92%        |
| difference (95%) | −0.71 to +0.10 points | −0.19 to +1.05 | −3.9 to −1.2 |            |           |            |

- **Daily totals: confirmed.** Daily MAE −9% (26.6 against 29.2), on wet days −33% (17.4 against
  26.1, where production over-fills by 70%) and on dry days −4% (28.8 against 30.0).
- **Season totals: better on average, not established.** 8.23% against 8.49%, with an interval
  that includes zero; eight of ten species better, Red Kite (7.1% → 7.4%) and White Stork
  (12.1% → 13.2%) worse.
- Both are close to unbiased on season totals; the upper tail stays calibrated (count above q90 on
  9.4% of hidden days).

Season errors are larger here than on the realistic masks because a lockbox mask hides four days
in every 21 of every year (19% of the season) against 10% of days.
