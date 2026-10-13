"""Download the hourly ERA5 weather at Défilé from the Open-Meteo archive into `data/weather/`.

Run from the repository root (34 requests, one a year, paced for the free API's limits):
uv run python scripts/hierarchical/fetch_weather.py > logs/hierarchical/fetch_weather.log

Plain ERA5 (`models=era5`, 0.25°), GMT, wind in m/s. Open-Meteo gives accumulated variables
(precipitation, radiation, sunshine) over the hour ending at the time stamp and the others at the
time stamp; `hourly_weather` in `run_steps.py` turns both into the UTC hour [t, t + 1). A year
already downloaded is skipped; delete its file to fetch it again. Missing hours are reported, not
filled: the fit asserts that every modelled day has its weather.
"""

import json
import time
import urllib.parse
import urllib.request

import pandas as pd
from common import WEATHER_DIR

LOCATION = (46.117215, 5.914877)  # the count site
YEARS = (1992, 2025)  # 1992 for the first days' 24-hour pressure change
URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = [
    "precipitation",
    "shortwave_radiation",
    "sunshine_duration",
    "cloud_cover_low",
    "boundary_layer_height",
    "temperature_2m",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_speed_100m",
    "wind_direction_100m",
]
PAUSE_SECONDS = 15


def fetch_year(year: int) -> pd.DataFrame:
    query = {
        "latitude": LOCATION[0],
        "longitude": LOCATION[1],
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "models": "era5",
        "timezone": "GMT",
        "wind_speed_unit": "ms",
        "hourly": ",".join(VARIABLES),
    }
    with urllib.request.urlopen(f"{URL}?{urllib.parse.urlencode(query)}", timeout=300) as r:
        hourly = json.load(r)["hourly"]
    frame = pd.DataFrame(hourly)
    frame["time"] = pd.to_datetime(frame.time, utc=True)
    missing = frame[VARIABLES].isna().sum()
    if missing.any():  # e.g. boundary-layer height, January-June 2024: the fit refuses such a day
        print(f"{year}: missing hours {missing[missing > 0].to_dict()}", flush=True)
    return frame


def main():
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(YEARS[0], YEARS[1] + 1):
        path = WEATHER_DIR / f"era5_{year}.csv"
        if path.exists():
            continue
        for attempt in range(3):
            try:
                fetch_year(year).to_csv(path, index=False)
                break
            except OSError as error:
                print(f"{year}: {error}, retrying", flush=True)
                time.sleep(60 * (attempt + 1))
        else:
            raise RuntimeError(f"{year}: failed three times")
        print(f"{year}: done", flush=True)
        time.sleep(PAUSE_SECONDS)


if __name__ == "__main__":
    main()
