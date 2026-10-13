"""Fit unchanged mean models, original benchmark, and one prespecified retained update."""

import argparse
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from compare_production import interval_slots, training_profile
from scipy.sparse import csr_matrix
from simple_rate_model import fit_rate
from simple_rate_prediction import count_interval, retained_prediction, select_retained_strength

from defile_explore import profile as P
from defile_explore import trend as T

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "logs/historical-transfer"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--keys", nargs="+")
parser.add_argument("--shard", nargs=2, type=int, metavar=("INDEX", "COUNT"))
parser.add_argument("--resume", action="store_true")
args = parser.parse_args()
manifest = pd.read_csv(OUT / "design/manifest.csv")
if args.keys:
    manifest = manifest[manifest.key.isin(args.keys)]
if args.shard:
    species_index = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
    manifest = manifest[manifest.english_name.map(species_index) % args.shard[1] == args.shard[0]]
profile_cache = {}
benchmarked = set()
for context in manifest.itertuples():
    started = perf_counter()
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    if args.resume and (folder / "assessment.csv").exists():
        continue
    with (folder / "run.log").open("w") as log:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/research/fit_simple_rate.py",
                "--input",
                str(OUT / "design"),
                "--out",
                str(folder),
                "--variant",
                "year_weather",
                "--keys",
                key,
                "--select-smoothing",
                "--variance-power",
                "1.5",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    if result.returncode:
        print(key, "FAILED mean fit", flush=True)
        continue
    rows = pd.read_csv(OUT / f"design/{key}_components.csv")
    observations = pd.read_csv(OUT / f"design/{key}_observations.csv")
    dates = pd.to_datetime(rows.date)
    weeks = ((dates - pd.Timestamp("1970-01-05")).dt.days // 7).to_numpy()
    X = np.loadtxt(OUT / f"design/{key}_year_weather_X.csv", delimiter=",")
    penalty = np.loadtxt(OUT / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    state = np.load(folder / f"{key}_fit.npz")
    penalty *= float(state["smoothing"])
    penalty[[1, 15, 16, 17, 18, 19, 20, 21], [1, 15, 16, 17, 18, 19, 20, 21]] += 1
    rows["mean"] = rows.fraction * np.exp(X @ state["coefficients"])
    rows["retained_count"] = rows["count"].where(~rows.hidden, 0)
    rows["retained_mean"] = rows["mean"].where(~rows.hidden, 0)
    target = (
        rows[rows.year.eq(context.target_year)]
        .groupby("date")
        .agg(
            full_count=("count", "sum"),
            retained_count=("retained_count", "sum"),
            retained_mean=("retained_mean", "sum"),
            missing_mean=("mean", lambda x: x[rows.loc[x.index, "hidden"]].sum()),
            gap_hours=("fraction", lambda x: x[rows.loc[x.index, "hidden"]].sum()),
            total_hours=("fraction", "sum"),
        )
    )
    target["count"] = target.full_count - target.retained_count
    target = target[target.gap_hours.gt(0)].copy()
    rain = (rows.rain_mm * rows.fraction).where(rows.hidden, 0).groupby(rows.date).sum()
    target["weather"] = np.where(
        rain.reindex(target.index) / target.gap_hours >= 0.1, "wet", "dry"
    )
    target["retained_fraction"] = 1 - target.gap_hours / target.total_hours

    # Calibration truth comes only from the other three years. Recreate each target's mask and resolution.
    cal_frames, gradients = [], []
    for fold in range(3):
        cal_days = rows.year.ne(context.target_year) & (weeks % 3 == fold)
        pseudo_hidden = cal_days & ~rows.template_keep
        hidden = rows.hidden | pseudo_hidden
        coarse = ~hidden & (
            (rows.year.eq(context.target_year) & (context.resolution == "survey"))
            | (cal_days & (context.resolution == "survey"))
        )
        run = (
            rows.date.ne(rows.date.shift())
            | rows.start.ne(rows.end.shift())
            | coarse.ne(coarse.shift())
        )
        ids = np.where(coarse, run.cumsum() + len(rows), rows.row_id)
        index = pd.Index(pd.unique(ids))
        A = csr_matrix(
            (rows.fraction, (index.get_indexer(ids), np.arange(len(rows)))),
            shape=(len(index), len(rows)),
        )
        cal_observations = (
            pd.DataFrame({"id": ids, "hidden": hidden, "count": rows["count"]})
            .groupby("id", sort=False)
            .agg(hidden=("hidden", "first"), count=("count", "sum"))
            .reindex(index)
        )
        assert (
            pd.DataFrame({"id": ids, "hidden": hidden}).groupby("id").hidden.nunique().eq(1).all()
        )
        fitted, _ = fit_rate(
            X,
            A[~cal_observations.hidden.to_numpy()],
            cal_observations.loc[~cal_observations.hidden, "count"].to_numpy(),
            penalty,
            1.5,
        )
        gradients.append(np.abs(fitted.jac).max())
        assert gradients[-1] < 0.001, (key, fold, gradients[-1])
        mean = rows.fraction * np.exp(X @ fitted.x)
        cal = pd.DataFrame(
            {
                "date": rows.date,
                "count": rows["count"].where(pseudo_hidden, 0),
                "missing_mean": mean.where(pseudo_hidden, 0),
                "retained_mean": mean.where(cal_days & ~pseudo_hidden, 0),
                "retained_count": rows["count"].where(cal_days & ~pseudo_hidden, 0),
                "hours": rows.fraction.where(pseudo_hidden, 0),
                "fold": fold,
            }
        )
        cal = (
            cal[cal_days]
            .groupby("date")
            .agg(
                missing_count=("count", "sum"),
                missing_mean=("missing_mean", "sum"),
                retained_mean=("retained_mean", "sum"),
                retained_count=("retained_count", "sum"),
                hours=("hours", "sum"),
                fold=("fold", "first"),
            )
        )
        cal_frames.append(cal[cal.hours.gt(0)])
    calibration = pd.concat(cal_frames)
    partial = calibration.retained_mean.gt(0)
    strength = select_retained_strength(calibration[partial])
    calibration["adjusted"] = calibration.missing_mean
    for fold in range(3):
        held = calibration.fold.eq(fold) & partial
        inner_strength = select_retained_strength(
            calibration[~calibration.fold.eq(fold) & partial]
        )
        calibration.loc[held, "adjusted"] = retained_prediction(
            calibration.loc[held, "missing_mean"],
            calibration.loc[held, "retained_mean"],
            calibration.loc[held, "retained_count"],
            inner_strength,
        )
    output = []
    for method in ["weather_mean", "weather_retained"]:
        sample = target.copy()
        sample["predicted"] = sample.missing_mean
        if method == "weather_retained":
            selected = sample.retained_mean.gt(0)
            sample.loc[selected, "predicted"] = retained_prediction(
                sample.loc[selected, "missing_mean"],
                sample.loc[selected, "retained_mean"],
                sample.loc[selected, "retained_count"],
                strength,
            )
        point = calibration.missing_mean if method == "weather_mean" else calibration.adjusted
        score = abs(calibration.missing_count - point) / (point + 1) ** 0.75
        for level in [0.8, 0.95]:
            (
                sample[f"lower{int(level * 100)}"],
                sample[f"upper{int(level * 100)}"],
            ) = count_interval(sample.predicted, score, level)
        sample["method"] = method
        output.append(sample.reset_index())
    calibration.to_csv(folder / "calibration.csv")

    # Original architecture: outside-year hourly profile, identical for both input resolutions.
    original_path = (
        OUT
        / "benchmark"
        / f'{context.english_name.replace(" ", "_")}_{context.scenario}_{context.target_year}.csv'
    )
    original_path.parent.mkdir(exist_ok=True)
    if original_path not in benchmarked and not (args.resume and original_path.exists()):
        frame_rows = rows.copy()
        frame_rows["date"] = pd.to_datetime(frame_rows.date)
        frame_rows["start"], frame_rows["end"] = pd.to_datetime(
            frame_rows.start, utc=True
        ), pd.to_datetime(frame_rows.end, utc=True)
        cache_key = (context.english_name, context.target_year)
        if cache_key not in profile_cache:
            profile_cache[cache_key] = training_profile(
                frame_rows[frame_rows.year.ne(context.target_year)]
            )
        profile = profile_cache[cache_key]
        slots = interval_slots(frame_rows)
        c = (slots * profile[np.clip(rows.doy.to_numpy(), *P.PROFILE_DOY) - P.PROFILE_DOY[0]]).sum(
            axis=1
        )
        frame_rows["c"] = c
        train = frame_rows[~frame_rows.hidden]
        day = train.groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
        calendar = pd.concat(
            [
                pd.Series(pd.date_range(f"{year}-07-18", f"{year}-11-18"))
                for year in range(2022, 2026)
            ],
            ignore_index=True,
        )
        frame = (
            pd.DataFrame(
                {
                    "date": calendar,
                    "year": calendar.dt.year,
                    "doy": T.season_day(pd.DatetimeIndex(calendar)),
                }
            )
            .join(day, on="date")
            .fillna({"y": 0, "c": 0})
        )
        low = frame.c.lt(T.MIN_COVERAGE)
        frame["extra"] = frame.y.where(low, 0)
        frame.loc[low, ["y", "c"]] = 0
        fit = T.fit(
            "gam", frame, np.arange(2022, 2026), (int(rows.doy.min()), int(rows.doy.max()))
        )
        # Rao–Blackwell mean: integrate coefficients, analytically average count/day-state draws.
        mu = np.exp(
            T.eta_draws(
                fit, frame.year, frame.doy, fit.draws(500, np.random.default_rng(20261012))
            )
        )
        rate = ((fit.theta + frame.y.to_numpy()) / (fit.theta / mu + frame.c.to_numpy())).mean(
            axis=0
        )
        missed_c = frame_rows[frame_rows.hidden].groupby("date").c.sum()
        original = target.copy()
        prediction = (
            pd.Series(rate, index=frame.date) * missed_c.reindex(frame.date).fillna(0).to_numpy()
        )
        original["predicted"] = prediction.reindex(pd.to_datetime(original.index)).to_numpy()
        original["method"] = "original_episode"
        original.reset_index().to_csv(original_path, index=False)
    benchmarked.add(original_path)
    output.append(pd.read_csv(original_path))
    combined = pd.concat(output, ignore_index=True)
    for name in [
        "key",
        "english_name",
        "scenario",
        "template_year",
        "target_year",
        "resolution",
        "panel",
    ]:
        combined[name] = getattr(context, name)
    combined.to_csv(folder / "assessment.csv", index=False)
    pd.DataFrame(
        [
            dict(
                key=key,
                calibration_gradient=max(gradients),
                strength=strength,
                calibration_days=len(calibration),
                seconds=perf_counter() - started,
            )
        ]
    ).to_csv(folder / "assessment_diagnostics.csv", index=False)
    print(key, "completed", round(perf_counter() - started, 2), flush=True)
