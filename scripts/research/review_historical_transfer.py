"""Report paired gap error and species-season bias without pooled cancellation."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/historical-transfer")
manifest = pd.read_csv(OUT / "design/manifest.csv")
frames, seasons, numerical, failures = [], [], [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    if not (folder / "assessment.csv").exists():
        failures.append(
            dict(key=context.key, scenario=context.scenario, resolution=context.resolution)
        )
        continue
    frame = pd.read_csv(folder / "assessment.csv")
    rows = pd.read_csv(OUT / f"input/{context.key}_components.csv")
    truth = rows[rows.year.eq(context.target_year)]
    for method, result in frame.groupby("method"):
        seasons.append(
            dict(
                key=context.key,
                english_name=context.english_name,
                scenario=context.scenario,
                target_year=context.target_year,
                resolution=context.resolution,
                method=method,
                truth=truth["count"].sum(),
                missing_truth=result["count"].sum(),
                missing_predicted=result.predicted.sum(),
                retained_hours=truth.loc[~truth.hidden, "fraction"].sum(),
                truth_hours=truth.fraction.sum(),
            )
        )
    frames.append(frame)
    diagnostics = pd.read_csv(folder / "diagnostics.csv").merge(
        pd.read_csv(folder / "assessment_diagnostics.csv"),
        on="key",
        suffixes=("_mean", "_assessment"),
    )
    numerical.append(diagnostics)
coverage = pd.read_csv(OUT / "coverage.csv").query("scenario == 'early'")
coverage = coverage.merge(
    pd.read_csv("logs/gap-target-audit/year.csv")[["year", "observed_hours", "daylight_hours"]],
    left_on="target_year",
    right_on="year",
)
coverage["truth_share_of_observed_effort"] = (
    coverage.observed_truth_hours / coverage.observed_hours
)
coverage.to_csv(OUT / "truth_support.csv", index=False)
pd.DataFrame(failures, columns=["key", "scenario", "resolution"]).to_csv(
    OUT / "failures.csv", index=False
)
results = pd.concat(frames, ignore_index=True)
season = pd.DataFrame(seasons)
for data in [results, season]:
    data["assessment_group"] = np.select(
        [
            data.english_name.isin(["Common Wood Pigeon", "Stock Dove"]),
            data.english_name.isin(
                ["Barn Swallow", "Eurasian Chaffinch", "Meadow Pipit", "Redwing"]
            ),
        ],
        ["pigeons", "passerines"],
        default="core_large_birds",
    )
results["error"] = results.predicted - results["count"]
results["absolute_error"] = abs(results.error)
results["coverage_band"] = pd.cut(
    results.retained_fraction,
    [-0.001, 0, 0.25, 0.5, 0.75, 1],
    labels=["none", "0–25%", "25–50%", "50–75%", "75–100%"],
)
for level in [80, 95]:
    results[f"covered{level}"] = (
        results["count"]
        .between(results[f"lower{level}"], results[f"upper{level}"])
        .where(results[f"lower{level}"].notna() & results[f"upper{level}"].notna())
    )
    results[f"width{level}"] = results[f"upper{level}"] - results[f"lower{level}"]
season["bias"] = season.missing_predicted - season.missing_truth
season["reconstructed"] = season.truth + season.bias
season["relative_bias"] = season.bias / season.truth
season["absolute_relative_bias"] = abs(season.relative_bias)
season["retained_fraction"] = season.retained_hours / season.truth_hours
season.to_csv(OUT / "season_totals.csv", index=False)
results.to_csv(OUT / "predictions.csv", index=False)
pd.concat(numerical, ignore_index=True).to_csv(OUT / "diagnostics.csv", index=False)
summary = pd.concat([results, results.assign(weather="all")], ignore_index=True)
keys = ["assessment_group", "scenario", "resolution", "method", "weather"]
metrics = ["absolute_error", "error", "covered80", "covered95", "width80", "width95"]
species = summary.groupby(keys + ["english_name"])[metrics].mean()
species.to_csv(OUT / "species_gap_scores.csv")
species.groupby(keys).mean().to_csv(OUT / "group_gap_scores.csv")
results.groupby(
    ["assessment_group", "scenario", "resolution", "method", "coverage_band"], observed=True
)[metrics].mean().to_csv(OUT / "coverage_scores.csv")
season.groupby(["assessment_group", "scenario", "resolution", "method"]).agg(
    mean_relative_bias=("relative_bias", "mean"),
    mean_absolute_relative_bias=("absolute_relative_bias", "mean"),
    median_absolute_relative_bias=("absolute_relative_bias", "median"),
    reconstructed=("reconstructed", "sum"),
    truth=("truth", "sum"),
    missing_truth=("missing_truth", "sum"),
    missing_predicted=("missing_predicted", "sum"),
).to_csv(OUT / "season_scores.csv")
season.groupby(["assessment_group", "scenario", "resolution", "method", "target_year"]).agg(
    mean_relative_bias=("relative_bias", "mean"),
    mean_absolute_relative_bias=("absolute_relative_bias", "mean"),
).to_csv(OUT / "year_season_scores.csv")
season.groupby(["assessment_group", "scenario", "resolution", "method", "english_name"]).agg(
    mean_relative_bias=("relative_bias", "mean"),
    mean_absolute_relative_bias=("absolute_relative_bias", "mean"),
).to_csv(OUT / "species_season_scores.csv")

# Modern years are the independent resampling unit; all species/templates move together.
rng = np.random.default_rng(20261012)
weights = rng.multinomial(4, [0.25] * 4, size=4000)
paired = []
for (group, scenario, resolution), sample in season.groupby(
    ["assessment_group", "scenario", "resolution"]
):
    table = sample.pivot(
        index=["target_year", "english_name"], columns="method", values="absolute_relative_bias"
    )
    for method in ["weather_mean", "weather_retained"]:
        difference = (
            (table[method] - table.original_episode)
            .groupby("target_year")
            .mean()
            .reindex(range(2022, 2026))
            .to_numpy()
        )
        boot = weights @ difference / 4
        paired.append(
            dict(
                assessment_group=group,
                scenario=scenario,
                resolution=resolution,
                method=method,
                seasonal_abs_relative_difference=np.mean(difference),
                lower=np.quantile(boot, 0.025),
                upper=np.quantile(boot, 0.975),
                years=4,
            )
        )
pd.DataFrame(paired).to_csv(OUT / "paired_season_scores.csv", index=False)
print("Completed contexts:", len(frames), "of", len(manifest), "failures:", len(failures))
print(
    pd.read_csv(OUT / "season_scores.csv")
    .query("assessment_group == 'core_large_birds'")
    .to_string(index=False)
)
print(
    pd.concat(numerical)[["seconds_mean", "gradient", "derivative_error", "calibration_gradient"]]
    .agg(["median", "max"])
    .to_string()
)
