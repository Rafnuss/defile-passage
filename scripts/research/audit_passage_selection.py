"""Audit saved training-fold selection targets without fitting or outer scoring."""

from pathlib import Path

import numpy as np
import pandas as pd

SOURCE = Path("logs/count-balanced-passage")
OUT = Path("logs/passage-selection-audit")
OUT.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
checks = pd.read_csv(SOURCE / "cv_checks.csv")
assert len(checks) == len(manifest) * 12 and checks.numerical_pass.all()
metrics, years, blocks, target_metrics = [], [], [], []
for context in manifest.itertuples():
    folder = SOURCE / "fits" / context.key
    saved = pd.read_csv(folder / "amplitude_scores.csv")
    reference = pd.read_csv(folder / "cv_daily_sd0.csv")
    for sd in saved.sd:
        # Preserve the original integer filenames at both endpoints of the grid.
        label = str(int(sd)) if sd in [0, 1] else str(sd)
        frame = pd.read_csv(folder / f"cv_daily_sd{label}.csv")
        assert frame.date.equals(reference.date) and np.array_equal(
            frame["count"], reference["count"]
        )
        dates = pd.to_datetime(frame.date)
        frame["year"] = dates.dt.year
        frame["block"] = (dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7
        frame["error"] = frame.predicted - frame["count"]
        annual = frame.groupby("year")[["count", "predicted", "error"]].sum()
        assert annual["count"].gt(0).all()
        annual["relative_bias"] = annual.error / annual["count"]
        weekly = frame.groupby("block")[["count", "predicted", "error"]].sum()
        daily_mae = abs(frame.error).mean()
        assert np.isclose(
            daily_mae, saved.loc[saved.sd.eq(sd), "daily_mae"].iloc[0], atol=1e-9, rtol=1e-12
        )
        metrics.append(
            dict(
                key=context.key,
                task=context.task,
                english_name=context.english_name,
                sd=sd,
                daily_mae=daily_mae,
                year_total_mare=abs(annual.relative_bias).mean(),
                week_total_error=abs(weekly.error).sum() / frame["count"].sum(),
                signed_total_bias=frame.error.sum() / frame["count"].sum(),
                days=len(frame),
                count=frame["count"].sum(),
                outer_pair_complete=(folder / "assessment.csv").exists(),
            )
        )
        target = frame[
            frame.year.le(2021) if context.task == "historical" else frame.year.ge(2022)
        ]
        target_year = target.groupby("year")[["count", "error"]].sum()
        target_week = target.groupby("block")[["count", "error"]].sum()
        assert target_year["count"].gt(0).all()
        target_metrics.append(
            dict(
                key=context.key,
                sd=sd,
                daily_mae=abs(target.error).mean(),
                year_total_mare=abs(target_year.error / target_year["count"]).mean(),
                week_total_error=abs(target_week.error).sum() / target["count"].sum(),
                signed_total_bias=target.error.sum() / target["count"].sum(),
            )
        )
        years.append(
            annual.reset_index().assign(
                key=context.key, task=context.task, english_name=context.english_name, sd=sd
            )
        )
        blocks.append(
            weekly.reset_index().assign(
                key=context.key, task=context.task, english_name=context.english_name, sd=sd
            )
        )
metrics = pd.DataFrame(metrics)
metrics.to_csv(OUT / "grid_metrics.csv", index=False)
pd.concat(years, ignore_index=True).to_csv(OUT / "year_errors.csv", index=False)
pd.concat(blocks, ignore_index=True).to_csv(OUT / "week_errors.csv", index=False)
choices = []
for key, frame in metrics.groupby("key"):
    frame = frame.sort_values("sd")
    for rule, column in [
        ("daily_mae", "daily_mae"),
        ("year_total", "year_total_mare"),
        ("week_total", "week_total_error"),
        ("no_state", "sd"),
    ]:
        chosen = frame.loc[frame[column].idxmin()].to_dict()
        chosen["rule"] = rule
        choices.append(chosen)
choices = pd.DataFrame(choices)
choices.to_csv(OUT / "choices.csv", index=False)
target_choices = choices[["key", "task", "english_name", "rule", "sd"]].merge(
    pd.DataFrame(target_metrics), on=["key", "sd"], validate="many_to_one"
)
target_choices.to_csv(OUT / "target_era_choices.csv", index=False)
score_columns = ["daily_mae", "year_total_mare", "week_total_error", "signed_total_bias"]
target_choices.groupby(["task", "english_name", "rule"])[score_columns].mean().groupby(
    ["task", "rule"]
).mean().to_csv(OUT / "target_era_macro.csv")
choices.groupby(["task", "english_name", "rule"])[score_columns].mean().to_csv(
    OUT / "species_scores.csv"
)
choices.groupby(["task", "english_name", "rule"])[score_columns].mean().groupby(
    ["task", "rule"]
).mean().to_csv(OUT / "macro_scores.csv")
wide = choices.pivot(
    index=["key", "task", "english_name"], columns="rule", values=["sd"] + score_columns
)
comparison = pd.DataFrame(index=wide.index)
comparison["daily_sd"] = wide["sd"].daily_mae
comparison["year_sd"] = wide["sd"].year_total
comparison["week_sd"] = wide["sd"].week_total
comparison["year_minimum_disagrees"] = comparison.daily_sd.ne(comparison.year_sd)
comparison["week_minimum_disagrees"] = comparison.daily_sd.ne(comparison.week_sd)
comparison["daily_gain"] = wide["daily_mae"].no_state - wide["daily_mae"].daily_mae
comparison["year_change"] = wide["year_total_mare"].daily_mae - wide["year_total_mare"].no_state
comparison["week_change"] = wide["week_total_error"].daily_mae - wide["week_total_error"].no_state
comparison["daily_better_year_worse"] = comparison.daily_gain.gt(1e-9) & comparison.year_change.gt(
    1e-12
)
comparison.to_csv(OUT / "selection_conflicts.csv")
comparison.groupby("task").agg(
    contexts=("daily_sd", "size"),
    positive_daily_sd=("daily_sd", lambda x: x.gt(0).sum()),
    yearly_disagreements=("year_minimum_disagrees", "sum"),
    weekly_disagreements=("week_minimum_disagrees", "sum"),
    daily_better_year_worse=("daily_better_year_worse", "sum"),
).to_csv(OUT / "conflict_summary.csv")
choices.groupby(["task", "rule", "sd"]).size().rename("contexts").to_csv(OUT / "selected_sd.csv")
# Selection replay is independent of outer hidden outcomes.
for key, frame in choices[choices.rule.eq("daily_mae")].groupby("key"):
    folder = SOURCE / "fits" / key
    if (folder / "weather_daily_fit.npz").exists():
        assert np.load(folder / "weather_daily_fit.npz")["sd"] == frame.sd.iloc[0]
print("Audited 160 saved grid settings; daily selection matches all saved outer endpoints.")
print(pd.read_csv(OUT / "macro_scores.csv").to_string(index=False))
print(pd.read_csv(OUT / "conflict_summary.csv").to_string(index=False))
