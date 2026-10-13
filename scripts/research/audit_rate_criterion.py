"""Audit retained interval weights and shared smoothing without refitting models."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.special import xlogy

SOURCE = Path("logs/history-episode")
SEASON = Path("logs/history-season")
OUT = Path("logs/rate-criterion")
OUT.mkdir(parents=True, exist_ok=True)

# Verify duration scaling with constant observed and predicted hourly rates.
duration = np.array([0.25, 0.5, 1, 2, 4, 8, 12])
hour_count, hour_mean = 3.0, 5.0
count, mean = duration * hour_count, duration * hour_mean
loss = 2 * (np.sqrt(mean) - np.sqrt(count)) ** 2 / np.sqrt(mean)
hour_loss = 2 * (np.sqrt(hour_mean) - np.sqrt(hour_count)) ** 2 / np.sqrt(hour_mean)
poisson = mean - count + xlogy(count, count / mean)
hour_poisson = hour_mean - hour_count + xlogy(hour_count, hour_count / hour_mean)
assert np.allclose(loss / hour_loss, np.sqrt(duration))
assert np.allclose(poisson / hour_poisson, duration)
assert np.allclose(np.sqrt(duration) * loss / hour_loss, duration)
pd.DataFrame(
    dict(
        hours=duration,
        current_relative_to_hourly=1 / np.sqrt(duration),
        duration_weighted_relative_to_hourly=np.ones(len(duration)),
        poisson_relative_to_hourly=np.ones(len(duration)),
    )
).to_csv(OUT / "constant_rate_scaling.csv", index=False)

# Use retained observations only; hidden counts never enter these diagnostics.
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
intervals, smoothing = [], []
for context in manifest.itertuples():
    key = context.key
    obs = pd.read_csv(
        SOURCE / f"design/{key}_observations.csv",
        usecols=["observation_id", "hidden", "exposure_hours", "year", "count"],
    )
    parts = pd.read_csv(
        SOURCE / f"design/{key}_components.csv", usecols=["observation_id", "fraction"]
    )
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    retained = ~obs.hidden.to_numpy()
    A = A[retained]
    obs = obs.loc[retained].reset_index(drop=True)
    hours = np.asarray(A.sum(axis=1)).ravel()
    assert np.allclose(hours, obs.exposure_hours)
    era = pd.cut(
        obs.year, [1992, 2007, 2016, 2021, 2025], labels=["early", "middle", "late", "recent"]
    )
    length = pd.cut(
        hours, [0, 1.01, 4, 8, np.inf], labels=["up_to_1h", "1_to_4h", "4_to_8h", "over_8h"]
    )
    for method, directory, suffix in [
        ("weather_mean", SOURCE / "design", "_year_weather"),
        ("weather_season", SEASON / "design", ""),
    ]:
        X = np.loadtxt(directory / f"{key}{suffix}_X.csv", delimiter=",")
        P = np.loadtxt(directory / f"{key}{suffix}_penalty.csv", delimiter=",")
        terms = pd.read_csv(directory / f"{key}{suffix}_terms.csv").term
        fit = np.load(SEASON / f"fits/{key}/{method}_fit.npz")
        beta, strength = fit["coefficients"], float(fit["smoothing"])
        rate = np.exp(X @ beta)
        mu = A @ rate
        if method == "weather_mean":
            rows = pd.DataFrame(
                dict(
                    era=era,
                    duration_group=length,
                    observations=1,
                    hours=hours,
                    birds=obs["count"],
                    intercept_information=np.sqrt(mu),
                    duration_weighted_information=np.sqrt(hours * mu),
                    absolute_intercept_score=abs(mu - obs["count"]) / np.sqrt(mu),
                    working_loss=2 * (np.sqrt(mu) - np.sqrt(obs["count"])) ** 2 / np.sqrt(mu),
                )
            )
            grouped = rows.groupby(["era", "duration_group"], observed=True).sum().reset_index()
            grouped = grouped.assign(key=key, english_name=context.english_name, task=context.task)
            for column in [
                "observations",
                "hours",
                "birds",
                "intercept_information",
                "duration_weighted_information",
            ]:
                grouped[f"{column}_share"] = grouped[column] / grouped[column].sum()
            intervals.append(grouped)
        # Expected working information; these EDF are conditional on fitted means/strength.
        J = A @ (rate[:, None] * X)
        information = J.T @ (mu[:, None] ** -1.5 * J)
        ridge = np.diag(
            (
                terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
                | terms.str.startswith("factor(year)")
            ).astype(float)
        )
        influence = np.linalg.solve(information + strength * P + ridge, information)
        for block, mask in [
            ("season", terms.str.startswith("season_").to_numpy()),
            ("clock", terms.str.match("(sin|cos)[123]$").to_numpy()),
        ]:
            indices = np.flatnonzero(mask)
            block_penalty = P[np.ix_(indices, indices)]
            smoothing.append(
                dict(
                    key=key,
                    english_name=context.english_name,
                    task=context.task,
                    method=method,
                    block=block,
                    strength=strength,
                    coefficients=len(indices),
                    conditional_edf=np.diag(influence)[indices].sum(),
                    penalty_energy=strength * beta[indices] @ block_penalty @ beta[indices] / 2,
                    penalty_trace=np.trace(block_penalty),
                )
            )

intervals = pd.concat(intervals, ignore_index=True)
intervals.to_csv(OUT / "interval_weights.csv", index=False)
shares = [column for column in intervals if column.endswith("_share")]
intervals.groupby(["task", "era", "duration_group"], observed=True)[shares].mean().to_csv(
    OUT / "mean_weight_shares.csv"
)
era_shares = intervals.groupby(["key", "task", "era"], observed=True)[shares].sum().reset_index()
era_shares.groupby(["task", "era"], observed=True)[shares].mean().to_csv(
    OUT / "era_weight_shares.csv"
)
smoothing = pd.DataFrame(smoothing)
smoothing.to_csv(OUT / "smoothing_blocks.csv", index=False)
smoothing.groupby(["task", "method", "block"])[
    ["conditional_edf", "penalty_energy", "penalty_trace"]
].median().to_csv(OUT / "median_smoothing_blocks.csv")
selection = smoothing[smoothing.block == "clock"].pivot(
    index="key", columns="method", values="strength"
)
selection.assign(clock_penalty_ratio=selection.weather_season / selection.weather_mean).to_csv(
    OUT / "smoothing_changes.csv"
)
print(
    f"Completed retained-input audit for {len(manifest)} contexts; no fits or hidden-count scores."
)
