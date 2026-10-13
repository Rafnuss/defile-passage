"""The day's weather at the count site, for the trend model's weather terms and the `weather` block.
Part of `defile_explore`.

Hourly ERA5 reanalysis at Défilé (`LOCATION`; plain ERA5, 0.25°) from the Open-Meteo archive,
downloaded by `fetch` into `<data dir>/weather/` (one file a year), and read by `hourly` as the UTC
hour [t, t + 1): rain, radiation and sunshine accumulated over the hour (Open-Meteo stamps them at
the hour's end), the others the mean of the hour's two ends. Nothing comes from the forecast repo.

A taxon's daily term is the time-of-day profile's weighted mean of the hourly values over the day
(`daily_terms`): the weather of the hours the taxon flies. The trend model takes them standardised
on its counted days (`standardise`; `trend.design` adds them as a `weather` block with a unit
prior). `TERMS`, in their own units:

- `rain`, `rain_yesterday`: log(1 + mm in the hour), and the same hour the day before;
- `sunshine`: the share of the hour with sunshine (ERA5 direct radiation above 120 W/m²);
- `boundary_layer`: boundary-layer height, km (the depth of thermal mixing);
- `wind_u`, `wind_v`, `wind_speed`: wind at 100 m towards the east and the north, and its speed,
  m/s: together a preferred direction and the effect of wind of any direction;
- `pressure_change`: sea-level pressure less 24 hours earlier, hPa;
- `temperature_anomaly`: 2 m temperature less its mean for the date and hour (1993-2025, a
  `CLIMATE_DAYS` window), °C.

Settled with the user on the hierarchical line's broad panel (`DECISIONS.md`, 2026-10-13; the
scripts in `scripts/hierarchical/`): low cloud and the 24-hour temperature change were tried and
left out. `weather_block` turns the fits into what the page draws: each term's effect for a fixed
contrast (`CONTRASTS`), its class (`reliability.weather_class`), the counted days in classes of the
term (`BINS`) and `counted`, the class on the contrast's side against the opposite one
(`CONTRAST_BIN`), and the wind as a rose (`SECTORS`), each side's counted days against calm days.
The counted days are compared as the fit sees them, a partial residual: their birds over what the
fit expects without that term (the date, the year, the episodes and the other weather kept), so
that a class's other weather (wet days are overcast too) is not read as its own effect.
"""

import json
import os
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from defile_explore import export as E
from defile_explore import reliability as Q
from defile_explore.profile import PROFILE_DOY

METHOD = "weather@1"
WEATHER_DIR = "weather"  # under the data dir
LOCATION = (46.117215, 5.914877)  # the count site
FIRST_YEAR = 1992  # one year before the first counts: the first days' 24-hour changes
URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = [
    "precipitation",
    "sunshine_duration",
    "boundary_layer_height",
    "temperature_2m",
    "pressure_msl",
    "wind_speed_100m",
    "wind_direction_100m",
]
FETCH_PAUSE = 15  # seconds between requests, for the free API's limits
CLIMATE_DAYS = 31
TERMS = [
    "rain",
    "rain_yesterday",
    "sunshine",
    "boundary_layer",
    "wind_u",
    "wind_v",
    "wind_speed",
    "pressure_change",
    "temperature_anomaly",
]
WIND = ("wind_u", "wind_v", "wind_speed")  # drawn together, as the rose
# Contrasts the effects are given for, in each term's own units (the page words them).
CONTRASTS = {
    "rain": np.log1p(1.0),  # 1 mm an hour all day, against a dry day
    "rain_yesterday": np.log1p(1.0),  # the same, the day before
    "sunshine": 1.0,  # a sunny day against an overcast one
    "boundary_layer": 0.5,  # mixing 500 m deeper
    "pressure_change": 5.0,  # 5 hPa higher than the day before
    "temperature_anomaly": -3.0,  # 3 °C colder than usual for the date
}
WIND_SPEED = 5.0  # m/s from each side of the rose, against calm
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]  # where the wind comes from
CALM = 2.0  # m/s: a day's mean wind below this has no side
# Classes of the counted days shown beside each effect: lower edges in the term's units, and names.
BINS = {
    "rain": ([0.05, np.log1p(0.5)], ["dry", "light", "wet"]),
    "rain_yesterday": ([0.05, np.log1p(0.5)], ["dry", "light", "wet"]),
    "sunshine": ([0.25, 0.75], ["overcast", "mixed", "sunny"]),
    "boundary_layer": ([0.4, 0.8], ["shallow", "medium", "deep"]),
    "pressure_change": ([-3.0, 3.0], ["falling", "steady", "rising"]),
    "temperature_anomaly": ([-2.0, 2.0], ["cold", "usual", "warm"]),
}
# The classes of counted days on the contrast's two sides, compared beside each effect.
CONTRAST_BIN = {
    "rain": ("wet", "dry"),
    "rain_yesterday": ("wet", "dry"),
    "sunshine": ("sunny", "overcast"),
    "boundary_layer": ("deep", "shallow"),
    "pressure_change": ("rising", "falling"),
    "temperature_anomaly": ("cold", "warm"),
}
COEF_DRAWS = 2000


