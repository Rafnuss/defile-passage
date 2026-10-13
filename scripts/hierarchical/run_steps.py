"""Fit the ladder's daily steps on the realistic masks and predict what each mask hides.

Run from the repository root, after `fetch_weather.py` (the hourly ERA5 table): uv run --with 'pyarrow<20' python scripts/hierarchical/run_steps.py --arms P R RS RSW   >
logs/hierarchical/steps.log

Per species and mask draw: production's time-of-day profile from the retained hours timed to the
hour (2014-2025, as production; the research benchmark used 2022-2025 only), coverage of every
observation, the daily frame, then one fit per arm and `fill_draws` (with the hourly dispersion
`kappa`) for the hidden part of each day: a whole day under a day mask, the hours after the end
under an early-end mask.

Arms (README "Steps"): `P` production; `R` + rain (the research hybrid's two terms); `RS` + daily
radiation and low cloud; `RSW` + daily wind u and v; `W` the weather plan's terms
(`WEATHER_PLAN.md`) `We` (diagnostic: each `W` effect again for 1993-2013); `W2` `W` and the second menu; `W3` `W` and yesterday's rain (the proposal); `D` `RSW` with a daily AR(1) process in place
of the episode block (and `De`, a diagnostic: rain terms of their own for 1993-2013); `I` `D` with
the time-of-day profile moved by each hour's weather (`intraday_effect`), which changes the
coverage of every observation. Daily terms are the time-of-day profile's weighted means over the
whole solar day, standardised on the days with a count.
"""

import argparse
import os
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from common import CORE, LOGS, MASKS, ROOT, WEATHER_DIR, apply_mask, load_species, season_doy
from scipy.optimize import minimize
from weather_design import fit as fit_arm

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T

sys.path.insert(0, str(ROOT / "scripts/research"))
from compare_production import interval_slots, training_profile  # noqa: E402

ARMS = {
    "P": [],
    "R": ["log_rain", "rain_hinge"],
    "RS": ["log_rain", "rain_hinge", "radiation", "low_cloud"],
    "RSW": ["log_rain", "rain_hinge", "radiation", "low_cloud", "wind_u", "wind_v"],
    "D": ["log_rain", "rain_hinge", "radiation", "low_cloud", "wind_u", "wind_v"],
    "I": ["log_rain", "rain_hinge", "radiation", "low_cloud", "wind_u", "wind_v"],
    # Diagnostic, not a ladder step: the rain terms again for 1993-2013 alone (an era effect).
    "De": ["log_rain", "rain_hinge", "radiation", "low_cloud", "wind_u", "wind_v"]
    + ["log_rain_early", "rain_hinge_early"],
}
# `W`: the weather plan's terms (WEATHER_PLAN.md), every one in every taxon's model.
WEATHER_ONLY = ["sunshine", "boundary_layer", "wind_speed", "pressure_change"]
WEATHER_ONLY += ["temperature_anomaly"]  # hourly values used as they are (`hour_terms`)
ARMS["W"] = ["rain", "sunshine", "boundary_layer", "wind_u100", "wind_v100", "wind_speed"]
ARMS["W"] += ["pressure_change", "temperature_anomaly"]
# `W2`: `W` and the second menu, fixed before it was fitted (WEATHER_PLAN.md).
ARMS["W2"] = ARMS["W"] + ["rain_yesterday", "temperature_change", "low_cloud"]
# `W3`: the production proposal, `W` and yesterday's rain (WEATHER_PLAN.md, the broad panel).
ARMS["W3"] = ARMS["W"] + ["rain_yesterday"]
ARMS["We"] = ARMS["W"] + [f"{k}_early" for k in ARMS["W"]]  # diagnostic: an effect per era
DAILY_PROCESS = {"D", "I", "De"}  # arms with the daily AR(1) process in place of the episode block
INTRADAY = {"I"}  # arms whose time-of-day profile moves with the hour's weather
EARLY_ERA = 2014  # `De`: years before this get rain terms of their own
HOURLY_TERMS = ["log_rain", "rain_hinge", "radiation", "low_cloud", "wind_u", "wind_v"]
DRAWS = 500
COEF_DRAWS = 2000  # posterior draws for the weather coefficients' standard errors
SEED = 20261013
TIMED_FROM = 2014  # the profile is learned from the hours timed to the hour, as production
WET_MM_PER_HOUR = 0.1  # a hidden part is wet at this mean rain per hour (research convention)
CLIMATE_DAYS = 31  # the temperature anomaly's normal: the mean over this many days around the date


