"""Compare refitted time effects with frozen-time predictions on identical observations."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--panels", nargs="+", default=["priority", "passerines"])
parser.add_argument("--prefix", default="coherent-time")
parser.add_argument("--out", type=Path, default=Path("logs/time-refit-review"))
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
frames, diagnostics = [], []
for panel in args.panels:
    folder = root / f"logs/{args.prefix}-{panel}-year"
    new = pd.read_csv(folder / "held_out_intervals.csv")
    old = pd.read_csv(root / f"logs/coherent-intervals-{panel}-year/held_out_intervals.csv")
    new = new.merge(
        old[["english_name", "fold", "observation_id", "count", "predicted"]],
        on=["english_name", "fold", "observation_id"],
        suffixes=("", "_frozen"),
        validate="one_to_one",
    )
    assert np.array_equal(new["count"], new.count_frozen)
    bounds = []
    for context in pd.read_csv(root / f"logs/mixed-design-{panel}-year/manifest.csv").itertuples():
        components = pd.read_csv(
            root / f"logs/mixed-design-{panel}-year/{context.key}_components.csv"
        )
        components["rain_exposure"] = components.rain_mm * components.fraction
        support = components.groupby("observation_id", as_index=False).agg(
            min_tau=("tau", "min"),
            max_tau=("tau", "max"),
            rain_exposure=("rain_exposure", "sum"),
            exposure=("fraction", "sum"),
        )
        support["rain"] = support.rain_exposure / support.exposure
        support["english_name"], support["fold"] = context.english_name, context.fold
        bounds.append(support)
    new = new.merge(
        pd.concat(bounds), on=["english_name", "fold", "observation_id"], validate="one_to_one"
    )
    new["outside_daylight"] = new.min_tau.lt(0) | new.max_tau.gt(1)
    new["weather"] = np.where(new.rain.ge(0.1), "wet", "dry")
    new["year"] = pd.to_datetime(new.date).dt.year
    new["mae"] = abs(new.predicted - new["count"])
    new["frozen_mae"] = abs(new.predicted_frozen - new["count"])
    frames.append(new)
    diagnostics.append(pd.read_csv(folder / "fit_diagnostics.csv"))
rows = pd.concat(frames, ignore_index=True)
fits = pd.concat(diagnostics, ignore_index=True)
assert len(fits) == sum(
    len(pd.read_csv(root / f"logs/mixed-design-{panel}-year/manifest.csv"))
    for panel in args.panels
)
assert fits.gradient.lt(0.001).all() and fits.gradient_check.lt(0.001).all()
fits["integration_flag"] = fits.integration_loss_delta.ge(
    0.001
) | fits.integration_gradient_delta.ge(0.01)
fits.to_csv(args.out / "fit_diagnostics.csv", index=False)
scores = rows.groupby(
    ["english_name", "year", "resolution", "outside_daylight", "weather"], as_index=False
).agg(
    observations=("count", "size"),
    birds=("count", "sum"),
    predicted=("predicted", "sum"),
    frozen_predicted=("predicted_frozen", "sum"),
    mae=("mae", "mean"),
    frozen_mae=("frozen_mae", "mean"),
    max_prediction=("predicted", "max"),
)
scores["mae_ratio"] = scores.mae / scores.frozen_mae
scores.to_csv(args.out / "species_scores.csv", index=False)
scores.groupby(["resolution", "outside_daylight", "year", "weather"], as_index=False).agg(
    species=("english_name", "nunique"), mae_ratio=("mae_ratio", "mean")
).to_csv(args.out / "macro_scores.csv", index=False)
rows[rows.resolution.eq("hour") & rows.rain.ge(3)].groupby(
    ["english_name", "year"], as_index=False
).agg(
    hours=("count", "size"),
    positive_hours=("count", lambda x: (x > 0).sum()),
    birds=("count", "sum"),
    predicted=("predicted", "sum"),
    frozen_predicted=("predicted_frozen", "sum"),
).to_csv(
    args.out / "heavy_rain_scores.csv", index=False
)
days = rows.groupby(["english_name", "fold", "date", "year"], as_index=False).agg(
    count=("count", "sum"),
    predicted=("predicted", "sum"),
    frozen_predicted=("predicted_frozen", "sum"),
)
days["mae"] = abs(days.predicted - days["count"])
days["frozen_mae"] = abs(days.predicted_frozen - days["count"])
days.groupby(["english_name", "year"], as_index=False).agg(
    days=("count", "size"), mae=("mae", "mean"), frozen_mae=("frozen_mae", "mean")
).to_csv(args.out / "daily_scores.csv", index=False)
print(
    f"{len(fits)} contexts; integration flags {fits.integration_flag.sum()}; time-refit uncertainty has not been assessed."
)
print(
    scores[
        scores.english_name.eq("Great Cormorant")
        & scores.outside_daylight
        & scores.resolution.eq("hour")
    ].to_string(index=False)
)