# --- the data --------------------------------------------------------------


def fetch(data_dir: str, last_year: int) -> list[int]:
    """Download the years `FIRST_YEAR`..`last_year` not yet in `<data_dir>/weather/`, and the
    current calendar year every time, up to yesterday (ERA5 runs a few days behind); the years
    fetched. A year that cannot be fetched is reported and skipped: `trend.with_weather` refuses a
    modelled day without weather."""
    folder = os.path.join(data_dir, WEATHER_DIR)
    os.makedirs(folder, exist_ok=True)
    fetched = []
    for year in range(FIRST_YEAR, last_year + 1):
        path = os.path.join(folder, f"era5_{year}.csv")
        today = pd.Timestamp.now().normalize()
        if os.path.exists(path) and year < today.year:
            continue
        end = min(pd.Timestamp(f"{year}-12-31"), today - pd.Timedelta(days=1))
        query = {
            "latitude": LOCATION[0],
            "longitude": LOCATION[1],
            "start_date": f"{year}-01-01",
            "end_date": end.strftime("%Y-%m-%d"),
            "models": "era5",
            "timezone": "GMT",
            "wind_speed_unit": "ms",
            "hourly": ",".join(VARIABLES),
        }
        try:
            with urllib.request.urlopen(f"{URL}?{urllib.parse.urlencode(query)}", timeout=300) as r:
                frame = pd.DataFrame(json.load(r)["hourly"])
        except OSError as error:  # offline, or the archive not there yet: the fit says if needed
            print(f"Weather {year} not downloaded: {error}")
            continue
        frame["time"] = pd.to_datetime(frame["time"], utc=True)  # GMT
        frame.to_csv(path, index=False)
        fetched.append(year)
        time.sleep(FETCH_PAUSE)
    return fetched


def files_key(data_dir: str) -> str:
    """The weather files (names and sizes), for the shared stage's cache key."""
    folder = os.path.join(data_dir, WEATHER_DIR)
    if not os.path.isdir(folder):
        return ""
    return ",".join(
        f"{f}:{os.path.getsize(os.path.join(folder, f))}" for f in sorted(os.listdir(folder))
    )


def hourly(data_dir: str) -> pd.DataFrame:
    """The hourly terms (`TERMS`, own units) per UTC hour [t, t + 1), indexed by its start, on
    the days of the profile's season (`profile.PROFILE_DOY`); empty without weather files."""
    folder = os.path.join(data_dir, WEATHER_DIR)
    paths = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    if not paths:
        return pd.DataFrame(columns=TERMS)
    raw = pd.concat(pd.read_csv(os.path.join(folder, p)) for p in paths)
    raw.index = pd.to_datetime(raw.pop("time"), utc=True, format="ISO8601")
    raw = raw.sort_index().asfreq("h")
    towards = np.deg2rad(raw.wind_direction_100m)
    raw["u"] = -raw.wind_speed_100m * np.sin(towards)
    raw["v"] = -raw.wind_speed_100m * np.cos(towards)
    hour = raw.index.hour.to_numpy()
    day = season_doy(raw.index)
    climate = raw.temperature_2m[raw.index.year > FIRST_YEAR]
    mean = climate.groupby([season_doy(climate.index), climate.index.hour]).mean().unstack()
    mean = pd.concat([mean.iloc[-CLIMATE_DAYS:], mean, mean.iloc[:CLIMATE_DAYS]])
    normal = mean.rolling(CLIMATE_DAYS, center=True).mean().iloc[CLIMATE_DAYS:-CLIMATE_DAYS]
    raw["anomaly"] = raw.temperature_2m.to_numpy() - normal.to_numpy()[day - 1, hour]
    raw["change"] = raw.pressure_msl - raw.pressure_msl.shift(24)

    def ends(column):
        return (raw[column] + raw[column].shift(-1)) / 2

    rain = np.log1p(raw.precipitation.shift(-1))
    w = pd.DataFrame(
        {
            "rain": rain,
            "rain_yesterday": rain.shift(24),
            "sunshine": raw.sunshine_duration.shift(-1) / 3600,
            "boundary_layer": ends("boundary_layer_height") / 1000,
            "wind_u": ends("u"),
            "wind_v": ends("v"),
            "wind_speed": ends("wind_speed_100m"),
            "pressure_change": ends("change"),
            "temperature_anomaly": ends("anomaly"),
        },
        index=raw.index,
    )
    keep = (day >= PROFILE_DOY[0] - 1) & (day <= PROFILE_DOY[1] + 1) & (raw.index.year > FIRST_YEAR)
    return w[keep].astype("float32")