def hourly_weather() -> pd.DataFrame:
    """ERA5 at Defile per UTC hour [t, t+1), from `fetch_weather.py`: rain, radiation and sunshine
    accumulated over the hour (Open-Meteo's value at t+1), the others the mean of the hour's two
    ends. Wind u and v toward the east and north, at 10 m (`RSW`) and 100 m (`W`); the pressure
    and temperature changes over 24 hours; the temperature's departure from its mean for the date
    and hour; the rain of the same hour the day before."""
    raw = pd.concat([pd.read_csv(p) for p in sorted(WEATHER_DIR.glob("era5_*.csv"))])
    raw.index = pd.to_datetime(raw.pop("time"), utc=True)
    raw = raw.sort_index().asfreq("h")
    for height in ("10m", "100m"):
        speed, towards = raw[f"wind_speed_{height}"], np.deg2rad(raw[f"wind_direction_{height}"])
        raw[f"u_{height}"], raw[f"v_{height}"] = -speed * np.sin(towards), -speed * np.cos(towards)
    hour = raw.index.hour
    day = season_doy(pd.Series(raw.index.tz_localize(None))).to_numpy()
    mean = raw.temperature_2m.groupby([day, hour]).mean().unstack()  # (doy, hour)
    mean = pd.concat([mean.iloc[-CLIMATE_DAYS:], mean, mean.iloc[:CLIMATE_DAYS]])
    normal = mean.rolling(CLIMATE_DAYS, center=True).mean().iloc[CLIMATE_DAYS:-CLIMATE_DAYS]
    raw["temperature_anomaly"] = raw.temperature_2m.to_numpy() - normal.to_numpy()[day - 1, hour]
    raw["pressure_change"] = raw.pressure_msl - raw.pressure_msl.shift(24)
    raw["temperature_change"] = raw.temperature_2m - raw.temperature_2m.shift(24)
    ends = lambda column: (raw[column] + raw[column].shift(-1)) / 2  # noqa: E731
    w = pd.DataFrame(index=raw.index)
    w["rain_mm"] = raw.precipitation.shift(-1)
    w["radiation"] = raw.shortwave_radiation.shift(-1)
    w["sunshine"] = raw.sunshine_duration.shift(-1) / 3600
    w["low_cloud"] = ends("cloud_cover_low") / 100
    w["wind_u"], w["wind_v"] = ends("u_10m"), ends("v_10m")
    w["wind_u100"], w["wind_v100"] = ends("u_100m"), ends("v_100m")
    w["wind_speed"] = ends("wind_speed_100m")
    w["boundary_layer"] = ends("boundary_layer_height") / 1000
    w["pressure_change"] = ends("pressure_change")
    w["temperature_anomaly"] = ends("temperature_anomaly")
    w["temperature_change"] = ends("temperature_change")
    w["rain_yesterday"] = w.rain_mm.shift(24)  # the same hour of the day before
    return w.loc["1993-01-01":"2025-12-31"]


def slot_weather(dates: pd.Series, weather: pd.DataFrame) -> dict[str, np.ndarray]:
    """The hourly weather terms at each five-minute solar slot of each date, `(n_dates, SLOTS)`."""
    calendar = pd.DatetimeIndex(dates)
    noon = calendar + pd.Timedelta(hours=12)
    utc_noon = noon.tz_localize(E.TIMEZONE).tz_convert("UTC").tz_localize(None)
    zone = (noon - utc_noon) / pd.Timedelta(hours=1)
    shift = E.solar_shift(pd.Series(calendar)).to_numpy() - np.asarray(zone)
    midpoint = (np.arange(E.SLOTS) + 0.5) / E.STEPS_PER_HOUR
    times = calendar.to_numpy()[:, None] + pd.to_timedelta(
        (shift[:, None] + midpoint).ravel(), unit="h"
    ).to_numpy().reshape(len(calendar), E.SLOTS)
    times = pd.to_datetime(times.ravel(), utc=True).floor("h")
    return hour_terms(weather.reindex(times), (len(calendar), E.SLOTS))


def hour_terms(w: pd.DataFrame, shape) -> dict[str, np.ndarray]:
    """The weather terms of hours (`HOURLY_TERMS`), unstandardised, reshaped to `shape`."""
    log_rain = np.log1p(w.rain_mm.to_numpy())
    values = {
        "log_rain": log_rain,
        "rain_hinge": np.maximum(log_rain - np.log(2), 0),
        "radiation": w.radiation.to_numpy(),
        "low_cloud": w.low_cloud.to_numpy(),
        "wind_u": w.wind_u.to_numpy(),
        "wind_v": w.wind_v.to_numpy(),
    }
    values |= {
        "rain": log_rain,
        "rain_yesterday": np.log1p(w.rain_yesterday.to_numpy()),
        "temperature_change": w.temperature_change.to_numpy(),
        "wind_u100": w.wind_u100.to_numpy(),
        "wind_v100": w.wind_v100.to_numpy(),
        **{k: w[k].to_numpy() for k in WEATHER_ONLY},
    }
    return {k: v.reshape(shape) for k, v in values.items()}


