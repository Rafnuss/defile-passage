"""Numerical pilot: `P` and `R` rebuilt here replay the research's saved production and hybrid.

Run from the repository root:
uv run python scripts/hierarchical/pilot_replay.py > logs/hierarchical/pilot.log

On the research's own masks (historical fold 2 and recent fold 0, four species), with its data
subset and its point prediction (the posterior mean day rate over 500 coefficient draws, same
seed), the predictions must match the saved `original_replay` and `original_rain` to rounding. The
`fill_draws` mean used by `run_steps.py` must match the same expectation within Monte Carlo error.
Also checked: fill draws' mean on a synthetic frame with known parameters.
"""

import numpy as np
import pandas as pd
from common import LOGS, RESEARCH_DESIGN, ROOT
from run_steps import ARMS, daily_terms, hourly_weather, kappa_of
from weather_design import fit as fit_arm

from defile_passage import export as E
from defile_passage import profile as P
from defile_passage import trend as T

import sys  # isort: skip

sys.path.insert(0, str(ROOT / "scripts/research"))
from compare_production import interval_slots, training_profile  # noqa: E402

SPECIES = ("Common Buzzard", "European Honey Buzzard", "Great Cormorant", "White Stork")
SAVED = ROOT / "logs/original-rain/fits"
weather = hourly_weather()
rows = []
for species in SPECIES:
    for task, fold in (("historical", 2), ("recent", 0)):
        key = f"{task}__{species.replace(' ', '_')}_fold{fold}"
        obs = pd.read_csv(
            RESEARCH_DESIGN / f"{key}_observations.csv", parse_dates=["date"], low_memory=False
        )
        parts = pd.read_csv(
            RESEARCH_DESIGN / f"{key}_components.csv", parse_dates=["date"], low_memory=False
        )
        if task == "recent":
            obs = obs[obs.source.eq("recent")].copy()
            parts = parts[parts.observation_id.isin(obs.observation_id)].copy()
        for f in (obs, parts):
            f["start"] = pd.to_datetime(f.start, utc=True)
            f["end"] = pd.to_datetime(f.end, utc=True)
        timed = obs[~obs.hidden & obs.source.eq("recent") & obs.resolution.eq("hour")]
        sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
            timed[["observation_id", "count"]], on="observation_id", validate="one_to_one"
        )
        sample["exposure_hours"] = sample.fraction
        profile = training_profile(sample)
        slots = interval_slots(parts)
        parts["c"] = (
            slots * profile[np.clip(parts.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
        ).sum(axis=1)
        obs = obs.join(parts.groupby("observation_id").c.sum(), on="observation_id")
        daily = obs[~obs.hidden].groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
        years = np.arange(obs.year.min(), obs.year.max() + 1)
        calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
        calendar = calendar[E.in_window(pd.Series(calendar)).to_numpy()]
        frame = (
            pd.DataFrame(dict(date=calendar, year=calendar.year, doy=T.season_day(calendar)))
            .join(daily, on="date")
            .fillna({"y": 0, "c": 0})
        )
        low = frame.c.lt(T.MIN_COVERAGE)
        frame["extra"] = frame.y.where(low, 0)
        frame.loc[low, ["y", "c"]] = 0
        raw = daily_terms(frame, profile, weather)
        counted = frame.c.gt(0).to_numpy()
        # The research divides the rain terms by their standard deviation, without centring.
        terms = raw / raw[counted].std()
        hidden_c = obs[obs.hidden].groupby("date").c.sum()
        saved = pd.read_csv(SAVED / key / "assessment.csv", parse_dates=["date"])
        doy_range = (int(parts.doy.min()), int(parts.doy.max()))
        train = obs[~obs.hidden].reset_index(drop=True)
        train_slots = np.zeros((len(train), E.SLOTS))
        row = train.set_index("observation_id").index.get_indexer(parts.observation_id)
        np.add.at(train_slots, row[row >= 0], slots[row >= 0])
        kappa = kappa_of(train, train_slots, profile)
        for arm, column in (("P", "original_replay"), ("R", "original_rain")):
            fit = fit_arm(frame, years, doy_range, terms[ARMS[arm]] if ARMS[arm] else None)
            draw = fit.draws(500, np.random.default_rng(20261012 + fold))
            mu = np.exp(T.eta_draws(fit, frame.year, frame.doy, draw))
            rate = pd.Series(
                ((fit.theta + frame.y.to_numpy()) / (fit.theta / mu + frame.c.to_numpy())).mean(
                    axis=0
                ),
                index=frame.date,
            )
            exact = (hidden_c * rate.reindex(hidden_c.index)).reindex(saved.date).to_numpy()
            missing = frame.date.map(hidden_c).fillna(0).to_numpy()
            fill = T.fill_draws(fit, frame, frame.c + missing, n=4000, seed=1, kappa=kappa)
            fill = pd.Series(
                (fill - frame.y.to_numpy() - frame.extra.to_numpy()).mean(axis=0), index=frame.date
            ).reindex(saved.date)
            reference = saved[column].to_numpy()
            rows.append(
                {
                    "key": key,
                    "arm": arm,
                    "targets": len(saved),
                    "replay_max_abs": np.nanmax(abs(exact - reference)),
                    "replay_total_rel": np.nansum(exact - reference) / np.nansum(reference),
                    "fill_total_rel": np.nansum(fill - reference) / np.nansum(reference),
                    "rain_coef": (
                        fit.beta[fit.design.columns_of("weather")].round(3).tolist()
                        if ARMS[arm]
                        else []
                    ),
                }
            )
            print(rows[-1], flush=True)

# Synthetic: fill_draws' mean of a hidden day equals its negative binomial expectation ----------
rng = np.random.default_rng(3)
years = np.arange(2000, 2011)
dates = pd.date_range("2000-08-01", "2010-10-31")
dates = dates[(dates.month >= 8) & (dates.month <= 10)]
frame = pd.DataFrame({"date": dates, "year": dates.year, "doy": T.season_day(dates)})
mean = np.exp(3 + 1.5 * np.sin((frame.doy - 213) / 92 * np.pi))
theta = 2.0
frame["c"] = rng.uniform(0.3, 1, len(frame))
frame["y"] = rng.negative_binomial(theta, theta / (theta + mean * frame.c))
hide = rng.random(len(frame)) < 0.1
frame["extra"] = 0.0
truth_c = frame.c.copy()
frame.loc[hide, ["y", "c"]] = 0
fit = T.fit("gam", frame, years, (int(frame.doy.min()), int(frame.doy.max())))
fill = T.fill_draws(fit, frame, truth_c.where(hide, frame.c), n=4000, seed=2)
expected = (mean * truth_c)[hide]
print(
    "\nSynthetic: theta fitted {:.2f} (true {}), hidden total from draws / truth expectation {:.3f}".format(
        fit.theta, theta, fill[:, hide].mean(axis=0).sum() / expected.sum()
    )
)
pd.DataFrame(rows).to_csv(LOGS / "pilot_replay.csv", index=False)
