# Missingness audit

Step 1 of the [design](README.md): why season days and daylight hours are missing, before any model
is fitted. `audit_missingness.py` writes the tables to `logs/hierarchical/audit/` and the log to
`logs/hierarchical/audit.log` (run 2026-10-13, 1993–2025).

Inputs: the release's surveys for effort (every era), the frozen historical counts (1993–2021) and
the release's Trektellen counts (2022–2025) for the ten core species, and the research's ERA5 cache
aligned as in `build_hourly_weather.py`. The season is 15 July to 15 November, cut to each year's
first and last counted day. A day is *counted* if any daylight hour was counted, *closed* if only a
documented weather stop covers it, *uncounted* otherwise. Intervals are 95% bootstrap intervals,
over years for days and over days for hours.

## 1. Missing days follow the weather and the era

| era                   | season days | counted | closed (documented) | uncounted | hours counted / daylight |
| --------------------- | ----------- | ------- | ------------------- | --------- | ------------------------ |
| notebook 1993–2013    | 2587        | 91.2%   | 0.8%                | 8.0%      | 7.8 / 13.6               |
| spreadsheet 2014–2016 | 366         | 95.4%   | 3.0%                | 1.6%      | 8.8 / 13.6               |
| naturalist 2017–2021  | 616         | 98.5%   | 0.6%                | 0.8%      | 10.2 / 13.6              |
| Trektellen 2022–2025  | 489         | 98.8%   | 0.8%                | 0.4%      | 11.8 / 13.6              |

Share of days missing by daylight rain: notebook 2.5% of dry days (\<0.5 mm), 8.7% at 0.5–5 mm,
32% above 5 mm; spreadsheet 0%, 2.8%, 25%; since 2017 under 0.5%, 0–0.8%, 6–7%. November is missed
most (19% of notebook days).

Odds of a missing day, all terms together (per standard deviation; era and month adjusted):

| term                        | odds ratio | 95%       |
| --------------------------- | ---------- | --------- |
| log rain (daylight total)   | 1.90       | 1.46–2.55 |
| share of daylight hours wet | 1.30       | 0.97–1.77 |
| mean radiation              | 0.44       | 0.27–0.61 |
| wind speed                  | 1.07       | 0.87–1.28 |
| low cloud                   | 1.02       | 0.87–1.23 |
| weekend (against a weekday) | 0.52       | 0.35–0.77 |

Rain and a dark day drive missing days; radiation matters as much as rain. Weekends are counted
more often in the notebook years (6.2% of weekend days missing, 9.8% of weekdays), a reason
unrelated to passage.

## 2. Missing hours: the ends of the day, and after rain

Counted days are cut at both ends, much more in early years:

| era         | dawn → first counted hour (dry day / >5 mm) | last counted hour → dusk (dry / >5 mm) |
| ----------- | ------------------------------------------- | -------------------------------------- |
| notebook    | 2.6 h / 3.2 h                               | 2.8 h / 4.9 h                          |
| spreadsheet | 1.5 h / 4.0 h                               | 2.4 h / 4.4 h                          |
| naturalist  | 1.1 h / 2.0 h                               | 1.5 h / 2.6 h                          |
| Trektellen  | 0.9 h / 1.0 h                               | 1.0 h / 1.0 h                          |

Inside the day (2014–2025, time of day, era and month adjusted), an hour is more often missing after
rain in the three hours before (odds 1.17 per SD, 1.12–1.23) than for rain in the hour itself (1.05,
1.00–1.11): counting stops once rain has set in and is slow to restart. Windier hours are counted
more (0.84, 0.81–0.88). Notebook days are one interval each, so they have no inner gaps to test.

## 3. Counting ends early when passage dies down (soaring raptors)

On days timed to the hour (2014–2025), the count of the last hour before an end at least two hours
before dusk, against its expectation: the three hours before it times the ratio of that hour to the
three before on days that go on, same species, era, month and clock hour. A late start (first hour
at least two hours after dawn, against the three hours after it) is the control: observers arriving
cannot know the passage before.

