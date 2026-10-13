"""Snapshot existing ERA5 predictors for a controlled hourly-rate weather screen."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("../defile-migration-forecast/data/weather/era5_hourly/location=Defile")
OUT = Path("logs/era5-features")
COLUMNS = ["total_precipitation", "surface_solar_radiation_downwards", "low_cloud_cover"]
OUT.mkdir(parents=True, exist_ok=True)
paths = [p for p in sorted(CACHE.glob("part-*.parquet")) if int(p.stem.split("-")[1]) >= 1990]
weather = pd.concat([pd.read_parquet(p, columns=["datetime", *COLUMNS]) for p in paths])
weather["slot_start"] = pd.to_datetime(weather.datetime, utc=True)
weather = weather.set_index("slot_start").sort_index()
assert (
    weather.index.is_unique
    and weather.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all()
)
# Accumulations at t+1 cover the slot [t, t+1); antecedent rain excludes that slot.
weather["rain_mm"] = weather.total_precipitation.shift(-1) * 1000
weather["rain_previous_24h_mm"] = weather.rain_mm.shift(1).rolling(24, min_periods=24).sum()
weather["radiation_w_m2"] = weather.surface_solar_radiation_downwards.shift(-1) / 3600
weather["low_cloud_fraction"] = (weather.low_cloud_cover + weather.low_cloud_cover.shift(-1)) / 2
weather = weather.loc[
    "1993":"2025", ["rain_mm", "rain_previous_24h_mm", "radiation_w_m2", "low_cloud_fraction"]
]
assert np.isfinite(weather.to_numpy()).all()
assert weather.rain_mm.ge(0).all() and weather.radiation_w_m2.ge(0).all()
assert weather.low_cloud_fraction.between(0, 1).all()
weather["log_previous_rain"] = np.log1p(weather.rain_previous_24h_mm)
weather["dry_previous_rain"] = weather.rain_mm.lt(0.1) * weather.log_previous_rain
weather["radiation_200"] = weather.radiation_w_m2 / 200
weather.to_csv(OUT / "weather.csv")
weather.groupby(weather.index.year).agg(["size", "min", "max"]).to_csv(OUT / "weather_audit.csv")
(OUT / "sources.json").write_text(
    json.dumps(
        [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
        indent=2,
    )
    + "\n"
)
print(f"Saved {len(weather)} complete hourly slots, 1993–2025; no forecast code imported.")