def daily_terms(frame: pd.DataFrame, profile: np.ndarray, weather: pd.DataFrame) -> pd.DataFrame:
    """Profile-weighted daily weather of every modelled day (counted or not), unstandardised."""
    weights = profile[np.clip(frame.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
    assert np.allclose(weights.sum(axis=1), 1)
    slots = slot_weather(frame.date, weather)
    out = pd.DataFrame({k: (weights * v).sum(axis=1) for k, v in slots.items()})
    out.index = pd.MultiIndex.from_frame(frame[["year", "doy"]])
    return out


def intraday_effect(
    sample: pd.DataFrame, weather: pd.DataFrame
) -> tuple[np.ndarray, pd.Series, pd.Series]:
    """Step `I`: how the hour's weather moves passage within the day.

    On the retained hours timed to the hour, a day's birds are multinomial over its counted hours
    with shares proportional to `c_h exp(x_h . gamma)`: `c_h` the hour's share of the day under the
    time-of-day profile, `x_h` the hour's standardised weather (`HOURLY_TERMS`). The day's level
    cancels, so `gamma` only moves passage between the hours of a day. Unit ridge, as the daily
    terms. Returns `gamma` and the standardisation (mean, sd).
    """
    w = hour_terms(weather.reindex(pd.to_datetime(sample.slot_start, utc=True)), (len(sample),))
    X = pd.DataFrame(w, index=sample.index)[HOURLY_TERMS]
    mean, sd = X.mean(), X.std()
    X = ((X - mean) / sd).to_numpy()
    day = pd.factorize(sample.date)[0]
    y, logc = sample["count"].to_numpy(float), np.log(sample.c.to_numpy() + 1e-12)
    total = np.bincount(day, y)
    keep = (total > 0)[day] & (np.bincount(day)[day] >= 2) & (sample.c.to_numpy() > 0)
    X, y, logc, day = X[keep], y[keep], logc[keep], pd.factorize(day[keep])[0]
    total = np.bincount(day, y)

    def objective(g):
        eta = logc + X @ g
        top = np.full(total.size, -np.inf)
        np.maximum.at(top, day, eta)
        e = np.exp(eta - top[day])
        norm = np.bincount(day, e)
        p = e / norm[day]
        ll = (y * np.log(p + 1e-300)).sum() - 0.5 * g @ g
        grad = X.T @ (y - total[day] * p) - g
        return -ll, -grad

    gamma = minimize(objective, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B").x
    return gamma, mean, sd


def intraday_profile(
    dates: pd.Series, profile: np.ndarray, weather: pd.DataFrame, gamma, mean, sd
) -> np.ndarray:
    """Each date's time-of-day profile moved by its hours' weather, `(n_dates, SLOTS)`, summing to
    one over the day."""
    base = profile[
        np.clip(T.season_day(pd.DatetimeIndex(dates)), *P.PROFILE_DOY) - P.PROFILE_DOY[0]
    ]
    slots = slot_weather(dates, weather)
    eta = sum(g * (slots[k] - mean[k]) / sd[k] for k, g in zip(HOURLY_TERMS, gamma))
    moved = base * np.exp(eta - eta.max(axis=1, keepdims=True))
    return moved / moved.sum(axis=1, keepdims=True)


def kappa_of(train: pd.DataFrame, slots: np.ndarray, profile: np.ndarray) -> float:
    """Production's hourly dispersion from the retained observations (as the benchmark)."""
    midpoint = E.to_local(train.start + (train.end - train.start) / 2)
    train = train.assign(
        hour=np.floor(
            (midpoint - midpoint.dt.normalize()) / pd.Timedelta(hours=1)
            - E.solar_shift(train.date)
        ).astype(int)
    )
    hourly = train.groupby(["date", "hour"], as_index=False)["count"].sum()
    daily = train.groupby("date", as_index=False)["count"].sum().assign(timed=1.0)
    by_date = pd.Series(range(len(train)), index=train.date).groupby(level=0).indices
    effort = pd.DataFrame(
        {
            "date": list(by_date),
            "state": "counted",
            "slots": [slots[rows].sum(axis=0) for rows in by_date.values()],
        }
    )
    return T.hour_dispersion(daily, hourly, effort, profile)


def species_slots(species: str, parts: pd.DataFrame) -> np.ndarray:
    """`interval_slots` of `parts`, cached in `logs/` (recomputed when the parts change)."""
    cache = LOGS / "cache" / f"{species.replace(' ', '_')}_slots.npy"
    cache.parent.mkdir(exist_ok=True)
    if cache.exists():
        slots = np.load(cache)
        if len(slots) == len(parts):
            return slots
    slots = interval_slots(parts)
    part = cache.with_suffix(f".{os.getpid()}.npy")  # written whole, then moved: jobs run in parallel
    np.save(part, slots)
    os.replace(part, cache)
    return slots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", nargs="+", default=list(ARMS))
    parser.add_argument("--species", nargs="+", default=list(CORE))
    parser.add_argument("--draws", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    parser.add_argument("--out", type=Path, default=LOGS / "steps")
    parser.add_argument("--masks", type=Path, default=MASKS, help="folder of draw<k>.csv")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    weather = hourly_weather()
    for species in args.species:
        obs, parts = load_species(species)
        slots = species_slots(species, parts)
        row_of = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
        obs_slots = np.zeros((len(obs), E.SLOTS))
        np.add.at(obs_slots, row_of, slots)
        years = np.arange(1993, 2026)
        doy_range = (int(parts.doy.min()), int(parts.doy.max()))
        calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
        calendar = calendar[E.in_window(pd.Series(calendar)).to_numpy()]
        doy = T.season_day(calendar)
        calendar = calendar[(doy >= doy_range[0]) & (doy <= doy_range[1])]
        truth = obs.groupby("year")["count"].sum()
        rain_hours = (
            parts.assign(
                rain=weather.rain_mm.reindex(pd.to_datetime(parts.slot_start, utc=True)).to_numpy()
                * parts.fraction
            )
            .groupby("observation_id")
            .rain.sum()
        )
        for draw in args.draws:
            mask = pd.read_csv(args.masks / f"draw{draw}.csv", parse_dates=["date"])
            mask["hide_from"] = pd.to_datetime(mask.hide_from, utc=True)
            hidden = apply_mask(obs, mask).to_numpy()
            timed = obs[
                ~hidden & obs.year.ge(TIMED_FROM).to_numpy() & obs.exposure_hours.le(1).to_numpy()
                & ~obs.weather_stop.to_numpy()
            ]
            sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
                timed[["observation_id", "count"]], on="observation_id"
            )
            sample = sample[~sample.observation_id.duplicated(keep=False)]  # one hour each
            sample["exposure_hours"] = sample.fraction
            profile = training_profile(sample)
            base_profile = profile[
                np.clip(T.season_day(pd.DatetimeIndex(obs.date)), *P.PROFILE_DOY)
                - P.PROFILE_DOY[0]
            ]
            c = (obs_slots * base_profile).sum(axis=1)
            obs_c = obs.assign(c=c)
            kappa = kappa_of(obs_c[~hidden], obs_slots[~hidden], profile)

            def build(c):
                """Daily frame, standardised daily terms and hidden targets for coverages `c`."""
                obs_c = obs.assign(c=c)
                day = obs_c[~hidden].groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
                frame = pd.DataFrame(
                    {"date": calendar, "year": calendar.year, "doy": T.season_day(calendar)}
                )
                frame = frame.join(day, on="date").fillna({"y": 0, "c": 0})
                low = frame.c.lt(T.MIN_COVERAGE)
                frame["extra"] = frame.y.where(low, 0)
                frame.loc[low, ["y", "c"]] = 0
                raw = daily_terms(frame, profile, weather)
                early = (frame.year < EARLY_ERA).to_numpy()
                raw["log_rain_early"] = raw.log_rain.where(early, 0)
                raw["rain_hinge_early"] = raw.rain_hinge.where(early, 0)
                counted = frame.c.gt(0).to_numpy()
                terms = (raw - raw[counted].mean()) / raw[counted].std()
                for k in ("log_rain_early", "rain_hinge_early"):  # zero outside the early era
                    terms[k] = (raw[k] - raw[k][counted & early].mean()).where(early, 0) / raw[k][
                        counted & early
                    ].std()
                # `We`: the early era's departure from each `W` effect, in the same units.
                for k in ARMS["W"]:
                    centred = (raw[k] - raw[k][counted & early].mean()).where(early, 0)
                    terms[f"{k}_early"] = centred / raw[k][counted].std()
                test = obs_c[hidden].assign(
                    rain=rain_hours.reindex(obs_c.observation_id[hidden]).to_numpy()
                )
                target = test.groupby("date").agg(
                    count=("count", "sum"),
                    hidden_c=("c", "sum"),
                    hours=("exposure_hours", "sum"),
                    rain=("rain", "sum"),
                )
                target["kind"] = np.where(
                    target.index.isin(mask.date[mask.kind.eq("day")]), "day", "end"
                )
                target["weather"] = np.where(
                    target.rain / target.hours >= WET_MM_PER_HOUR, "wet", "dry"
                )
                missing = frame.date.map(target.hidden_c).fillna(0).to_numpy()
                selected = frame.date.isin(target.index).to_numpy()
                return frame, terms, target, missing, selected, raw[counted].std()

            built = {False: build(c)}
            gamma = None
            if INTRADAY & set(args.arms):
                hourly = sample.merge(
                    obs_c[["observation_id", "c"]], on="observation_id", validate="one_to_one"
                )
                gamma, w_mean, w_sd = intraday_effect(hourly, weather)
                dates = pd.Series(obs.date.unique())
                moved = intraday_profile(dates, profile, weather, gamma, w_mean, w_sd)
                index = pd.Index(dates).get_indexer(obs.date)
                built[True] = build((obs_slots * moved[index]).sum(axis=1))
            for arm in args.arms:
                frame, terms, target, missing, selected, scale = built[arm in INTRADAY]
                started = perf_counter()
                fit = fit_arm(
                    frame,
                    years,
                    doy_range,
                    terms[ARMS[arm]] if ARMS[arm] else None,
                    ar1=arm in DAILY_PROCESS,
                )
                seconds = perf_counter() - started
                draws = T.fill_draws(
                    fit,
                    frame,
                    frame.c.to_numpy() + missing,
                    n=DRAWS,
                    seed=SEED + draw,
                    kappa=kappa,
                )
                missed = (draws - frame.y.to_numpy() - frame.extra.to_numpy())[:, selected]
                result = target.loc[frame.date[selected]].reset_index()
                result["predicted"] = missed.mean(axis=0)
                for q, name in zip(T.QUANTILES, ["q025", "q10", "q50", "q90", "q975"]):
                    result[name] = np.quantile(missed, q, axis=0)
                result = result.assign(
                    english_name=species, draw=draw, arm=arm, year=result.date.dt.year
                )
                # Season: the hidden part of each year, its draws' quantiles and the year's total.
                year_of = result.year.to_numpy()
                season = []
                for year in np.unique(year_of):
                    total = missed[:, year_of == year].sum(axis=1)
                    season.append(
                        {
                            "english_name": species,
                            "draw": draw,
                            "arm": arm,
                            "year": year,
                            "hidden_count": result["count"][year_of == year].sum(),
                            "predicted": total.mean(),
                            **{
                                name: np.quantile(total, q)
                                for q, name in zip(
                                    T.QUANTILES, ["q025", "q10", "q50", "q90", "q975"]
                                )
                            },
                            "observed_truth": truth.get(year, np.nan),
                        }
                    )
                columns = fit.design.columns_of("weather") if ARMS[arm] else slice(0, 0)
                weather_coef = dict(zip(ARMS[arm], fit.beta[columns]))
                spread = (
                    fit.draws(COEF_DRAWS, np.random.default_rng(SEED))[:, columns].std(axis=0)
                    if ARMS[arm]
                    else []
                )
                diagnostics = {
                    "english_name": species,
                    "draw": draw,
                    "arm": arm,
                    "seconds": seconds,
                    "theta": fit.theta,
                    "kappa": kappa,
                    "tau": fit.hyper.get("tau", np.nan),
                    **{f"beta_{k}": v for k, v in weather_coef.items()},
                    **{f"se_{k}": v for k, v in zip(ARMS[arm], spread)},
                    **{f"sd_{k}": v for k, v in scale.items() if k in ARMS[arm]},
                    **(
                        {f"gamma_{k}": g for k, g in zip(HOURLY_TERMS, gamma)}
                        if arm in INTRADAY
                        else {}
                    ),
                }
                stem = f"{species.replace(' ', '_')}_draw{draw}_{arm}"
                result.to_csv(args.out / f"{stem}_days.csv", index=False)
                pd.DataFrame(season).to_csv(args.out / f"{stem}_season.csv", index=False)
                pd.DataFrame([diagnostics]).to_csv(args.out / f"{stem}_fit.csv", index=False)
                print(
                    f"{species} draw {draw} {arm}: {seconds:.1f}s, theta {fit.theta:.2f}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
