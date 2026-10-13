"""Download point ERA5 lift proxies with the temporary dependencies in ERA5_LIFT.md."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

OUT = Path("logs/era5-lift")
SOURCE = Path("logs/era5-features")
STORE = "https://arco.datastores.ecmwf.int/cadl-arco-geo-002/arco/reanalysis_era5_single_levels/sfc/geoChunked.zarr"
LATITUDE, LONGITUDE = 46.117215, 5.914877
VARIABLES = ["blh", "sshf", "tp", "ssrd"]
OUT.mkdir(parents=True, exist_ok=True)
config = yaml.safe_load(Path.home().joinpath(".cdsapirc").read_text())
dataset = xr.open_zarr(
    STORE,
    consolidated=True,
    chunks=None,
    storage_options={"headers": {"Authorization": "Bearer " + config["key"]}},
)
point = dataset[VARIABLES].sel(latitude=LATITUDE, longitude=LONGITUDE, method="nearest")
point = point.sel(time=slice("1992-12-31", "2026-01-01T01:00:00")).load()
raw = point.to_dataframe()[VARIABLES]
raw.index = pd.to_datetime(raw.index, utc=True)
assert (
    raw.index.is_unique and raw.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all()
)
assert np.isfinite(raw.to_numpy()).all() and raw.blh.ge(0).all()
raw.to_csv(OUT / "raw_hourly.csv")
metadata = dict(
    store=STORE,
    requested_coordinates=[LATITUDE, LONGITUDE],
    selected_coordinates=[float(point.latitude), float(point.longitude)],
    first=str(raw.index.min()),
    last=str(raw.index.max()),
    variables={name: dict(point[name].attrs) for name in VARIABLES},
    raw_sha256=hashlib.sha256((OUT / "raw_hourly.csv").read_bytes()).hexdigest(),
    download_runtime={
        name: version(name) for name in ["xarray", "zarr", "fsspec", "aiohttp", "numpy", "pandas"]
    },
)
(OUT / "sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
weather = pd.read_csv(SOURCE / "weather.csv", index_col="slot_start")
weather.index = pd.to_datetime(weather.index, utc=True)
# Boundary-layer height is instantaneous; heat/rain/radiation are preceding-hour accumulations.
aligned = pd.DataFrame(index=raw.index)
aligned["boundary_layer_m"] = (raw.blh + raw.blh.shift(-1)) / 2
# ECMWF's positive-downward convention: negative sensible heat heats the atmosphere.
aligned["upward_heat_w_m2"] = -raw.sshf.shift(-1) / 3600
aligned["control_rain_mm"] = raw.tp.shift(-1) * 1000
aligned["control_radiation_w_m2"] = raw.ssrd.shift(-1) / 3600
aligned = aligned.reindex(weather.index)
assert np.isfinite(aligned.to_numpy()).all()
controls = []
for reference, control in [
    ("rain_mm", "control_rain_mm"),
    ("radiation_w_m2", "control_radiation_w_m2"),
]:
    difference = aligned[control] - weather[reference]
    controls.append(
        dict(
            variable=reference,
            correlation=aligned[control].corr(weather[reference]),
            mean_absolute_difference=abs(difference).mean(),
            maximum_absolute_difference=abs(difference).max(),
        )
    )
pd.DataFrame(controls).to_csv(OUT / "source_comparison.csv", index=False)
weather["boundary_layer_m"] = aligned.boundary_layer_m
weather["upward_heat_w_m2"] = aligned.upward_heat_w_m2
weather["log_boundary_layer_km"] = np.log1p(weather.boundary_layer_m / 1000)
weather["upward_heat_100"] = weather.upward_heat_w_m2 / 100
weather.to_csv(OUT / "weather.csv")
weather.groupby(weather.index.year)[["boundary_layer_m", "upward_heat_w_m2"]].agg(
    ["size", "min", "max"]
).to_csv(OUT / "weather_audit.csv")
print("Saved ERA5 point:", metadata["selected_coordinates"], "hours:", len(weather))
print(pd.DataFrame(controls).to_string(index=False))
