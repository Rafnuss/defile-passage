"""Check a bounded BFGS solver against saved optima and previously stalled CV fits."""

from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from simple_rate_model import check_rate_gradient, fit_rate

OUT = Path("logs/bounded-solver")
SOURCE = Path("logs/history-episode")
OUT.mkdir(parents=True, exist_ok=True)
manifest = pd.read_csv(SOURCE / "design/manifest.csv")
rows = []
for context in manifest.itertuples():
    key = context.key
    obs = pd.read_csv(SOURCE / f"design/{key}_observations.csv", low_memory=False)
    parts = pd.read_csv(
        SOURCE / f"design/{key}_components.csv", usecols=["observation_id", "fraction"]
    )
    index = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    A = csr_matrix((parts.fraction, (index, np.arange(len(parts)))), shape=(len(obs), len(parts)))
    training = A[~obs.hidden.to_numpy()]
    y = obs.loc[~obs.hidden, "count"].to_numpy()
    duration = np.asarray(training.sum(axis=1)).ravel()
    X = np.loadtxt(SOURCE / f"design/{key}_year_weather_X.csv", delimiter=",")
    P = np.loadtxt(SOURCE / f"design/{key}_year_weather_penalty.csv", delimiter=",")
    terms = pd.read_csv(SOURCE / f"design/{key}_year_weather_terms.csv").term
    ridge = np.diag(
        (
            terms.isin(["log_rain", "rain_hinge", "wind_u", "wind_v", "night"])
            | terms.str.startswith("factor(year)")
        ).astype(float)
    )
    for power in [0, 0.25, 0.5]:
        file = (
            SOURCE / f"fits/{key}/weather_mean_fit.npz"
            if power == 0
            else Path(f"logs/duration-weight/power-{power}/fits/{key}/weather_weighted_fit.npz")
        )
        if not file.exists():
            continue
        saved = np.load(file)
        started = perf_counter()
        fit, objective = fit_rate(
            X, training, y, float(saved["smoothing"]) * P + ridge, 1.5, duration**power
        )
        seconds = perf_counter() - started
        old_loss = objective(saved["coefficients"])[0]
        prediction_error = np.max(np.abs(np.exp(X @ (fit.x - saved["coefficients"])) - 1))
        rows.append(
            dict(
                key=key,
                power=power,
                stage="saved_final",
                smoothing=float(saved["smoothing"]),
                fold=-1,
                seconds=seconds,
                iterations=fit.nit,
                success=fit.success,
                message=fit.message,
                gradient=abs(fit.jac).max(),
                derivative_error=check_rate_gradient(objective, fit.x),
                loss_difference=fit.fun - old_loss,
                relative_loss_difference=abs(fit.fun - old_loss) / max(1, abs(old_loss)),
                maximum_rate_relative_difference=prediction_error,
            )
        )
    if context.english_name != "European Honey Buzzard":
        continue
    dates = pd.to_datetime(obs.loc[~obs.hidden, "date"])
    weeks = ((dates - pd.Timestamp("1970-01-05", tz=dates.dt.tz)).dt.days // 7).to_numpy()
    for strength in [0.1, 1, 10]:
        for fold in range(3):
            mask = weeks % 3 != fold
            started = perf_counter()
            fit, objective = fit_rate(
                X, training[mask], y[mask], strength * P + ridge, 1.5, duration[mask] ** 0.5
            )
            rows.append(
                dict(
                    key=key,
                    power=0.5,
                    stage="previously_stalled_cv",
                    smoothing=strength,
                    fold=fold,
                    seconds=perf_counter() - started,
                    iterations=fit.nit,
                    success=fit.success,
                    message=fit.message,
                    gradient=abs(fit.jac).max(),
                    derivative_error=check_rate_gradient(objective, fit.x),
                )
            )
checks = pd.DataFrame(rows)
checks.to_csv(OUT / "checks.csv", index=False)
assert (checks.gradient < 0.001).all()
assert (checks.derivative_error < 0.001).all()
saved_checks = checks[checks.stage.eq("saved_final")]
assert (saved_checks.relative_loss_difference < 1e-7).all()
assert (saved_checks.maximum_rate_relative_difference < 1e-5).all()
print("Completed solver check batch:", len(rows), "fits", flush=True)
