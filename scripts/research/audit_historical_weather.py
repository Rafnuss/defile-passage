"""Inventory existing historical ERA5 values without changing cached weather.

Run with uv run --with 'pyarrow<20' python scripts/research/audit_historical_weather.py.
"""

from pathlib import Path

import pandas as pd

CACHE = Path("../defile-migration-forecast/data/weather/era5_hourly/location=Defile")
OUT = Path("logs/historical-transfer")
COLUMNS = [
    "total_precipitation",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "low_cloud_cover",
    "surface_solar_radiation_downwards",
]
frames, inventory = [], []
for part in sorted(CACHE.glob("part-*.parquet")):
    frame = pd.read_parquet(part, columns=["datetime", *COLUMNS])
    inventory.append(
        dict(
            part=part.name, rows=len(frame), first=frame.datetime.min(), last=frame.datetime.max()
        )
    )
    frames.append(frame)
weather = pd.concat(frames, ignore_index=True).sort_values("datetime")
assert not weather.datetime.duplicated().any()
assert weather.datetime.diff().dropna().eq(pd.Timedelta(hours=1)).all()
weather["year"] = weather.datetime.dt.year
weather["missing_values"] = weather[COLUMNS].isna().any(axis=1)
weather["negative_rain"] = weather.total_precipitation.lt(0)
weather.groupby("year").agg(
    hours=("datetime", "size"),
    missing_values=("missing_values", "sum"),
    negative_rain=("negative_rain", "sum"),
).to_csv(OUT / "weather_cache_years.csv")
pd.DataFrame(inventory).to_csv(OUT / "weather_cache_inventory.csv", index=False)
print(pd.DataFrame(inventory).to_string(index=False))
print(
    "Missing weather rows:",
    weather.missing_values.sum(),
    "; negative rain rows:",
    weather.negative_rain.sum(),
)
print("No duplicated timestamps or hourly gaps; units/alignment follow build_hourly_weather.py.")
