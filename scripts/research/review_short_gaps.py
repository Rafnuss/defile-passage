"""Compare practical retained-hour fills against frozen-day and original-model predictions."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/short-gaps-review")
OUT.mkdir(exist_ok=True)
KEYS = ["english_name", "fold", "date"]
operational = pd.read_csv("logs/short-gaps-uncertainty/predictions.csv")
assert operational.task.eq("three_hour_gap").all()
operational["method"] = operational.method.map(
    {"unadjusted": "retained_in_fit", "retained_adjusted": "retained_in_fit_plus_adjustment"}
)
truth = operational[operational.method.eq("retained_in_fit")].copy()
assert len(truth) == 4035
truth["retained_hours"] = truth.exposure_hours - truth.gap_hours
truth["retained_fraction"] = truth.retained_hours / truth.exposure_hours
truth["retained_rain"] = (truth.rain_exposure - truth.gap_rain) / truth.retained_hours
truth["retained_weather"] = np.where(truth.retained_rain >= 0.1, "wet", "dry")
truth["weather_pair"] = "retained_" + truth.retained_weather + "_gap_" + truth.weather
truth["retained_coverage"] = pd.cut(
    truth.retained_fraction,
    [0, 0.5, 0.75, 1],
    labels=["below_half", "half_to_three_quarters", "above_three_quarters"],
)
dates = pd.to_datetime(truth.date)
doy = dates.dt.dayofyear - (dates.dt.is_leap_year & dates.dt.month.gt(2))
truth["position"] = np.array(["early", "middle", "late"])[doy % 3]
truth["retained_zero"] = truth.retained_count.eq(0)
truth["missing_zero"] = truth["count"].eq(0)
truth["year"] = dates.dt.year
truth["week"] = (dates - pd.Timestamp("1970-01-05")).dt.days // 7
metadata = [
    "assessment_group",
    "weather",
    "gap_hours",
    "retained_count",
    "full_observed_count",
    "retained_hours",
    "retained_fraction",
    "weather_pair",
    "retained_coverage",
    "position",
    "retained_zero",
    "missing_zero",
    "year",
    "week",
]
frames = []
for sample in [
    operational,
    pd.read_csv("logs/simple-uncertainty/predictions.csv").query("task == 'three_hour_gap'"),
]:
    sample = sample.copy()
    sample["method"] = sample.method.replace(
        {"unadjusted": "day_excluded", "retained_adjusted": "day_excluded_plus_adjustment"}
    )
    sample = sample.merge(
        truth[KEYS + ["count", "gap_hours"]],
        on=KEYS,
        suffixes=("", "_truth"),
        validate="many_to_one",
    )
    assert np.array_equal(sample["count"], sample.count_truth)
    assert np.allclose(sample.gap_hours, sample.gap_hours_truth)
    frames.append(
        sample[KEYS + ["method", "count", "predicted", "lower80", "upper80", "lower95", "upper95"]]
    )
benchmark = pd.concat(
    [
        pd.read_csv(f"logs/short-gaps-benchmark-{panel}/production_held_out_days.csv")
        for panel in ["priority", "passerines"]
    ],
    ignore_index=True,
)
benchmark = benchmark.merge(
    truth[KEYS + ["count", "gap_hours"]], on=KEYS, suffixes=("", "_truth"), validate="one_to_one"
)
assert len(benchmark) == len(truth)
assert np.array_equal(benchmark["count"], benchmark.count_truth)
assert np.allclose(benchmark.hours, benchmark.gap_hours)
benchmark["method"] = "original_episode"
benchmark = benchmark.rename(
    columns={"q10": "lower80", "q90": "upper80", "q025": "lower95", "q975": "upper95"}
)
frames.append(
    benchmark[KEYS + ["method", "count", "predicted", "lower80", "upper80", "lower95", "upper95"]]
)
results = pd.concat(frames, ignore_index=True).merge(
    truth[KEYS + metadata], on=KEYS, validate="many_to_one"
)
assert len(results) == 5 * len(truth)
assert not results.duplicated(KEYS + ["method"]).any()
results["full_day_predicted"] = results.retained_count + results.predicted
results["absolute_error"] = abs(results["count"] - results.predicted)
results["bias"] = results.predicted - results["count"]
for level in [80, 95]:
    lower, upper = results[f"lower{level}"], results[f"upper{level}"]
    results[f"covered{level}"] = results["count"].between(lower, upper)
    results[f"width{level}"] = upper - lower
    results[f"interval_score{level}"] = (
        upper
        - lower
        + 2
        / (1 - level / 100)
        * ((lower - results["count"]).clip(lower=0) + (results["count"] - upper).clip(lower=0))
    )
    results[f"full_day_lower{level}"] = results.retained_count + lower
    results[f"full_day_upper{level}"] = results.retained_count + upper
    assert np.allclose(
        results.full_day_predicted - results.full_observed_count,
        results.predicted - results["count"],
    )
results.to_csv(OUT / "predictions.csv", index=False)
metrics = [
    "absolute_error",
    "bias",
    "covered80",
    "covered95",
    "width80",
    "width95",
    "interval_score80",
    "interval_score95",
]
summary = pd.concat([results, results.assign(weather="all")], ignore_index=True)
species = summary.groupby(["assessment_group", "method", "weather", "english_name"])[
    metrics
].mean()
species.to_csv(OUT / "species_scores.csv")
species.groupby(["assessment_group", "method", "weather"]).mean().to_csv(OUT / "group_scores.csv")
summary.groupby(["assessment_group", "method", "weather"])[["count", "predicted"]].sum().to_csv(
    OUT / "totals.csv"
)
for column in [
    "position",
    "weather_pair",
    "retained_coverage",
    "retained_zero",
    "missing_zero",
    "year",
]:
    species = results.groupby(
        ["assessment_group", "method", column, "english_name"], observed=True
    )[metrics].mean()
    species.to_csv(OUT / f"species_{column}_scores.csv")
    strata = species.groupby(["assessment_group", "method", column], observed=True).mean()
    counts = results.groupby(["assessment_group", "method", column], observed=True).agg(
        days=("count", "size"), species=("english_name", "nunique")
    )
    strata.join(counts).to_csv(OUT / f"{column}_scores.csv")


# Resample calendar weeks jointly across species and methods.
weeks = np.sort(results.week.unique())
frequency = np.random.default_rng(20261012).multinomial(
    len(weeks), np.full(len(weeks), 1 / len(weeks)), size=1200
)
contrasts = [
    ("retained_in_fit", "day_excluded"),
    ("retained_in_fit_plus_adjustment", "retained_in_fit"),
    ("retained_in_fit", "original_episode"),
    ("retained_in_fit_plus_adjustment", "original_episode"),
]
paired_scores = []
for candidate, reference in contrasts:
    a = results[results.method.eq(candidate)]
    b = results[results.method.eq(reference)]
    paired = a.merge(
        b[KEYS + ["absolute_error"]], on=KEYS, suffixes=("", "_reference"), validate="one_to_one"
    )
    paired["difference"] = paired.absolute_error - paired.absolute_error_reference
    for (group, weather), frame in pd.concat([paired, paired.assign(weather="all")]).groupby(
        ["assessment_group", "weather"]
    ):
        cluster = frame.groupby(["english_name", "week"]).agg(
            total=("difference", "sum"), n=("difference", "size")
        )
        totals = cluster.total.unstack().reindex(columns=weeks).fillna(0).to_numpy()
        counts = cluster.n.unstack().reindex(columns=weeks).fillna(0).to_numpy()
        draws = ((totals @ frequency.T) / (counts @ frequency.T)).mean(axis=0)
        species = frame.groupby("english_name")[
            ["absolute_error", "absolute_error_reference"]
        ].mean()
        paired_scores.append(
            dict(
                candidate=candidate,
                reference=reference,
                assessment_group=group,
                weather=weather,
                days=len(frame),
                candidate_mae=species.absolute_error.mean(),
                reference_mae=species.absolute_error_reference.mean(),
                difference=(species.absolute_error - species.absolute_error_reference).mean(),
                lower=np.quantile(draws, 0.025),
                upper=np.quantile(draws, 0.975),
                median_species_ratio=(
                    species.absolute_error / species.absolute_error_reference
                ).median(),
                species_better=int(
                    (species.absolute_error < species.absolute_error_reference).sum()
                ),
            )
        )
pd.DataFrame(paired_scores).to_csv(OUT / "paired_scores.csv", index=False)
print(pd.read_csv(OUT / "group_scores.csv").to_string(index=False))
print(
    pd.DataFrame(paired_scores)
    .query("assessment_group == 'core_large_birds'")
    .to_string(index=False)
)
print("Verified matching counts and exposure for all 4035 short gaps and five methods.")
