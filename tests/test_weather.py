"""The trend model's weather terms (`defile_explore.weather`) and their classes."""

import numpy as np
import pandas as pd

from defile_explore import export as E
from defile_explore import reliability as Q
from defile_explore import trend as T
from defile_explore import weather as W
from defile_explore.profile import PROFILE_DOY


def hourly_table(days: pd.DatetimeIndex, rng) -> pd.DataFrame:
    hours = pd.date_range(days[0] - pd.Timedelta(days=1), days[-1] + pd.Timedelta(days=2),
                          freq="h", tz="UTC")  # fmt: skip
    return pd.DataFrame(rng.normal(size=(len(hours), len(W.TERMS))), index=hours, columns=W.TERMS)


def flat_profile() -> np.ndarray:
    p = np.zeros((PROFILE_DOY[1] - PROFILE_DOY[0] + 1, E.SLOTS))
    p[:, 8 * E.STEPS_PER_HOUR : 16 * E.STEPS_PER_HOUR] = 1.0
    return p / p.sum(axis=1, keepdims=True)


def test_daily_terms_are_the_profile_weighted_mean():
    days = pd.date_range("2020-09-01", "2020-09-03")
    weather = hourly_table(days, np.random.default_rng(0))
    weather[:] = 0.0
    weather["rain"] = 2.0  # constant: the mean is the value
    weather.loc[
        weather.index.hour < 3, "sunshine"
    ] = 1.0  # at night: the profile gives it no weight
    out = W.daily_terms(pd.Series(days), T.season_day(days), flat_profile(), weather)
    assert np.allclose(out["rain"], 2.0)
    assert np.allclose(out["sunshine"], 0.0)


def test_fit_recovers_a_weather_effect_and_the_smooth_leaves_it_out():
    rng = np.random.default_rng(1)
    years = np.arange(2010, 2020)
    dates = pd.DatetimeIndex([d for y in years for d in pd.date_range(f"{y}-08-01", f"{y}-10-31")])
    frame = pd.DataFrame({"date": dates, "year": dates.year, "doy": T.season_day(dates)})
    frame["c"] = 1.0
    terms = pd.DataFrame(rng.normal(size=(len(frame), len(W.TERMS))), columns=W.TERMS)
    season = np.exp(-(((frame["doy"] - 260) / 25) ** 2))
    mu = 200 * season * np.exp(-0.8 * terms["rain"])
    frame["y"] = rng.negative_binomial(5, 5 / (5 + mu)).astype(float)
    frame["extra"] = 0.0
    frame = frame.assign(**{c: terms[t].to_numpy() for c, t in zip(T.WEATHER_COLUMNS, W.TERMS)})
    doy_range = (int(frame["doy"].min()), int(frame["doy"].max()))
    f = T.fit("gam", frame, years, doy_range)
    beta = dict(zip(W.TERMS, f.beta[f.design.columns_of("weather")]))
    assert abs(beta["rain"] + 0.8) < 0.1
    assert abs(beta["sunshine"]) < 0.1
    # the smooth season is at the mean weather: no weather column reaches it
    curve = T.season_curve(f, 2015)
    assert np.isfinite(curve["mid"]).all()
    # the exported day-to-day curves: the weather apart from the episodes, together the full fit
    e = T.episode_curves(f, np.array([2015]))
    full = T.eta_draws(f, np.full(len(e["doy"]), 2015), e["doy"], f.beta[None])[0]
    together = np.log(e["base"]["2015"]) + e["weather"]["2015"] + e["episode"]["2015"]
    assert np.allclose(together, full, atol=0.05)
    assert np.std(e["weather"]["2015"]) > 0.3  # the rain, sd 0.8 on the log scale


def test_weather_class():
    rng = np.random.default_rng(2)
    strong = rng.normal(-0.5, 0.05, 2000)
    assert Q.weather_class(strong, strong, strong) == {"class": "show", "confirmed": True}
    weak_half = rng.normal(-0.1, 0.2, 2000)
    assert Q.weather_class(strong, strong, weak_half) == {"class": "show", "confirmed": False}
    assert Q.weather_class(strong, strong, -strong)["class"] == "caveat"
    tiny = rng.normal(-0.05, 0.005, 2000)  # clear but below `WEATHER_MIN_EFFECT`
    assert Q.weather_class(tiny, tiny, tiny)["class"] == "hide"
    assert Q.weather_class(strong, strong, strong, days=5)["class"] == "hide"
