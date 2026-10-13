"""Audit observed weather against missing daylight effort; closures never become training zeros."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
FEATURES = (
    "rain_mm",
    "rain_previous_24h_mm",
    "wind_u_m_s",
    "wind_v_m_s",
    "radiation_w_m2",
    "low_cloud_fraction",
)
RAIN_EDGES = [-np.inf, 0.1, 1, 3, np.inf]
RAIN_LABELS = ["<0.1 mm/h", "0.1–1 mm/h", "1–3 mm/h", ">=3 mm/h"]

# Read the prepared snapshot -------------------------------------------------
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, default=ROOT / "data/hourly-weather")
parser.add_argument("--out", type=Path, default=ROOT / "logs/hourly-weather-v2")
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
observed = pd.read_csv(args.input / "validation_masks.csv")
grid = pd.read_csv(args.input / "prediction_hours.csv")
grid["weather_available"] = grid[list(FEATURES)].notna().all(axis=1)
audit = []
ranges = []

# Match weather combinations to genuinely observed hours ---------------------
for species, target in grid.groupby("english_name"):
    training = observed[observed["english_name"].eq(species)]
    weather = training[list(FEATURES)].copy()
    weather[["rain_mm", "rain_previous_24h_mm"]] = np.log1p(
        weather[["rain_mm", "rain_previous_24h_mm"]]
    )
    scale = weather.std()
    tree = cKDTree((weather / scale).to_numpy())
    reference_distance = tree.query((weather / scale).to_numpy(), k=2)[0][:, 1]
    threshold = np.quantile(reference_distance, 0.95)
    target = target.copy()
    available = target["weather_available"]
    transformed = target.loc[available, list(FEATURES)].copy()
    transformed[["rain_mm", "rain_previous_24h_mm"]] = np.log1p(
        transformed[["rain_mm", "rain_previous_24h_mm"]]
    )
    target.loc[available, "weather_distance"] = tree.query((transformed / scale).to_numpy())[0]
    target["sparse_weather_combination"] = available & target["weather_distance"].gt(threshold)
    target["outside_observed_range"] = False
    for feature in FEATURES:
        lo, hi = training[feature].min(), training[feature].max()
        outside = available & (target[feature].lt(lo) | target[feature].gt(hi))
        target["outside_observed_range"] |= outside
        ranges.append(
            {
                "english_name": species,
                "feature": feature,
                "observed_min": lo,
                "observed_max": hi,
                "missing_hours_outside_range": target.loc[outside, "missing_exposure_hours"].sum(),
                "closure_hours_outside_range": target.loc[
                    outside & target["documented_weather_stop"], "closure_exposure_hours"
                ].sum(),
            }
        )
    audit.append(target)

# Summarise actual exposure and actual observed zeros ------------------------
audit = pd.concat(audit, ignore_index=True)
audit["rain_band"] = pd.cut(audit["rain_mm"], RAIN_EDGES, labels=RAIN_LABELS, right=False)
audit["closure_hours"] = audit["closure_exposure_hours"]
audit["unsupported_missing_hours"] = audit["missing_exposure_hours"].where(
    audit["sparse_weather_combination"] | audit["outside_observed_range"], 0
)
support = audit.groupby(["english_name", "rain_band"], observed=False).agg(
    observed_hours=("observed_exposure_hours", "sum"),
    missing_hours=("missing_exposure_hours", "sum"),
    closure_hours=("closure_hours", "sum"),
    unsupported_missing_hours=("unsupported_missing_hours", "sum"),
)
observed["rain_band"] = pd.cut(observed["rain_mm"], RAIN_EDGES, labels=RAIN_LABELS, right=False)
observed["zero_hours"] = observed["exposure_hours"].where(observed["count"].eq(0), 0)
counts = observed.groupby(["english_name", "rain_band"], observed=False).agg(
    birds=("count", "sum"), zero_hours=("zero_hours", "sum")
)
support = support.join(counts)
support["zero_effort_fraction"] = support["zero_hours"] / support["observed_hours"]
support["observed_birds_per_hour"] = support["birds"] / support["observed_hours"]
audit.to_csv(args.out / "weather_support_hours.csv", index=False)
support.to_csv(args.out / "weather_support.csv")
pd.DataFrame(ranges).to_csv(args.out / "weather_support_ranges.csv", index=False)
missing_weather = (
    audit[~audit["weather_available"]].groupby("english_name")["exposure_hours"].sum()
)
missing_weather.to_csv(args.out / "weather_missing.csv")
print(support.round(3).to_string())
print("\nHours without weather:\n", missing_weather.to_string())
