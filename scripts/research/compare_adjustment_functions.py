"""Diagnose signed errors and compare training-selected adjustment forms on frozen means."""

from pathlib import Path

import numpy as np
import pandas as pd
from adjustment_functions import PARAMETERS, adjusted_count

OUT = Path("logs/adjustment-functions")
OUT.mkdir(exist_ok=True)
KEYS = ["english_name", "fold", "date"]
previous = pd.read_csv("logs/short-gaps-review/predictions.csv")
base = previous[previous.method.eq("retained_in_fit")].copy()
current = previous[previous.method.eq("retained_in_fit_plus_adjustment")].copy()
current = current.merge(
    base[KEYS + ["predicted"]], on=KEYS, suffixes=("", "_base"), validate="one_to_one"
)
current["added_prediction"] = current.predicted - current.predicted_base
core = current[current.assessment_group.eq("core_large_birds")]
for columns, name in [
    (["english_name"], "species"),
    (["year"], "year"),
    (["english_name", "year"], "species_year"),
    (["position"], "position"),
    (["missing_zero"], "missing_zero"),
]:
    scores = core.groupby(columns).agg(
        days=("count", "size"),
        observed=("count", "sum"),
        predicted=("predicted", "sum"),
        unadjusted=("predicted_base", "sum"),
        error=("bias", "sum"),
        added_prediction=("added_prediction", "sum"),
        mae=("absolute_error", "mean"),
    )
    scores.to_csv(OUT / f"diagnosis_{name}.csv")
core.sort_values("bias", ascending=False).to_csv(OUT / "diagnosis_events.csv", index=False)

# Summarize missing-hour predictions in daylight-relative bins without allocating coarse counts.
hours = []
for panel in ["priority", "passerines"]:
    folder = Path(f"logs/short-gaps-design-{panel}")
    outputs = pd.read_csv(f"logs/short-gaps-{panel}/predictions.csv")
    for context in pd.read_csv(folder / "manifest.csv").itertuples():
        components = pd.read_csv(folder / f"{context.key}_components.csv")
        sample = outputs[
            outputs.english_name.eq(context.english_name) & outputs.fold.eq(context.fold)
        ]
        sample = sample.merge(
            components[["observation_id", "tau"]], on="observation_id", validate="one_to_one"
        )
        sample = sample.merge(
            current[KEYS + ["predicted", "predicted_base", "assessment_group"]],
            on=KEYS,
            suffixes=("_hour", "_day"),
            validate="many_to_one",
        )
        sample["adjusted_hour"] = (
            sample.predicted_hour * sample.predicted_day / sample.predicted_base
        )
        hours.append(sample)
hours = pd.concat(hours, ignore_index=True)
hours["daylight_bin"] = pd.cut(
    hours.tau,
    [-np.inf, 0, 0.25, 0.5, 0.75, 1, np.inf],
    labels=[
        "before_dawn",
        "first_quarter",
        "second_quarter",
        "third_quarter",
        "last_quarter",
        "after_dusk",
    ],
)
hours[hours.assessment_group.eq("core_large_birds")].groupby(
    ["english_name", "daylight_bin"], observed=True
).agg(
    intervals=("count", "size"),
    observed=("count", "sum"),
    unadjusted=("predicted_hour", "sum"),
    adjusted=("adjusted_hour", "sum"),
).to_csv(
    OUT / "diagnosis_daylight.csv"
)

# Calibration rows contain only pseudo gaps on complete non-target days.
calibration = pd.read_csv("logs/short-gaps-uncertainty/calibration.csv")
assert calibration.task.eq("three_hour_gap").all()
truth = pd.read_csv("logs/short-gaps-uncertainty/predictions.csv").query("method == 'unadjusted'")
truth = truth.merge(
    base[
        KEYS
        + [
            "assessment_group",
            "year",
            "position",
            "retained_fraction",
            "retained_zero",
            "missing_zero",
        ]
    ],
    on=KEYS,
    suffixes=("", "_reference"),
    validate="one_to_one",
)
assert len(truth) == 4035
predictions, selections = [], []
for (species, fold), cal in calibration.groupby(["english_name", "fold"]):
    target = truth[truth.english_name.eq(species) & truth.fold.eq(fold)].copy()
    for function, parameters in PARAMETERS.items():
        candidates = np.column_stack(
            [
                adjusted_count(
                    cal.missing_mean.to_numpy(),
                    cal.retained_mean.to_numpy(),
                    cal.retained_count.to_numpy(),
                    function,
                    p,
                )
                for p in parameters
            ]
        )
        residual = candidates - cal.missing_count.to_numpy()[:, None]
        for loss in ["mae", "mse"]:
            score = np.mean(abs(residual) if loss == "mae" else residual**2, axis=0)
            parameter = parameters[np.argmin(score)]
            output = target.copy()
            output["method"] = function + "_" + loss
            output["predicted"] = adjusted_count(
                target.missing_mean,
                target.retained_mean,
                target.retained_count,
                function,
                parameter,
            )
            predictions.append(output)
            selections.append(
                dict(
                    english_name=species,
                    fold=fold,
                    function=function,
                    loss=loss,
                    parameter=parameter,
                    calibration_score=score.min(),
                )
            )