def season_doy(times) -> np.ndarray:
    """Day of the year on a non-leap calendar (`trend.season_day`, for UTC times)."""
    t = pd.DatetimeIndex(times)
    return (t.dayofyear - (t.is_leap_year & (t.month > 2))).to_numpy()


def daily_terms(dates: pd.Series, doy: np.ndarray, profile: np.ndarray, weather: pd.DataFrame):
    """Each date's terms (`TERMS`, own units): the time-of-day profile's weighted mean of the hourly
    terms over the day's solar slots. `doy`: the dates' season days (`trend.season_day`)."""
    calendar = pd.DatetimeIndex(dates)
    noon = calendar + pd.Timedelta(hours=12)
    utc_noon = noon.tz_localize(E.TIMEZONE).tz_convert("UTC").tz_localize(None)
    zone = (noon - utc_noon) / pd.Timedelta(hours=1)
    shift = E.solar_shift(pd.Series(calendar)).to_numpy() - np.asarray(zone)  # solar -> UTC
    midpoint = (np.arange(E.SLOTS) + 0.5) / E.STEPS_PER_HOUR
    times = calendar.to_numpy()[:, None] + pd.to_timedelta(
        (shift[:, None] + midpoint).ravel(), unit="h"
    ).to_numpy().reshape(len(calendar), E.SLOTS)
    hours = pd.to_datetime(times.ravel(), utc=True).floor("h")
    weights = profile[np.clip(np.asarray(doy), *PROFILE_DOY) - PROFILE_DOY[0]]
    values = weather.reindex(hours)[TERMS].to_numpy(float).reshape(len(calendar), E.SLOTS, -1)
    out = pd.DataFrame(np.einsum("ds,dst->dt", weights, values), columns=TERMS)
    assert np.allclose(weights.sum(axis=1), 1)
    return out


def standardise(raw: pd.DataFrame, counted: np.ndarray) -> tuple[pd.DataFrame, pd.Series]:
    """The terms centred and scaled on the counted days, and the scale (sd, own units)."""
    mean, sd = raw[counted].mean(), raw[counted].std()
    return (raw - mean) / sd, sd


# --- the block --------------------------------------------------------------


def _per_unit(f, sd: pd.Series, n: int, seed: int) -> pd.DataFrame:
    """Draws of the weather coefficients per unit of each term, `(n, terms)`."""
    columns = f.design.columns_of("weather")
    draws = f.draws(n, np.random.default_rng(seed))[:, columns]
    return pd.DataFrame(draws / sd.to_numpy(), columns=sd.index)


def _summary(log_effect: np.ndarray) -> dict:
    lo, mid, hi = np.quantile(log_effect, [0.025, 0.5, 0.975])
    return {"effect": float(np.exp(mid)), "lo": float(np.exp(lo)), "hi": float(np.exp(hi))}


def _origin(b: pd.DataFrame) -> np.ndarray:
    """Where the wind that raises passage most comes from, degrees (the coefficients point to
    where it blows)."""
    return (np.degrees(np.arctan2(b.wind_u, b.wind_v)) + 180) % 360


def _circular_mean(degrees) -> float:
    return float(np.degrees(np.angle(np.exp(1j * np.radians(np.asarray(degrees))).mean())) % 360)


