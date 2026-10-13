"""Re-score the research's saved calendar-mask predictions with the hierarchical line's scores.

Run from the repository root:
uv run python scripts/hierarchical/rescore_calendar.py > logs/hierarchical/rescore.log

No fitting: the point predictions saved by the research runs, on their own masks (historical
1993-2021, one fold; recent 2022-2025, three folds). Every method is scored on the targets all
methods share, so the rows compare like with like. Scores (README "Scores"): season-total absolute
relative error and its signed bias per species-year, and daily-total error and bias, overall and on
wet and dry days; species weighted equally; paired bootstrap over years (historical) and weeks
(recent) for the difference from production.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from defile_explore.release import MAIN_CATEGORY, parse_surveys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/hierarchical/rescore"
OUT.mkdir(parents=True, exist_ok=True)
DATASET = ROOT / "data/count/dataset"
SOURCES = {  # saved predictions: file -> methods taken from it
    "logs/original-rain/predictions.csv": ["original_episode", "original_rain", "weather_soaring"],
    "logs/history-episode/predictions.csv": ["weather_mean", "weather_episode"],
    "logs/daily-passage/predictions.csv": ["weather_daily"],
}
LABELS = {
    "original_episode": "production (P)",
    "original_rain": "hybrid: production + rain (R)",
    "weather_soaring": "hourly weather mean, radiation/cloud",
    "weather_mean": "hourly weather mean",
    "weather_episode": "hourly weather + episode",
    "weather_daily": "daily-passage AR(1)",
}
BOOT = 2000
KEYS = ["task", "english_name", "fold", "date"]
rng = np.random.default_rng(1)

frames = []
for path, methods in SOURCES.items():
    p = pd.read_csv(ROOT / path)
    frames.append(
        p[p.method.isin(methods)][[*KEYS, "count", "weather", "year", "method", "predicted"]]
    )
pred = pd.concat(frames, ignore_index=True)
pred["date"] = pd.to_datetime(pred.date)
assert not pred.duplicated([*KEYS, "method"]).any()

# The same production predictions are saved by every run: check they agree where they overlap.
for path in ("logs/history-episode/predictions.csv", "logs/daily-passage/predictions.csv"):
    other = pd.read_csv(ROOT / path).query("method == 'original_episode'")
    other["date"] = pd.to_datetime(other.date)
    both = other.merge(pred.query("method == 'original_episode'"), on=KEYS)
    print(
        f"{path}: production max difference {abs(both.predicted_x - both.predicted_y).max():.3g}"
    )

# Year totals of the counts, the denominator of the season error.
truth = pd.read_csv(ROOT / "logs/original-rain/season_errors.csv").drop_duplicates(
    ["english_name", "year"]
)[["english_name", "year", "observed_truth"]]
surveys = parse_surveys(pd.read_csv(DATASET / "survey.csv", low_memory=False))
counts = pd.read_csv(DATASET / "count.csv", low_memory=False)
taxa = pd.read_csv(DATASET / "taxonomy.csv")[["taxon_id", "english_name"]]
recent = (
    counts[counts.count_category.eq(MAIN_CATEGORY)]
    .merge(surveys[["survey_id", "date"]], on="survey_id")
    .merge(taxa, on="taxon_id")
    .assign(year=lambda f: f.date.dt.year)
    .query("year >= 2022 and year <= 2025")
    .groupby(["english_name", "year"], as_index=False)["count"]
    .sum()
    .rename(columns={"count": "observed_truth"})
)
truth = pd.concat([truth, recent], ignore_index=True)


def scores(f: pd.DataFrame) -> pd.Series:
    """Scores of one method on a set of targets, each species weighted equally."""
    f = f.assign(error=f.predicted - f["count"])
    sp = f.groupby("english_name").agg(
        abs_error=("error", lambda e: e.abs().sum()),
        error=("error", "sum"),
        count=("count", "sum"),
        mae=("error", lambda e: e.abs().mean()),
    )
    season = f.groupby(["english_name", "year", "fold"], as_index=False)["error"].sum()
    season = season.merge(truth, on=["english_name", "year"], validate="many_to_one")
    season = season[season.observed_truth.gt(0)]
    season["relative"] = season.error / season.observed_truth
    by_species = season.groupby("english_name").relative
    return pd.Series(
        {
            "season_abs_error": by_species.apply(lambda r: r.abs().mean()).mean(),
            "season_bias": by_species.mean().mean(),
            "daily_mae": sp.mae.mean(),
            "daily_rel_abs_error": (sp.abs_error / sp["count"]).mean(),
            "daily_rel_bias": (sp.error / sp["count"]).mean(),
        }
    )


def paired(f: pd.DataFrame, method: str, unit: pd.Series) -> dict:
    """Bootstrap interval of a method's scores minus production's, resampling `unit` (years or
    weeks) jointly for both and across species."""
    units = unit.unique()
    rows = []
    for _ in range(BOOT // 10):
        pick = rng.choice(units, len(units))
        weight = pd.Series(pick).value_counts()
        sample = f.loc[unit.isin(weight.index)]
        sample = sample.loc[sample.index.repeat(unit[sample.index].map(weight))]
        rows.append(
            scores(sample[sample.method.eq(method)])
            - scores(sample[sample.method.eq("original_episode")])
        )
    draws = pd.DataFrame(rows)
    return {f"{k}_diff_lo": draws[k].quantile(0.025) for k in draws} | {
        f"{k}_diff_hi": draws[k].quantile(0.975) for k in draws
    }


tables = []
for target_set, methods in (
    ("all methods", list(LABELS)),
    ("without daily-passage", [m for m in LABELS if m != "weather_daily"]),
):
    sub = pred[pred.method.isin(methods)]
    shared = sub.groupby(KEYS).method.nunique().eq(len(methods))
    sub = sub.set_index(KEYS).loc[shared[shared].index].reset_index()
    for task, t in sub.groupby("task"):
        unit = t.year if task == "historical" else t.date.dt.isocalendar().week + 100 * t.year
        for weather in ("all", "dry", "wet"):
            w = t if weather == "all" else t[t.weather.eq(weather)]
            wu = unit[w.index]
            for method in methods:
                row = {
                    "targets": target_set,
                    "task": task,
                    "days": weather,
                    "method": LABELS[method],
                }
                row |= scores(w[w.method.eq(method)]).to_dict()
                row["n"] = int(w.method.eq(method).sum())
                if method != "original_episode":
                    row |= paired(w, method, wu)
                tables.append(row)
table = pd.DataFrame(tables)
table.to_csv(OUT / "scores.csv", index=False)
pd.set_option("display.width", 250)
cols = ["method", "n", "season_abs_error", "season_bias", "daily_mae", "daily_rel_bias"]
for (target_set, task, days), t in table.groupby(["targets", "task", "days"], sort=False):
    print(f"\n## {target_set}, {task}, {days} days\n")
    print(t[cols].to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    diff = t.dropna(subset=["season_abs_error_diff_lo"])
    print(
        diff[["method"]]
        .assign(
            season_diff=diff.apply(
                lambda r: f"[{r.season_abs_error_diff_lo:+.4f}, {r.season_abs_error_diff_hi:+.4f}]",
                axis=1,
            ),
            mae_diff=diff.apply(
                lambda r: f"[{r.daily_mae_diff_lo:+.2f}, {r.daily_mae_diff_hi:+.2f}]", axis=1
            ),
        )
        .to_string(index=False)
    )