pd.DataFrame(selections).to_csv(OUT / "selected_parameters.csv", index=False)
results = pd.concat(predictions, ignore_index=True)
results = pd.concat(
    [results, previous[previous.method.isin(["retained_in_fit", "original_episode"])]],
    ignore_index=True,
)
# Alternative point rules need their own interval calibration; do not carry old bounds forward.
results = results[
    KEYS
    + [
        "method",
        "assessment_group",
        "weather",
        "year",
        "position",
        "retained_fraction",
        "retained_zero",
        "missing_zero",
        "count",
        "predicted",
        "retained_count",
    ]
].copy()
assert (
    len(results) == 10 * 4035
    and np.isfinite(results.predicted).all()
    and results.predicted.ge(0).all()
)
results["full_day_predicted"] = results.retained_count + results.predicted
results["absolute_error"] = abs(results.predicted - results["count"])
results["squared_error"] = (results.predicted - results["count"]) ** 2
results["bias"] = results.predicted - results["count"]
# The old MAE selection is reproduced exactly, isolating changes from selection errors.
check = results[results.method.eq("count_shrinkage_mae")].merge(
    current[KEYS + ["predicted"]], on=KEYS, suffixes=("", "_old"), validate="one_to_one"
)
assert np.allclose(check.predicted, check.predicted_old)
results.to_csv(OUT / "predictions.csv", index=False)
summary = pd.concat([results, results.assign(weather="all")], ignore_index=True)
species = summary.groupby(["assessment_group", "method", "weather", "english_name"]).agg(
    days=("count", "size"),
    mae=("absolute_error", "mean"),
    mse=("squared_error", "mean"),
    observed=("count", "sum"),
    predicted=("predicted", "sum"),
    bias=("bias", "sum"),
)
species["rmse"] = np.sqrt(species.mse)
species["abs_bias_pct"] = abs(100 * species.bias / species.observed)
species.to_csv(OUT / "species_scores.csv")
macro = species.groupby(["assessment_group", "method", "weather"])[["mae", "rmse"]].mean()
totals = summary.groupby(["assessment_group", "method", "weather"])[
    ["count", "predicted", "bias"]
].sum()
macro = macro.join(totals)
macro["median_abs_species_bias_pct"] = species.groupby(
    ["assessment_group", "method", "weather"]
).abs_bias_pct.median()
macro["bias_pct"] = 100 * macro.bias / macro["count"]
macro.to_csv(OUT / "group_scores.csv")
summary.groupby(["assessment_group", "method", "weather", "year"]).agg(
    observed=("count", "sum"), predicted=("predicted", "sum"), bias=("bias", "sum")
).to_csv(OUT / "year_totals.csv")
summary[summary.missing_zero].groupby(["assessment_group", "method", "weather"]).agg(
    days=("count", "size"), predicted=("predicted", "sum")
).to_csv(OUT / "zero_totals.csv")
# Common-week paired comparisons remain exploratory on these reused observations.
results["week"] = (pd.to_datetime(results.date) - pd.Timestamp("1970-01-05")).dt.days // 7
weeks = np.sort(results.week.unique())
frequency = np.random.default_rng(20261012).multinomial(
    len(weeks), np.full(len(weeks), 1 / len(weeks)), size=1200
)
paired_scores = []
for method, sample in results.groupby("method"):
    if method in ["retained_in_fit", "original_episode"]:
        continue
    for reference in ["count_shrinkage_mae", "original_episode"]:
        original = results[results.method.eq(reference)]
        paired = sample.merge(
            original[KEYS + ["absolute_error"]],
            on=KEYS,
            suffixes=("", "_reference"),
            validate="one_to_one",
        )
        paired["difference"] = paired.absolute_error - paired.absolute_error_reference
        for (group, weather), frame in pd.concat([paired, paired.assign(weather="all")]).groupby(
            ["assessment_group", "weather"]
        ):
            clusters = frame.groupby(["english_name", "week"]).agg(
                total=("difference", "sum"), n=("difference", "size")
            )
            totals = clusters.total.unstack().reindex(columns=weeks).fillna(0).to_numpy()
            counts = clusters.n.unstack().reindex(columns=weeks).fillna(0).to_numpy()
            draws = ((totals @ frequency.T) / (counts @ frequency.T)).mean(axis=0)
            scores = frame.groupby("english_name")[
                ["absolute_error", "absolute_error_reference"]
            ].mean()
            paired_scores.append(
                dict(
                    method=method,
                    reference=reference,
                    assessment_group=group,
                    weather=weather,
                    difference=(scores.absolute_error - scores.absolute_error_reference).mean(),
                    lower=np.quantile(draws, 0.025),
                    upper=np.quantile(draws, 0.975),
                    median_species_ratio=(
                        scores.absolute_error / scores.absolute_error_reference
                    ).median(),
                    species_better=int(
                        (scores.absolute_error < scores.absolute_error_reference).sum()
                    ),
                )
            )
pd.DataFrame(paired_scores).to_csv(OUT / "paired_scores.csv", index=False)
print(macro.loc["core_large_birds"].to_string())
print(
    "Verified: unchanged GAMs, training-only parameter selection and exact reproduction of current adjustment."
)
