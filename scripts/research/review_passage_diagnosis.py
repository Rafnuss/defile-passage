"""Summarize saved diagnostic tables and reconcile the original batch's scores."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/daily-passage-diagnosis")
FITS = Path("logs/daily-passage")
long = pd.read_csv(OUT / "bias_components.csv")
long["era"] = pd.cut(
    long.year,
    [1992, 2007, 2016, 2021, 2025],
    labels=["1993–2007", "2008–2016", "2017–2021", "2022–2025"],
)
for group in ["weather", "era"]:
    summary = long.groupby(["task", group, "english_name", "method"], observed=True).agg(
        count=("count", "sum"),
        predicted=("predicted", "sum"),
        mae=("absolute_error", "mean"),
        days=("date", "size"),
    )
    summary["relative_bias"] = (summary.predicted - summary["count"]) / summary["count"]
    summary.to_csv(OUT / f"{group}_species.csv")
    summary.groupby(["task", group, "method"], observed=True)[
        ["relative_bias", "mae"]
    ].mean().to_csv(OUT / f"{group}_summary.csv")

# Reconcile full-denominator count-stratum contributions with saved total bias.
strata = pd.read_csv(OUT / "count_group_summary.csv")
reconstructed = strata.groupby(["task", "method"]).bias_contribution.sum().reset_index()
reconstructed["method"] = reconstructed.method.replace(
    {"base": "weather_mean", "daily": "weather_daily"}
)
original = pd.read_csv(FITS / "group_total_bias.csv").query("weather == 'all'")
matched = original.merge(reconstructed, on=["task", "method"], validate="one_to_one")
assert len(matched) == 6
assert np.allclose(matched.relative_bias, matched.bias_contribution, atol=1e-12)
weather = pd.read_csv(OUT / "weather_summary.csv")
weather["method"] = weather.method.replace({"base": "weather_mean", "daily": "weather_daily"})
matched = pd.read_csv(FITS / "group_total_bias.csv").merge(
    weather, on=["task", "weather", "method"], validate="one_to_one"
)
assert len(matched) == 12
assert np.allclose(matched.relative_bias_x, matched.relative_bias_y, atol=1e-12)

# Preserve reconstructed-season evidence separately from missing-count bias.
season = pd.read_csv(FITS / "season_errors.csv")
season["relative_bias"] = season.bias / season.observed_truth
season.to_csv(OUT / "reconstructed_season_errors.csv", index=False)
summary = (
    season.groupby(["english_name", "method"])[["relative_bias", "absolute_relative_error"]]
    .mean()
    .groupby("method")
    .mean()
)
saved = pd.read_csv(FITS / "season_bias.csv").set_index("method").relative_bias
assert np.allclose(summary.relative_bias.loc[saved.index], saved, atol=1e-12)
summary.to_csv(OUT / "reconstructed_season_summary.csv")
print("All overall/weather bias and reconstructed-season summaries reconcile with saved batch.")
