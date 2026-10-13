"""Score the ladder's arms on the realistic masks (README "Scores").

Run from the repository root after `run_steps.py`: uv run python
scripts/hierarchical/score_steps.py > logs/hierarchical/scores.log

Primary: season-total absolute relative error per species-year (the hidden part's error over the
year's counted total, per mask draw) with its signed bias, and daily-total error with its bias.
Species weighted equally, draws averaged. Also: wet and dry hidden days, day and early-end masks,
eras, 80% / 95% interval coverage of hidden days and of each year's hidden total. Differences from
`P` and from the step before with a paired bootstrap over years (all species and draws together).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from common import LOGS

BOOT = 200
LADDER = ["P", "R", "RS", "RSW", "D", "I"]
BASE = {"De": "D", "W": "RSW", "W2": "W", "W3": "W"}  # an arm off the ladder is compared with `P` and with this one
rng = np.random.default_rng(1)


def scores(days: pd.DataFrame, season: pd.DataFrame) -> pd.Series:
    """Scores of one arm, each species weighted equally."""
    d = days.assign(error=days.predicted - days["count"])
    sp = d.groupby("english_name").agg(
        mae=("error", lambda e: e.abs().mean()),
        error=("error", "sum"),
        abs_error=("error", lambda e: e.abs().sum()),
        count=("count", "sum"),
        cover80=("in80", "mean"),
        cover95=("in95", "mean"),
        above90=("above90", "mean"),
        below10=("below10", "mean"),
        above975=("above975", "mean"),
    )
    s = season.assign(relative=(season.predicted - season.hidden_count) / season.observed_truth)
    by = s.groupby("english_name")
    return pd.Series(
        {
            "season_abs_error": by.relative.apply(lambda r: r.abs().mean()).mean(),
            "season_bias": by.relative.mean().mean(),
            "season_cover80": by.in80.mean().mean(),
            "daily_mae": sp.mae.mean(),
            "daily_rel_abs_error": (sp.abs_error / sp["count"]).mean(),
            "daily_rel_bias": (sp.error / sp["count"]).mean(),
            "daily_cover80": sp.cover80.mean(),
            "daily_cover95": sp.cover95.mean(),
            "daily_above_q90": sp.above90.mean(),
            "daily_below_q10": sp.below10.mean(),
            "daily_above_q975": sp.above975.mean(),
        }
    )


def with_cover(f: pd.DataFrame, count: str) -> pd.DataFrame:
    has = f.q10.notna()  # the reference arms have no intervals
    # Counts are discrete and often zero: q10 is then 0 and a zero count is never below it, so
    # the central intervals over-cover by construction. Each tail is reported on its own; the
    # upper tail (count above q90, target 10%) is the one that tests calibration.
    return f.assign(
        in80=f[count].between(f.q10, f.q90).where(has),
        in95=f[count].between(f.q025, f.q975).where(has),
        above90=f[count].gt(f.q90).where(has),
        below10=f[count].lt(f.q10).where(has),
        above975=f[count].gt(f.q975).where(has),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=Path, default=LOGS / "steps")
    parser.add_argument("--out", type=Path, default=LOGS / "scores")
    parser.add_argument("--references", nargs="*", default=["H"], help="compared with P only")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    days = with_cover(
        pd.concat(pd.read_csv(p, parse_dates=["date"]) for p in args.steps.glob("*_days.csv")),
        "count",
    )
    season = with_cover(
        pd.concat(pd.read_csv(p) for p in args.steps.glob("*_season.csv")), "hidden_count"
    )
    season = season[season.observed_truth.gt(0)]
    days = days[days.arm.isin(LADDER + args.references)]
    season = season[season.arm.isin(LADDER + args.references)]
    arms = [a for a in LADDER + args.references if a in set(days.arm)]
    ladder = [a for a in arms if a in LADDER]
    complete = days.groupby(["english_name", "draw"]).arm.nunique().eq(len(arms))
    print(f"species x draws with every arm: {complete.sum()} of {len(complete)}")
    keep = complete[complete].index
    days = days.set_index(["english_name", "draw"]).loc[keep].reset_index()
    season = season.set_index(["english_name", "draw"]).loc[keep].reset_index()
    days["era"] = np.where(days.year < 2014, "1993-2013", "2014-2025")

    subsets = {
        "all": (days, season),
        "dry days": (days[days.weather.eq("dry")], None),
        "wet days": (days[days.weather.eq("wet")], None),
        "day masks": (days[days.kind.eq("day")], None),
        "early-end masks": (days[days.kind.eq("end")], None),
        "1993-2013": (days[days.era.eq("1993-2013")], season[season.year.lt(2014)]),
        "2014-2025": (days[days.era.eq("2014-2025")], season[season.year.ge(2014)]),
    }
    rows = []
    for label, (d, s) in subsets.items():
        if s is None:  # the season score of a subset: its days' errors over the year's total
            s = (
                d.groupby(["english_name", "draw", "arm", "year"], as_index=False)
                .agg(predicted=("predicted", "sum"), hidden_count=("count", "sum"))
                .merge(
                    season[["english_name", "draw", "arm", "year", "observed_truth"]],
                    on=["english_name", "draw", "arm", "year"],
                )
                .assign(in80=np.nan)
            )
        years = np.array(sorted(d.year.unique()))
        for i, arm in enumerate(arms):
            row = {"subset": label, "arm": arm, "n_days": int(d.arm.eq(arm).sum())}
            row |= scores(d[d.arm.eq(arm)], s[s.arm.eq(arm)]).to_dict()
            previous = ladder[ladder.index(arm) - 1] if arm in ladder[1:] else BASE.get(arm)
            for name, ref in (("P", "P"), ("previous", previous)):
                if arm == "P" or ref is None or (name == "previous" and ref == "P"):
                    continue
                draws = []
                for _ in range(BOOT):
                    weight = pd.Series(rng.choice(years, len(years))).value_counts()

                    def sample(f, a):
                        f = f[f.arm.eq(a) & f.year.isin(weight.index)]
                        return f.loc[f.index.repeat(f.year.map(weight))]

                    draws.append(
                        scores(sample(d, arm), sample(s, arm))
                        - scores(sample(d, ref), sample(s, ref))
                    )
                draws = pd.DataFrame(draws)
                for k in ("season_abs_error", "season_bias", "daily_mae", "daily_rel_bias"):
                    row[
                        f"{k}_vs_{name}"
                    ] = f"[{draws[k].quantile(0.025):+.4g}, {draws[k].quantile(0.975):+.4g}]"
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(args.out / "scores.csv", index=False)
    pd.set_option("display.width", 250)
    main_cols = ["arm", "n_days", "season_abs_error", "season_bias", "daily_mae", "daily_rel_bias"]
    main_cols += ["daily_above_q90", "daily_below_q10", "daily_above_q975", "season_cover80"]
    diff_cols = ["arm", *[c for c in table.columns if "_vs_" in c]]
    for label, t in table.groupby("subset", sort=False):
        print(f"\n## {label}\n")
        print(t[main_cols].to_string(index=False, float_format=lambda v: f"{v:.4g}"))
        print(t[diff_cols].dropna(how="all", subset=diff_cols[1:]).to_string(index=False))

    per_species = (
        season.assign(relative=(season.predicted - season.hidden_count) / season.observed_truth)
        .groupby(["english_name", "arm"])
        .relative.apply(lambda r: r.abs().mean())
        .unstack()[arms]
    )
    per_species.to_csv(args.out / "season_by_species.csv")
    print("\n## Season-total absolute relative error by species\n")
    print(per_species.to_string(float_format=lambda v: f"{v:.4f}"))
    fits = pd.concat(pd.read_csv(p) for p in args.steps.glob("*_fit.csv"))
    coef = fits.filter(like="beta_").groupby(fits.arm).median()
    print("\n## Median weather coefficients (per SD of the daily term)\n")
    print(coef.to_string(float_format=lambda v: f"{v:+.3f}"))
    print("\nMedian fit seconds:", fits.groupby("arm").seconds.median().round(1).to_dict())


if __name__ == "__main__":
    main()
