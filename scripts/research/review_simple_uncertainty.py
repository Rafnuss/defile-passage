"""Review empirical prediction intervals and paired retained-hour gains."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/simple-uncertainty")
results = pd.read_csv(OUT / "predictions.csv")
diagnostics = pd.read_csv(OUT / "diagnostics.csv")
assert len(diagnostics) == 48 and diagnostics.gradient.max() < 0.001
keys = ["english_name", "fold", "date"]
full = results[results.task.eq("full_day")]
original = pd.read_csv("logs/gap-validation-review/paired_days.csv")
matched = full.merge(
    original[keys + ["predicted"]], on=keys, suffixes=("", "_frozen"), validate="one_to_one"
)
assert len(matched) == 4191 and np.allclose(matched.predicted, matched.predicted_frozen)
partial = results[results.task.eq("three_hour_gap")]
assert np.allclose(partial.retained_count + partial.predicted, partial.full_day_predicted)
assert np.allclose(partial.retained_count + partial["count"], partial.full_observed_count)
for level in [80, 95]:
    assert (results[f"upper{level}"] >= results[f"lower{level}"]).all()
    assert (results[f"lower{level}"] >= 0).all()
    assert np.allclose(
        partial.retained_count + partial[f"lower{level}"], partial[f"full_day_lower{level}"]
    )
    assert np.allclose(
        partial.retained_count + partial[f"upper{level}"], partial[f"full_day_upper{level}"]
    )
base = partial[partial.method.eq("unadjusted")]
adjusted = partial[partial.method.eq("retained_adjusted")]
paired = adjusted.merge(
    base[keys + ["count", "absolute_error"]],
    on=keys,
    suffixes=("", "_base"),
    validate="one_to_one",
)
assert np.array_equal(paired["count"], paired.count_base)
paired["difference"] = paired.absolute_error - paired.absolute_error_base
paired["week"] = (pd.to_datetime(paired.date) - pd.Timestamp("1970-01-05")).dt.days // 7
rng = np.random.default_rng(20261012)
weeks = np.sort(paired.week.unique())
frequency = rng.multinomial(len(weeks), np.full(len(weeks), 1 / len(weeks)), size=1200)
summary = []
for (group, weather), frame in pd.concat([paired, paired.assign(weather="all")]).groupby(
    ["assessment_group", "weather"]
):
    clusters = frame.groupby(["english_name", "week"]).agg(
        total=("difference", "sum"), n=("difference", "size")
    )
    totals = clusters.total.unstack().reindex(columns=weeks).fillna(0).to_numpy()
    counts = clusters.n.unstack().reindex(columns=weeks).fillna(0).to_numpy()
    draws = ((totals @ frequency.T) / (counts @ frequency.T)).mean(axis=0)
    species = frame.groupby("english_name")[["absolute_error", "absolute_error_base"]].mean()
    summary.append(
        dict(
            assessment_group=group,
            weather=weather,
            days=len(frame),
            adjusted_mae=species.absolute_error.mean(),
            base_mae=species.absolute_error_base.mean(),
            difference=(species.absolute_error - species.absolute_error_base).mean(),
            lower=np.quantile(draws, 0.025),
            upper=np.quantile(draws, 0.975),
            median_species_ratio=(species.absolute_error / species.absolute_error_base).median(),
            species_better=int((species.absolute_error < species.absolute_error_base).sum()),
        )
    )
pd.DataFrame(summary).to_csv(OUT / "paired_adjustment_scores.csv", index=False)
print(pd.DataFrame(summary).to_string(index=False))
print("All 48 contexts preserve frozen means and retained-count/interval conservation.")

# Describe uncertainty in empirical coverage without treating dates/species as independent.
results["week"] = (pd.to_datetime(results.date) - pd.Timestamp("1970-01-05")).dt.days // 7
weeks = np.sort(results.week.unique())
frequency = np.random.default_rng(20261012).multinomial(
    len(weeks), np.full(len(weeks), 1 / len(weeks)), size=1200
)
coverage = []
for group_key, frame in pd.concat([results, results.assign(weather="all")]).groupby(
    ["assessment_group", "task", "method", "weather"]
):
    for level in [80, 95]:
        cluster = frame.groupby(["english_name", "week"]).agg(
            total=(f"covered{level}", "sum"), n=(f"covered{level}", "size")
        )
        totals = cluster.total.unstack().reindex(columns=weeks).fillna(0).to_numpy()
        counts = cluster.n.unstack().reindex(columns=weeks).fillna(0).to_numpy()
        draws = ((totals @ frequency.T) / (counts @ frequency.T)).mean(axis=0)
        coverage.append(
            dict(
                zip(["assessment_group", "task", "method", "weather"], group_key),
                nominal=level / 100,
                coverage=frame.groupby("english_name")[f"covered{level}"].mean().mean(),
                lower=np.quantile(draws, 0.025),
                upper=np.quantile(draws, 0.975),
            )
        )
pd.DataFrame(coverage).to_csv(OUT / "coverage_bootstrap.csv", index=False)

# Compare full-day interval performance against the same recent-data production refit.
reference = pd.read_csv("logs/gap-validation-benchmark.csv")
benchmark = full[keys + ["assessment_group", "weather", "count"]].merge(
    reference[keys + ["predicted", "q10", "q90", "q025", "q975"]], on=keys, validate="one_to_one"
)
benchmark["absolute_error"] = abs(benchmark["count"] - benchmark.predicted)
for level, lower_name, upper_name in [(80, "q10", "q90"), (95, "q025", "q975")]:
    lower, upper = benchmark[lower_name], benchmark[upper_name]
    benchmark[f"covered{level}"] = benchmark["count"].between(lower, upper)
    benchmark[f"width{level}"] = upper - lower
    benchmark[f"interval_score{level}"] = (
        upper
        - lower
        + 2
        / (1 - level / 100)
        * ((lower - benchmark["count"]).clip(lower=0) + (benchmark["count"] - upper).clip(lower=0))
    )
metrics = [
    "absolute_error",
    "covered80",
    "covered95",
    "width80",
    "width95",
    "interval_score80",
    "interval_score95",
]
combined = pd.concat(
    [full.assign(method="empirical_weather"), benchmark.assign(method="original_benchmark")],
    ignore_index=True,
)
combined = pd.concat([combined, combined.assign(weather="all")], ignore_index=True)
scores = combined.groupby(["assessment_group", "method", "weather", "english_name"])[
    metrics
].mean()
scores.to_csv(OUT / "benchmark_species_interval_scores.csv")
scores.groupby(["assessment_group", "method", "weather"]).mean().to_csv(
    OUT / "benchmark_interval_scores.csv"
)
