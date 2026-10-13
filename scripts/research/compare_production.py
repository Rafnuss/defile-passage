"""Refit the production episode GAM on the hourly pilot's training intervals and common masks.

This is a matched-input comparison of model architectures, not a score of cached all-history fits.
The production diurnal profile and dispersion are learned again inside every fold.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T
from defile_explore.timeofday import RATIO_WEIGHT_POWER, fit_ratio_surface

ROOT = Path(__file__).resolve().parents[2]
DRAWS = 500
SEED = 20261010


def training_profile(training: pd.DataFrame) -> np.ndarray:
    """Production ratio-profile estimator, using the retained intervals' exact daylight
    midpoints."""
    samples = training[training["exposure_hours"].ge(P.PROFILE_MIN_HOUR_EFFORT)].copy()
    daily = samples.groupby("date").agg(
        birds=("count", "sum"), hours=("exposure_hours", "sum"), intervals=("count", "size")
    )
    samples = samples.join(daily, on="date")
    samples = samples[samples["birds"].gt(0) & samples["intervals"].ge(P.PROFILE_MIN_HOURS)]
    ratio = samples["count"] / samples["exposure_hours"] / (samples["birds"] / samples["hours"])
    doy = np.arange(P.PROFILE_DOY[0], P.PROFILE_DOY[1] + 1)
    tau = np.linspace(0, 1, P.TAU_GRID)
    surface = fit_ratio_surface(
        samples["doy"].to_numpy(),
        samples["tau"].to_numpy(),
        ratio.to_numpy(),
        samples["birds"].to_numpy() ** RATIO_WEIGHT_POWER,
        doy,
        np.clip(tau, samples["tau"].min(), samples["tau"].max()),
        k1=P.PROFILE_TAU_SPLINES,
    )
    dawn, dusk = P.twilight(doy)
    slots = (np.arange(E.SLOTS) + 0.5) / E.STEPS_PER_HOUR
    profile = np.array(
        [
            np.interp((slots - a) / (b - a), tau, np.maximum(curve, 0))
            for a, b, curve in zip(dawn, dusk, surface)
        ]
    ) * P.daylight(doy)
    return profile / profile.sum(axis=1, keepdims=True)


def interval_slots(frame: pd.DataFrame) -> np.ndarray:
    """Exact effort fractions on the production model's five-minute solar grid."""
    start, end = E.to_local(frame["start"]), E.to_local(frame["end"])
    shifts = E.solar_shift(frame["date"])
    return np.array(
        [
            E.hours_per_slot([(a, b)], shift) * E.STEPS_PER_HOUR
            for a, b, shift in zip(start, end, shifts)
        ]
    )


def main():
    # Read the shared validation masks ------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/hourly-weather")
    parser.add_argument("--out", type=Path, default=ROOT / "logs/hourly-weather-v2")
    parser.add_argument("--taxa", nargs="+")
    parser.add_argument("--folds", nargs="+", type=int, default=[0, 1, 2, 3])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(args.input / "validation_masks.csv", parse_dates=["date"])
    data["start"] = pd.to_datetime(data["start"], utc=True)
    data["end"] = pd.to_datetime(data["end"], utc=True)
    if args.taxa:
        data = data[data["english_name"].isin(args.taxa)]
    results = []
    fit_diagnostics = []

    # Refit on exactly the retained observations in each fold --------------------
    for species, sample in data.groupby("english_name"):
        sample = sample.reset_index(drop=True)
        slots = interval_slots(sample)
        years = np.arange(sample["year"].min(), sample["year"].max() + 1)
        dates = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
        doy_range = (int(sample["doy"].min()), int(sample["doy"].max()))
        doy = T.season_day(dates)
        dates = dates[(doy >= doy_range[0]) & (doy <= doy_range[1])]
        for fold in args.folds:
            print(f"{species}: production episode, fold {fold}", flush=True)
            hidden = sample["hidden_hours"] if fold == 3 else sample["block_fold"].eq(fold)
            train, test = sample[~hidden].copy(), sample[hidden].copy()
            profile = training_profile(train)
            coverage = (
                slots
                * profile[np.clip(sample["doy"].to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]
            ).sum(axis=1)
            train["c"], test["c"] = coverage[~hidden], coverage[hidden]
            day = train.groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
            frame = pd.DataFrame({"date": dates, "year": dates.year, "doy": T.season_day(dates)})
            frame = frame.join(day, on="date").fillna({"y": 0, "c": 0})
            low = frame["c"].lt(T.MIN_COVERAGE)
            frame["extra"] = frame["y"].where(low, 0)
            frame.loc[low, ["y", "c"]] = 0
            fit = T.fit("gam", frame, years, doy_range)
            # The production flock estimator groups midpoint-assigned solar hours into four-hour blocks.
            midpoint = E.to_local(train["start"] + (train["end"] - train["start"]) / 2)
            train["hour"] = np.floor(
                (midpoint - midpoint.dt.normalize()) / pd.Timedelta(hours=1)
                - E.solar_shift(train["date"])
            ).astype(int)
            hourly = train.groupby(["date", "hour"], as_index=False)["count"].sum()
            daily = train.groupby("date", as_index=False)["count"].sum().assign(timed=1.0)
            effort = pd.DataFrame(
                {
                    "date": train["date"].drop_duplicates(),
                    "state": "counted",
                    "slots": [
                        slots[(sample["date"].eq(date) & ~hidden).to_numpy()].sum(axis=0)
                        for date in train["date"].drop_duplicates()
                    ],
                }
            )
            kappa = T.hour_dispersion(daily, hourly, effort, profile)
            target = test.groupby("date").agg(
                count=("count", "sum"),
                hidden_c=("c", "sum"),
                hours=("exposure_hours", "sum"),
            )
            rain = (test["rain_mm"] * test["exposure_hours"]).groupby(test["date"]).sum()
            target["rain_mm"] = rain
            missing = frame["date"].map(target["hidden_c"]).fillna(0).to_numpy()
            draws = T.fill_draws(
                fit, frame, frame["c"].to_numpy() + missing, n=DRAWS, seed=SEED + fold, kappa=kappa
            )
            missed = draws - frame["y"].to_numpy() - frame["extra"].to_numpy()
            selected = frame["date"].isin(target.index).to_numpy()
            prediction = missed[:, selected]
            result = target.loc[frame.loc[selected, "date"]].reset_index()
            result["english_name"], result["model"] = species, "production_episode"
            result["fold"], result["gap"] = fold, "hours" if fold == 3 else "days"
            result["year"] = result["date"].dt.year
            result["predicted"] = prediction.mean(axis=0)
            for quantile, name in zip(T.QUANTILES, ["q025", "q10", "q50", "q90", "q975"]):
                result[name] = np.quantile(prediction, quantile, axis=0)
            results.append(result)
            fit_diagnostics.append(
                {
                    "english_name": species,
                    "fold": fold,
                    "theta": fit.theta,
                    "kappa": kappa,
                    "low_coverage_days": int(low.sum()),
                }
            )
            pd.concat(results, ignore_index=True).to_csv(
                args.out / "production_held_out_days.csv", index=False
            )
            pd.DataFrame(fit_diagnostics).to_csv(
                args.out / "production_diagnostics.csv", index=False
            )
    print("Production episode comparisons saved", flush=True)


if __name__ == "__main__":
    main()