| species                 | early end | 95%       | early end, dry last hour | late start (control) |
| ----------------------- | --------- | --------- | ------------------------ | -------------------- |
| Common Buzzard          | 0.27      | 0.14–0.53 | 0.25                     | 0.85                 |
| Eurasian Sparrowhawk    | 0.51      | 0.30–0.85 | 0.54                     | 0.97                 |
| Red Kite                | 0.56      | 0.21–0.93 | 0.59                     | 1.10                 |
| European Honey Buzzard  | 0.67      | 0.30–1.01 | 0.70                     | 1.53                 |
| Western Marsh Harrier   | 0.71      | 0.39–1.10 | 0.73                     | 1.86                 |
| Black Kite              | 0.87      | 0.40–1.46 | 0.90                     | 0.65                 |
| Common Kestrel          | 0.87      | 0.48–2.29 | 0.84                     | 1.47                 |
| Great Cormorant         | 1.10      | 0.52–2.29 | 1.37                     | 1.38                 |
| Grey Heron              | 1.29      | 0.09–245  | 0.70                     | 0.61                 |
| White Stork             | 1.92      | 0.51–5.18 | 2.43                     | 5.73                 |
| ten species (geometric) | 0.77      | 0.54–1.45 | 0.77                     | 1.28                 |

For the raptors that soar on thermals, the last hour before an early end holds a quarter to two
thirds of what the same hour holds on days that go on, also when that hour is dry; the late start
shows no such drop. Observers leave once passage dies down, or passage stops with the thermals and
they leave; either way the hours after an early end hold less than the time-of-day profile gives
them, and production fills them at the profile's level. Waterbirds and storks travel in a few
large flocks and give no clear answer either way.

## 4. Missing days sit in quiet spells

For each missing day, the counts of the days either side against their local level (counts per
counted hour over the days 2–7 away), compared with the same for counted days; species weighted
equally:

| missing days               | ratio | 95%       | days |
| -------------------------- | ----- | --------- | ---- |
| all                        | 0.78  | 0.61–0.95 | 185  |
| dry (\<0.5 mm daylight)    | 0.58  | 0.26–0.80 | 17   |
| wet                        | 0.82  | 0.64–1.00 | 168  |
| 1993–2013                  | 0.89  | 0.70–1.09 | 157  |
| 2014–2025                  | 0.34  | 0.20–0.45 | 28   |
| uncounted only (no record) | 0.72  | 0.57–0.85 | 152  |

Passage on the days around a missing day is about a fifth below its local level, more around dry
missing days and in recent years, when a day is rarely missed and then only on a poor one. Part of
this is weather lasting more than a day; the rest is days skipped when passage is expected to be
poor.

## What this means for the design

- **Weather explains most missing days and late hours, so it must be in the model.** Without it,
  production fills a wet or dark day at a normal day's level. Radiation predicts a missing day as
  strongly as rain: step `R` should carry rain, and radiation should come next, before wind.
- **Early ends are not ignorable for soaring raptors.** The profile gives the hours after an early
  end too much passage. The daily weather term cannot see this; options are a term for the counts
  in the hours before an early end, or a profile fitted on full days only, scored on the masks
  below.
- **Missing days are in quiet spells.** A daily process filled by conditional simulation (the
  episode block today, AR(1) in step `D`) pulls a missing day towards its neighbours, which are
  low; filling from season and weather alone would put it too high. This is a reason to keep the
  process, and to check that the fills of real gaps fall below their seasonal mean.
- **Realistic masks need both mechanisms.** Hide whole days with the chance fitted in section 1
  (weather, era, month, weekend), and end days early with a chance that rises when the hours before
  are quiet, as section 3 measured. Masks drawn at random over well-counted days miss both.
- **Most real gaps are in 1993–2013.** Since 2014 a day is rarely missed (28 days) but its hours
  are; the historical years dominate any day-level assessment.

Not tested here: whether these patterns remain once weather is in the model (that is the residual
check of step `R`), and the notebook years' early ends, which have no hourly counts.
