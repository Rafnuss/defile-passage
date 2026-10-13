"""Reference arm `A`: the research's daily-passage AR(1) model, refitted on the realistic masks.

Run from the repository root after `run_reference_hourly.py` (it starts from that arm's fits): uv
run python scripts/hierarchical/run_reference_daily.py > logs/hierarchical/reference-daily.log

`run_daily_passage.py` runs unchanged. It reads its inputs under `logs/history-episode/` (relative
to its working directory), so a shadow tree in the work folder points there: the hourly arm's
designs, its fitted coefficients and smoothing, and its predictions (which the runner checks it
replays). Its point predictions are written in `run_steps.py`'s format.
"""

import argparse
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from common import CORE, LOGS, ROOT

ARM = "A"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--species", nargs="+", default=list(CORE))
    parser.add_argument("--draws", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    parser.add_argument("--hourly", type=Path, default=LOGS / "reference-hourly")
    parser.add_argument("--work", type=Path, default=LOGS / "reference-daily")
    parser.add_argument("--out", type=Path, default=LOGS / "steps")
    args = parser.parse_args()
    shadow = args.work / "logs/history-episode"
    (shadow / "fits").mkdir(parents=True, exist_ok=True)
    if not (shadow / "design").exists():
        os.symlink((args.hourly / "design").resolve(), shadow / "design")
    failures = []
    env = os.environ | {"OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"}
    for species in args.species:
        for draw in args.draws:
            key = f"realistic{draw}__{species.replace(' ', '_')}"
            stem = f"{species.replace(' ', '_')}_draw{draw}"
            folder = shadow / "fits" / key
            folder.mkdir(exist_ok=True)
            saved = np.load(args.hourly / "fits" / f"{key}_fit.npz")
            np.savez(folder / "weather_mean_fit.npz", **saved)
            hourly = pd.read_csv(args.out / f"{stem}_H_days.csv")
            hourly[["date", "predicted"]].rename(columns={"predicted": "weather_mean"}).assign(
                weather_episode=np.nan
            ).to_csv(folder / "assessment.csv", index=False)
            with (args.work / f"{key}.log").open("w") as log:
                run = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--project",
                        str(ROOT),
                        "python",
                        str(ROOT / "scripts/research/run_daily_passage.py"),
                        "--key",
                        key,
                        "--out",
                        str((args.work / "out").resolve()),
                    ],
                    cwd=args.work,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            if run.returncode:  # its own convergence checks failed: recorded, not scored
                failures.append(key)
                print(key, "failed", flush=True)
                continue
            result = pd.read_csv(args.work / "out/fits" / key / "assessment.csv")
            days = hourly.drop(columns="predicted").merge(
                result[["date", "weather_daily"]].rename(columns={"weather_daily": "predicted"}),
                on="date",
                validate="one_to_one",
            )
            days["arm"] = ARM
            days.to_csv(args.out / f"{stem}_{ARM}_days.csv", index=False)
            season = pd.read_csv(args.out / f"{stem}_H_season.csv").drop(columns="predicted")
            season = season.merge(
                days.groupby("year", as_index=False).predicted.sum(), on="year"
            ).assign(arm=ARM)
            season.to_csv(args.out / f"{stem}_{ARM}_season.csv", index=False)
            pd.DataFrame([dict(english_name=species, draw=draw, arm=ARM, seconds=np.nan)]).to_csv(
                args.out / f"{stem}_{ARM}_fit.csv", index=False
            )
            print(key, "done", flush=True)
    pd.Series(failures, name="key").to_csv(args.work / "failures.csv", index=False)


if __name__ == "__main__":
    main()
