"""Reference arm `H`: the research's hourly weather mean, refitted on the realistic masks.

Run from the repository root after `realistic_masks.py`:
uv run python scripts/hierarchical/run_reference_hourly.py > logs/hierarchical/reference.log

The research code runs unchanged (`prepare_historical_transfer.R`, then `fit_simple_rate.py
--variant year_weather --variance-power 1.5 --select-smoothing`, as `run_history_episode.py` does
for its recent contexts), on the research's own inputs with this line's masks as `hidden`. Its
point predictions are written in `run_steps.py`'s format, without intervals (it has none).
"""

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from common import CORE, LOGS, MASKS, RESEARCH_DESIGN, ROOT, apply_mask

ARM = "H"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--species", nargs="+", default=list(CORE))
    parser.add_argument("--draws", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    parser.add_argument("--work", type=Path, default=LOGS / "reference-hourly")
    parser.add_argument("--out", type=Path, default=LOGS / "steps")
    args = parser.parse_args()
    inputs, design, fits = (args.work / name for name in ("input", "design", "fits"))
    for folder in (inputs, design, fits, args.out):
        folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    for species in args.species:
        source = f"recent__{species.replace(' ', '_')}_fold0"
        obs = pd.read_csv(RESEARCH_DESIGN / f"{source}_observations.csv", low_memory=False)
        parts = pd.read_csv(RESEARCH_DESIGN / f"{source}_components.csv", low_memory=False)
        dated = obs.assign(
            date=pd.to_datetime(obs.date, format="ISO8601"),
            start=pd.to_datetime(obs.start, utc=True, format="ISO8601"),
        )
        for draw in args.draws:
            key = f"realistic{draw}__{species.replace(' ', '_')}"
            mask = pd.read_csv(MASKS / f"draw{draw}.csv", parse_dates=["date"])
            mask["hide_from"] = pd.to_datetime(mask.hide_from, utc=True)
            hidden = apply_mask(dated, mask).to_numpy()
            obs.assign(hidden=hidden).to_csv(inputs / f"{key}_observations.csv", index=False)
            parts.assign(hidden=parts.observation_id.isin(obs.observation_id[hidden])).to_csv(
                inputs / f"{key}_components.csv", index=False
            )
            manifest.append(dict(key=key, english_name=species, fold=draw, task="realistic"))
    pd.DataFrame(manifest).to_csv(inputs / "manifest.csv", index=False)
    subprocess.run(
        ["Rscript", "scripts/research/prepare_historical_transfer.R", str(inputs), str(design)],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    keys = [m["key"] for m in manifest]
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/research/fit_simple_rate.py",
            "--input",
            str(design),
            "--out",
            str(fits),
            "--keys",
            *keys,
            "--variant",
            "year_weather",
            "--variance-power",
            "1.5",
            "--select-smoothing",
        ],
        check=True,
        cwd=ROOT,
    )
    weather = pd.read_csv(LOGS / "weather_hourly.csv")
    weather = weather.set_index(pd.to_datetime(weather.slot_start, utc=True)).rain_mm
    for context in manifest:
        key, species, draw = context["key"], context["english_name"], context["fold"]
        pred = pd.read_csv(fits / f"{key}_predictions.csv", low_memory=False)
        parts = pd.read_csv(inputs / f"{key}_components.csv", low_memory=False)
        rain = (
            parts.assign(
                rain=weather.reindex(pd.to_datetime(parts.slot_start, utc=True)).to_numpy()
                * parts.fraction
            )
            .groupby("observation_id")
            .rain.sum()
        )
        pred["rain"] = pred.observation_id.map(rain)
        pred["date"] = pd.to_datetime(pred.date, format="ISO8601")
        mask = pd.read_csv(MASKS / f"draw{draw}.csv", parse_dates=["date"])
        days = pred.groupby("date").agg(
            count=("count", "sum"),
            hours=("exposure_hours", "sum"),
            rain=("rain", "sum"),
            predicted=("predicted", "sum"),
        )
        days["kind"] = np.where(days.index.isin(mask.date[mask.kind.eq("day")]), "day", "end")
        days["weather"] = np.where(days.rain / days.hours >= 0.1, "wet", "dry")
        for name in ("q025", "q10", "q50", "q90", "q975"):
            days[name] = np.nan
        days = days.reset_index().assign(
            english_name=species, draw=draw, arm=ARM, year=lambda f: f.date.dt.year
        )
        obs = pd.read_csv(inputs / f"{key}_observations.csv", low_memory=False)
        truth = obs.groupby("year")["count"].sum()
        season = (
            days.groupby("year", as_index=False)
            .agg(hidden_count=("count", "sum"), predicted=("predicted", "sum"))
            .assign(english_name=species, draw=draw, arm=ARM)
        )
        season["observed_truth"] = season.year.map(truth)
        for name in ("q025", "q10", "q50", "q90", "q975"):
            season[name] = np.nan
        stem = f"{species.replace(' ', '_')}_draw{draw}_{ARM}"
        days.to_csv(args.out / f"{stem}_days.csv", index=False)
        season.to_csv(args.out / f"{stem}_season.csv", index=False)
        pd.DataFrame([dict(english_name=species, draw=draw, arm=ARM, seconds=np.nan)]).to_csv(
            args.out / f"{stem}_fit.csv", index=False
        )


if __name__ == "__main__":
    main()
