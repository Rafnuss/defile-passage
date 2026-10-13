"""Compare one prespecified small episode candidate with unchanged weather means."""

import argparse
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.linalg import block_diag
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/history-episode")
EPISODE_STRENGTH = 100
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--shard", nargs=2, type=int, default=[0, 1])
args = parser.parse_args()
manifest = pd.read_csv(OUT / "design/manifest.csv")
names = {name: i for i, name in enumerate(sorted(manifest.english_name.unique()))}
manifest = manifest[manifest.english_name.map(names) % args.shard[1] == args.shard[0]]
for context in manifest.itertuples():
    key = context.key
    folder = OUT / "fits" / key
    folder.mkdir(parents=True, exist_ok=True)
    source_key = key.split("__", 1)[1]
    if context.task == "recent":
        with (folder / "baseline.log").open("w") as log:
            subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/research/fit_simple_rate.py",
                    "--input",
                    str(OUT / "design"),
                    "--out",
                    str(folder),
                    "--keys",
                    key,
                    "--variant",
                    "year_weather",
                    "--variance-power",
                    "1.5",
                    "--select-smoothing",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        saved = np.load(folder / f"{key}_fit.npz")
    else:
        saved = np.load(Path("logs/historical-counts/fits") / source_key / f"{source_key}_fit.npz")
    obs = pd.read_csv(OUT / f"design/{key}_observations.csv")
    parts = pd.read_csv(OUT / f"design/{key}_components.csv")
    X = np.loadtxt(OUT / f"design/{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(OUT / f"design/{key}_year_weather_penalty.csv", delimiter=",") * float(
        saved["smoothing"]
    )
    ridge = [1, 15, 16, 17, 18, *range(19, X.shape[1])]
    P[ridge, ridge] += 1
    episode = np.loadtxt(OUT / f"design/{key}_episode_X.csv", delimiter=",")
    episode_P = np.loadtxt(OUT / f"design/{key}_episode_penalty.csv", delimiter=",")
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    hidden = obs.hidden.to_numpy()
    target = obs[hidden].groupby("date")["count"].sum().to_frame()
    rain = (
        parts[parts.hidden]
        .assign(rain_hours=lambda x: x.rain_mm * x.fraction)
        .groupby("date")
        .agg(rain_hours=("rain_hours", "sum"), hours=("fraction", "sum"))
    )
    target = target.join(rain)
    target["weather"] = np.where(target.rain_hours / target.hours >= 0.1, "wet", "dry")
    target["year"] = pd.to_datetime(target.index).year
    diagnostics = []
    for method, design, penalty in [
        ("weather_mean", X, P),
        (
            "weather_episode",
            np.column_stack([X, episode]),
            block_diag(P, EPISODE_STRENGTH * episode_P),
        ),
    ]:
        started = perf_counter()
        fit, objective = fit_rate(
            design,
            A[~hidden],
            obs.loc[~hidden, "count"].to_numpy(),
            penalty,
            1.5,
            solver="trust-exact",
        )
        seconds = perf_counter() - started
        gradient = abs(fit.jac).max()
        derivative = check_rate_gradient(objective, fit.x)
        assert gradient < 0.001 and derivative < 0.001, (key, method, gradient, derivative)
        if method == "weather_mean":
            assert np.allclose(fit.x, saved["coefficients"], atol=1e-7, rtol=1e-7)
        prediction = obs[hidden][["date"]].assign(predicted=A[hidden] @ np.exp(design @ fit.x))
        target[method] = prediction.groupby("date").predicted.sum()
        np.savez(
            folder / f"{method}_fit.npz",
            coefficients=fit.x,
            smoothing=saved["smoothing"],
            episode_strength=EPISODE_STRENGTH if method == "weather_episode" else 0,
        )
        diagnostics.append(
            dict(
                key=key,
                method=method,
                coefficients=len(fit.x),
                seconds=seconds,
                iterations=fit.nit,
                gradient=gradient,
                derivative_error=derivative,
            )
        )
    target["english_name"], target["fold"], target["task"] = (
        context.english_name,
        context.fold,
        context.task,
    )
    target.reset_index().to_csv(folder / "assessment.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(folder / "episode_diagnostics.csv", index=False)
    print(key, "completed", flush=True)