def _bins(values: np.ndarray, edges, names, y, expected) -> list[dict]:
    """Counted days per class: days, and their birds over `expected` (the fit without the term,
    scaled so that the average counted day is 1)."""
    k = np.searchsorted(edges, values, side="right")
    out = []
    for i, name in enumerate(names):
        sel = k == i
        if sel.any():
            out.append(
                {
                    "bin": name,
                    "days": int(sel.sum()),
                    "relative": float(y[sel].sum() / expected[sel].sum()),
                }
            )
    return out


def weather_block(fits: dict, frame: pd.DataFrame, raw: pd.DataFrame, sd: pd.Series, seed=0):
    """The `weather` block from the fits on all years and on odd and even years alone
    (`fits`: `{"all", "odd", "even"}` of `trend.fit`), the model frame and the raw terms of its
    days (own units) with their scale."""
    from defile_explore import trend as T  # trend imports this module

    draws = {
        half: _per_unit(f, sd, COEF_DRAWS, seed + i) for i, (half, f) in enumerate(fits.items())
    }
    f = fits["all"]
    counted = frame["c"].to_numpy() > 0
    y = frame["y"].to_numpy()[counted]
    # The fit at its mode, and each weather term's share of it (standardised terms)
    eta = T.eta_draws(f, frame["year"], frame["doy"], f.beta[None])[0]
    share = frame[T.WEATHER_COLUMNS].to_numpy() * f.beta[f.design.columns_of("weather")]
    share = pd.DataFrame(share, columns=TERMS)
    c = frame["c"].to_numpy()

    def expected(drop) -> np.ndarray:
        """The counted days' expected birds without the terms `drop` (everything else in the fit
        kept, episodes included), scaled so that the average counted day is 1."""
        e = (c * np.exp(eta - share[list(drop)].sum(axis=1).to_numpy()))[counted]
        return e * y.sum() / e.sum()

    effects = []
    for term, contrast in CONTRASTS.items():
        log = {half: d[term].to_numpy() * contrast for half, d in draws.items()}
        bins = _bins(raw[term].to_numpy()[counted], *BINS[term], y, expected([term]))
        by = {b["bin"]: b for b in bins}
        side, reference = CONTRAST_BIN[term]
        effects.append(
            {
                "term": term,
                "contrast": contrast,
                **_summary(log["all"]),
                **Q.weather_class(*(log[h] for h in ("all", "odd", "even"))),
                "bins": bins,
                "counted": (
                    {
                        "bin": side,
                        "reference": reference,
                        "days": by[side]["days"],
                        "reference_days": by[reference]["days"],
                        "relative": by[side]["relative"] / by[reference]["relative"],
                    }
                    if side in by and reference in by
                    else None
                ),
            }
        )
    rose = []
    e_wind = expected(WIND)
    speed = np.hypot(raw.wind_u, raw.wind_v).to_numpy()[counted]
    sector = (_origin(raw[["wind_u", "wind_v"]]).to_numpy()[counted] + 22.5) // 45
    side = np.where(speed < CALM, "calm", np.array(SECTORS)[sector.astype(int) % 8])
    calm = side == "calm"
    calm_ratio = y[calm].sum() / e_wind[calm].sum() if calm.any() else np.nan
    for k, name in enumerate(SECTORS):
        u, v = -np.sin(np.radians(45 * k)), -np.cos(np.radians(45 * k))
        log = {
            h: WIND_SPEED * (d.wind_u * u + d.wind_v * v + d.wind_speed).to_numpy()
            for h, d in draws.items()
        }
        sel = side == name
        cls = Q.weather_class(*(log[h] for h in ("all", "odd", "even")), days=int(sel.sum()))
        ratio = y[sel].sum() / e_wind[sel].sum() / calm_ratio if sel.any() else np.nan
        rose.append(
            {
                "from": name,
                **_summary(log["all"]),
                **cls,
                "days": int(sel.sum()),
                "relative": float(ratio) if np.isfinite(ratio) else None,
            }
        )
    origin = {h: _circular_mean(_origin(d)) for h, d in draws.items()}
    return {
        "method": METHOD,
        "source": "ERA5 (Open-Meteo archive)",
        "effects": effects,
        "wind": {
            "speed": WIND_SPEED,
            "origin": origin["all"],
            **Q.wind_class(origin["all"], origin["odd"], origin["even"], rose),
            "rose": rose,
        },
    }
