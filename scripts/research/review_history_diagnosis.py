"""Review paired recent holdouts after changing historical training support."""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("logs/history-diagnosis")
manifest = pd.read_csv(OUT / "input/manifest.csv")
results, diagnostics, effects, shapes, failures = [], [], [], [], []
for context in manifest.itertuples():
    folder = OUT / "fits" / context.key
    if not (folder / "assessment.csv").exists():
        failures.append(dict(key=context.key, english_name=context.english_name, arm=context.arm))
        continue
    results.append(pd.read_csv(folder / "assessment.csv"))
    diagnostic = pd.read_csv(folder / "diagnostics.csv").assign(arm=context.arm)
    diagnostics.append(diagnostic)
    fit = np.load(folder / f"{context.key}_fit.npz")
    beta = fit["coefficients"]
    scale = pd.read_csv(OUT / f"design/{context.key}_weather_scale.csv").set_index("term").scale
    effects.append(
        dict(
            english_name=context.english_name,
            fold=context.fold,
            arm=context.arm,
            smoothing=float(fit["smoothing"]),
            log_rain=beta[1],
            rain_hinge=beta[15] / scale.rain_hinge,
            wind_u=beta[16] / scale.wind_u,
            wind_v=beta[17] / scale.wind_v,
            night=beta[18],
            rain_3mm_ratio=np.exp(beta[1] * np.log(4) + beta[15] / scale.rain_hinge * np.log(2)),
        )
    )
    X = np.loadtxt(OUT / f"design/{context.key}_year_weather_X.csv", delimiter=",")
    rows = pd.read_csv(OUT / f"design/{context.key}_components.csv")
    recent = rows.source.eq("recent").to_numpy()
    season = pd.DataFrame(
        dict(coordinate=rows.loc[recent, "doy"], value=np.exp(X[recent, 2:9] @ beta[2:9]))
    )
    season = season.groupby("coordinate", as_index=False).value.mean()
    season["value"] /= season.value.mean()
    season["effect"] = "season"
    hour = np.arange(24) + 0.5
    phase = 2 * np.pi * hour / 24
    harmonics = np.column_stack([f(n * phase) for n in range(1, 4) for f in [np.sin, np.cos]])
    clock = pd.DataFrame(dict(coordinate=hour, value=np.exp(harmonics @ beta[9:15])))
    clock["value"] /= clock.value.mean()
    clock["effect"] = "clock"
    shapes.append(
        pd.concat([season, clock]).assign(
            english_name=context.english_name, fold=context.fold, arm=context.arm
        )
    )
pd.DataFrame(failures, columns=["key", "english_name", "arm"]).to_csv(
    OUT / "failures.csv", index=False
)
a = pd.concat(results, ignore_index=True)
a["error"] = a.predicted - a["count"]
a["absolute_error"] = abs(a.error)
a["zero_truth"] = a["count"].eq(0)
a["week"] = (pd.to_datetime(a.date) - pd.Timestamp("1970-01-05")).dt.days // 7
pairs = a.pivot(index=["date", "english_name", "fold"], columns="arm", values="count")
assert pairs.notna().all().all() and pairs.sub(pairs.recent, axis=0).eq(0).all().all()
a.to_csv(OUT / "predictions.csv", index=False)
summary = pd.concat([a, a.assign(weather="all")], ignore_index=True)
species = summary.groupby(["english_name", "arm", "weather"]).agg(
    mae=("absolute_error", "mean"), bias=("error", "mean")
)
species.to_csv(OUT / "species_scores.csv")
species.groupby(["arm", "weather"]).mean().to_csv(OUT / "group_scores.csv")
summary.groupby(["year", "english_name", "arm", "weather"]).absolute_error.mean().groupby(
    ["year", "arm", "weather"]
).mean().to_csv(OUT / "year_scores.csv")
a.groupby(["english_name", "arm", "weather", "zero_truth"]).agg(
    mae=("absolute_error", "mean"), bias=("error", "mean"), count=("date", "size")
).to_csv(OUT / "zero_positive_scores.csv")
bootstrap = []
rng = np.random.default_rng(20261012)
for weather, sample in summary.groupby("weather"):
    errors = sample.pivot(
        index=["week", "date", "english_name", "fold"], columns="arm", values="absolute_error"
    )
    for arm in ["recent_coarse", "late_history", "all_history"]:
        difference = (errors[arm] - errors.recent).rename("difference").reset_index()
        sums = difference.groupby(["week", "english_name"]).difference.agg(["sum", "count"])
        weeks, names = sorted(difference.week.unique()), sorted(difference.english_name.unique())
        sums = sums.reindex(
            pd.MultiIndex.from_product([weeks, names], names=["week", "english_name"]),
            fill_value=0,
        )
        total = sums["sum"].to_numpy().reshape(len(weeks), len(names))
        count = sums["count"].to_numpy().reshape(len(weeks), len(names))
        weights = rng.multinomial(len(weeks), np.repeat(1 / len(weeks), len(weeks)), size=2000)
        draw = np.nanmean(
            (weights @ total) / np.where(weights @ count > 0, weights @ count, np.nan), axis=1
        )
        bootstrap.append(
            dict(
                weather=weather,
                arm=arm,
                difference=np.mean(total.sum(axis=0) / count.sum(axis=0)),
                lower=np.quantile(draw, 0.025),
                upper=np.quantile(draw, 0.975),
            )
        )
pd.DataFrame(bootstrap).to_csv(OUT / "paired_scores.csv", index=False)
pd.concat(diagnostics, ignore_index=True).to_csv(OUT / "diagnostics.csv", index=False)
pd.DataFrame(effects).to_csv(OUT / "physical_effects.csv", index=False)
pd.concat(shapes, ignore_index=True).to_csv(OUT / "normalized_shapes.csv", index=False)
print("Completed", len(results), "of", len(manifest), "; failures", len(failures))
print(pd.read_csv(OUT / "group_scores.csv").to_string(index=False))
print(pd.DataFrame(bootstrap).to_string(index=False))
