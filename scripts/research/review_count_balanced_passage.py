"""Compare completed count-balanced fits with matched retained references."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/count-balanced-passage")
KEY = ["date", "task", "english_name", "fold"]
new = pd.read_csv(OUT / "predictions.csv")
new = new[new.method.isin(["weather_mean", "weather_daily"])].copy()
new["method"] = new.method.replace({"weather_mean": "count_mean", "weather_daily": "count_daily"})
wide = new.pivot(index=KEY, columns="method", values="predicted").reset_index()
metadata = new.drop_duplicates(KEY)[KEY + ["count", "weather", "year", "era"]]
wide = wide.merge(metadata, on=KEY, validate="one_to_one")
old = pd.read_csv("logs/history-episode/predictions.csv")
old = old[old.method.isin(["weather_mean", "original_episode"])]
old_wide = old.pivot(index=KEY, columns="method", values="predicted").reset_index()
wide = wide.merge(old_wide, on=KEY, validate="one_to_one")
assert len(wide) * 2 == len(new)
assert wide[["weather_mean", "original_episode"]].notna().all().all()
old_truth = old.drop_duplicates(KEY)[KEY + ["count"]]
assert np.allclose(
    wide.merge(old_truth, on=KEY, validate="one_to_one").count_x,
    wide.merge(old_truth, on=KEY, validate="one_to_one").count_y,
)
prior = pd.read_csv("logs/daily-passage/predictions.csv")
prior = prior[prior.method.eq("weather_daily")][KEY + ["predicted"]].rename(
    columns={"predicted": "power15_daily"}
)
partial = wide.merge(prior, on=KEY, validate="one_to_one")
frames = []
for panel, frame, methods in [
    ("new_completed", wide, ["weather_mean", "original_episode", "count_mean", "count_daily"]),
    (
        "prior_daily_matched",
        partial,
        ["weather_mean", "original_episode", "power15_daily", "count_mean", "count_daily"],
    ),
]:
    long = frame.melt(
        id_vars=KEY + ["count", "weather", "year", "era"],
        value_vars=methods,
        var_name="method",
        value_name="predicted",
    )
    long["error"] = long.predicted - long["count"]
    long["absolute_error"] = abs(long.error)
    long["panel"] = panel
    frames.append(long)
long = pd.concat(frames, ignore_index=True)
long.to_csv(OUT / "criterion_predictions.csv", index=False)
expanded = pd.concat([long, long.assign(weather="all")])
species = expanded.groupby(["panel", "task", "weather", "english_name", "method"]).agg(
    mae=("absolute_error", "mean"),
    error=("error", "sum"),
    count=("count", "sum"),
    days=("date", "size"),
)
species["relative_bias"] = species.error / species["count"]
species.to_csv(OUT / "criterion_species.csv")
macro = species.groupby(["panel", "task", "weather", "method"])[["mae", "relative_bias"]].mean()
macro.to_csv(OUT / "criterion_macro.csv")
for group in ["year", "era"]:
    table = expanded.groupby(["panel", "task", group, "weather", "english_name", "method"]).agg(
        mae=("absolute_error", "mean"), error=("error", "sum"), count=("count", "sum")
    )
    table["relative_bias"] = table.error / table["count"]
    table.to_csv(OUT / f"criterion_{group}_species.csv")
    table.groupby(["panel", "task", group, "weather", "method"])[
        ["mae", "relative_bias"]
    ].mean().to_csv(OUT / f"criterion_{group}.csv")
truth = pd.read_csv(OUT / "season_errors.csv").drop_duplicates(["english_name", "year"])[
    ["english_name", "year", "observed_truth"]
]
season = (
    long[long.task.eq("historical")]
    .groupby(["panel", "english_name", "year", "method"])
    .error.sum()
    .reset_index()
)
season = season.merge(truth, on=["english_name", "year"], validate="many_to_one")
season["relative_bias"] = season.error / season.observed_truth
season["absolute_relative_error"] = abs(season.relative_bias)
season.to_csv(OUT / "criterion_season_species.csv", index=False)
season.groupby(["panel", "english_name", "method"])[
    ["relative_bias", "absolute_relative_error"]
].mean().groupby(["panel", "method"]).mean().to_csv(OUT / "criterion_season_macro.csv")

# Paired blocks are sampled jointly across species, separately for the two panels.
paired = []
rng = np.random.default_rng(20261012)
for (panel, task, weather), frame in expanded.groupby(["panel", "task", "weather"]):
    values = frame.pivot(
        index=KEY + ["count", "year"], columns="method", values="predicted"
    ).reset_index()
    values["block"] = (
        values.year
        if task == "historical"
        else pd.to_datetime(values.date).dt.to_period("W").astype(str)
    )
    blocks = sorted(values.block.unique())
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), size=2000)
    for reference in ["weather_mean", "original_episode", "count_mean"] + (
        ["power15_daily"] if panel == "prior_daily_matched" else []
    ):
        values["difference"] = abs(values.count_daily - values["count"]) - abs(
            values[reference] - values["count"]
        )
        grouped = values.groupby(["english_name", "block"]).difference.agg(["sum", "count"])
        sums = grouped["sum"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        counts = grouped["count"].unstack("block").reindex(columns=blocks).fillna(0).to_numpy()
        draws = ((weights @ sums.T) / (weights @ counts.T)).mean(axis=1)
        assert np.isfinite(draws).all()
        paired.append(
            dict(
                panel=panel,
                task=task,
                weather=weather,
                reference=reference,
                difference=values.groupby("english_name").difference.mean().mean(),
                low=np.quantile(draws, 0.025),
                high=np.quantile(draws, 0.975),
                species=values.english_name.nunique(),
            )
        )
pd.DataFrame(paired).to_csv(OUT / "criterion_paired.csv", index=False)

# Keep generic paired-new-baseline gates, then enforce the frozen old-reference gates.
gates = pd.read_csv(OUT / "acceptance.csv")
gates.to_csv(OUT / "acceptance_new_reference.csv", index=False)
for task, weather, gate in [
    ("historical", "wet", "historical_wet_2_percent_limit"),
    ("recent", "dry", "recent_dry_2_percent_limit"),
    ("recent", "wet", "recent_wet_2_percent_limit"),
]:
    group = macro.loc[("new_completed", task, weather)]
    gates.loc[gates.gate.eq(gate), "passed"] = (
        group.loc["count_daily", "mae"] <= 1.02 * group.loc["weather_mean", "mae"]
    )
gates.to_csv(OUT / "acceptance.csv", index=False)

# Training-only amplitude selection and saved endpoints must be reproducible.
manifest = pd.read_csv(OUT / "design/manifest.csv")
endpoint_count = 0
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    for sd in [0, 0.25, 0.5, 1]:
        for fold in range(3):
            saved = np.load(folder / f"cv_sd{sd}_fold{fold}.npz")
            assert saved["variance_power"] == 1 and saved["sd"] == sd
            endpoint_count += 1
        held = pd.read_csv(folder / f"cv_daily_sd{sd}.csv")
        actual = abs(held.predicted - held["count"]).mean()
        scores = pd.read_csv(folder / "amplitude_scores.csv")
        assert np.isclose(scores.loc[scores.sd.eq(sd), "daily_mae"].iloc[0], actual, atol=1e-9)
    if (folder / "assessment.csv").exists():
        selected = scores.sort_values("sd").sort_values("daily_mae", kind="stable").iloc[0].sd
        assert np.load(folder / "weather_daily_fit.npz")["sd"] == selected
print("Saved inner endpoints and amplitude scores verified:", endpoint_count)
print(macro.to_string())
print(
    "Reconstructed season:", pd.read_csv(OUT / "criterion_season_macro.csv").to_string(index=False)
)
print("Acceptance:", gates.to_string(index=False))
