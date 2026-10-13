"""Compare whole-day gap predictions with the original production benchmark."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--prefix", default="simple-gaps-panel")
parser.add_argument("--design-prefix", default="simple-gaps-design")
parser.add_argument(
    "--reference", type=Path, default=root / "logs/hourly-weather-panel-v4/held_out_days.csv"
)
parser.add_argument("--out", type=Path, default=root / "logs/simple-gaps-review")
args = parser.parse_args()
out = args.out
out.mkdir(exist_ok=True)
hours, status, diagnostics = [], [], []
for panel in ["priority", "passerines"]:
    folder = root / f"logs/{args.prefix}-{panel}"
    predictions = pd.read_csv(folder / "predictions.csv")
    status.append(pd.read_csv(folder / "status.csv"))
    diagnostics.append(pd.read_csv(folder / "diagnostics.csv"))
    inputs = root / f"logs/{args.design_prefix}-{panel}"
    for context in pd.read_csv(inputs / "manifest.csv").itertuples():
        rows = predictions[
            predictions.english_name.eq(context.english_name) & predictions.fold.eq(context.fold)
        ]
        components = pd.read_csv(inputs / f"{context.key}_components.csv")
        rows = rows.merge(
            components[["observation_id", "rain_mm"]], on="observation_id", validate="many_to_one"
        )
        hours.append(rows)
hours = pd.concat(hours, ignore_index=True)
hours["rain_exposure"] = hours.rain_mm * hours.exposure_hours
assert not hours.duplicated(["variant", "english_name", "start", "end"]).any()
days = (
    hours.groupby(["variant", "english_name", "fold", "date"])
    .agg(
        count=("count", "sum"),
        predicted=("predicted", "sum"),
        exposure_hours=("exposure_hours", "sum"),
        rain_exposure=("rain_exposure", "sum"),
    )
    .reset_index()
)
days["rain_mm"] = days.rain_exposure / days.exposure_hours
days["weather"] = np.where(days.rain_mm >= 0.1, "wet", "dry")
reference = pd.read_csv(args.reference)
reference = reference[reference.model.eq("production_episode") & reference.fold.lt(3)]
keys = ["english_name", "fold", "date"]
comparison = days.merge(
    reference[keys + ["count", "predicted", "hours"]],
    on=keys,
    suffixes=("", "_benchmark"),
    validate="many_to_one",
)
assert len(comparison) == len(days)
assert np.array_equal(comparison["count"], comparison.count_benchmark)
assert np.allclose(comparison.exposure_hours, comparison.hours)
comparison["candidate_error"] = (comparison.predicted - comparison["count"]).abs()
comparison["benchmark_error"] = (comparison.predicted_benchmark - comparison["count"]).abs()
comparison["difference"] = comparison.candidate_error - comparison.benchmark_error
comparison["squared_error"] = (comparison.predicted - comparison["count"]) ** 2
comparison["benchmark_squared_error"] = (comparison.predicted_benchmark - comparison["count"]) ** 2
comparison["week"] = (pd.to_datetime(comparison.date) - pd.Timestamp("1970-01-05")).dt.days // 7
comparison.to_csv(out / "paired_days.csv", index=False)
species = (
    comparison.groupby(["variant", "english_name", "weather"])
    .agg(
        days=("count", "size"),
        observed=("count", "sum"),
        predicted=("predicted", "sum"),
        candidate_mae=("candidate_error", "mean"),
        benchmark_mae=("benchmark_error", "mean"),
        candidate_mse=("squared_error", "mean"),
        benchmark_mse=("benchmark_squared_error", "mean"),
        benchmark_predicted=("predicted_benchmark", "sum"),
        difference=("difference", "mean"),
    )
    .reset_index()
)
species["mae_ratio"] = species.candidate_mae / species.benchmark_mae
species.to_csv(out / "species_scores.csv", index=False)

# Use the same observed days across the supplied model comparisons.
common = comparison.groupby(keys).variant.nunique().eq(comparison.variant.nunique())
common = common[common].reset_index()[keys]
matched = comparison.merge(common, on=keys, validate="many_to_one")
# Scientific priority is specified by the user, independent of candidate errors.
matched["assessment_group"] = np.select(
    [
        matched.english_name.isin(["Common Wood Pigeon", "Stock Dove"]),
        matched.english_name.isin(
            ["Barn Swallow", "Eurasian Chaffinch", "Meadow Pipit", "Redwing"]
        ),
    ],
    ["pigeons", "passerines"],
    default="core_large_birds",
)
rng = np.random.default_rng(20261012)
weeks = np.sort(matched.week.unique())
frequency = rng.multinomial(len(weeks), np.full(len(weeks), 1 / len(weeks)), size=1200)
summary = []
summary_rows = pd.concat([matched, matched.assign(weather="all")], ignore_index=True)
summary_rows = pd.concat(
    [summary_rows, summary_rows.assign(assessment_group="all_species")], ignore_index=True
)
for (group, variant, weather), frame in summary_rows.groupby(
    ["assessment_group", "variant", "weather"]
):
    cluster = frame.groupby(["english_name", "week"]).agg(
        total=("difference", "sum"), n=("difference", "size")
    )
    totals = cluster.total.unstack().reindex(columns=weeks).fillna(0).to_numpy()
    counts = cluster.n.unstack().reindex(columns=weeks).fillna(0).to_numpy()
    draws = ((totals @ frequency.T) / (counts @ frequency.T)).mean(axis=0)
    scores = frame.groupby("english_name")[["candidate_error", "benchmark_error"]].mean()
    summary.append(
        dict(
            assessment_group=group,
            variant=variant,
            weather=weather,
            species=len(scores),
            days=len(frame),
            candidate_mae=scores.candidate_error.mean(),
            benchmark_mae=scores.benchmark_error.mean(),
            difference=scores.candidate_error.mean() - scores.benchmark_error.mean(),
            lower=np.quantile(draws, 0.025),
            upper=np.quantile(draws, 0.975),
            median_species_mae_ratio=(scores.candidate_error / scores.benchmark_error).median(),
            species_better=(scores.candidate_error < scores.benchmark_error).sum(),
            observed=frame["count"].sum(),
            predicted=frame.predicted.sum(),
            benchmark_predicted=frame.predicted_benchmark.sum(),
        )
    )
pd.DataFrame(summary).to_csv(out / "group_macro_scores.csv", index=False)
pd.DataFrame(summary).query("assessment_group == 'all_species'").to_csv(
    out / "matched_macro_scores.csv", index=False
)
zero = (
    matched[matched["count"].eq(0)]
    .groupby(["variant", "weather"])
    .agg(
        days=("count", "size"),
        predicted=("predicted", "sum"),
        benchmark=("predicted_benchmark", "sum"),
        mean_predicted=("predicted", "mean"),
    )
)
zero.to_csv(out / "zero_days.csv")
heavy = (
    hours[hours.rain_mm.ge(3)]
    .groupby(["variant", "english_name"])
    .agg(hours=("count", "size"), observed=("count", "sum"), predicted=("predicted", "sum"))
)
heavy.to_csv(out / "heavy_rain_hours.csv")
pd.concat(status).to_csv(out / "status.csv", index=False)
pd.concat(diagnostics).to_csv(out / "fit_diagnostics.csv", index=False)
print(pd.concat(status).groupby("variant").passed.agg(["sum", "count"]).to_string())
print(pd.DataFrame(summary).to_string(index=False))
print("Zero-count observed days:\n", zero.to_string())

# Keep gap lengths, total calibration and zero/positive days visible by scientific group.
strata = []
for column in ["fold", "count_state", "year"]:
    frame = matched.assign(
        count_state=np.where(matched["count"].eq(0), "zero", "positive"),
        year=pd.to_datetime(matched.date).dt.year,
    )
    scores = frame.groupby(["assessment_group", "variant", "weather", column, "english_name"]).agg(
        days=("count", "size"),
        observed=("count", "sum"),
        predicted=("predicted", "sum"),
        benchmark_predicted=("predicted_benchmark", "sum"),
        candidate_mae=("candidate_error", "mean"),
        benchmark_mae=("benchmark_error", "mean"),
    )
    scores.to_csv(out / f"species_{column}_scores.csv")
    strata.append(scores.reset_index().assign(stratum=column))
pd.concat(strata, ignore_index=True).to_csv(out / "stratified_scores.csv", index=False)
