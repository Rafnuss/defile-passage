"""Small empirical retained-count adjustment and count prediction intervals."""

import numpy as np

SHRINKAGE = np.array([1, 10, 100, 1000, np.inf])
LEVELS = (0.8, 0.95)


def retained_prediction(missing_mean, retained_mean, retained_count, strength):
    """Shrink the observed retained-count ratio toward the unadjusted hourly model."""
    if np.isinf(strength):
        return np.asarray(missing_mean).copy()
    return missing_mean * (retained_count + strength) / (retained_mean + strength)


def select_retained_strength(frame):
    """Select a single pseudo-count on training-only missing-count MAE."""
    errors = [
        np.abs(
            frame["missing_count"]
            - retained_prediction(frame.missing_mean, frame.retained_mean, frame.retained_count, s)
        ).mean()
        for s in SHRINKAGE
    ]
    return SHRINKAGE[np.argmin(errors)]


def count_interval(mean, calibration_scores, level):
    """Cross-validation residual interval, with count-compatible integer endpoints."""
    scores = np.sort(calibration_scores)
    rank = min(int(np.ceil((len(scores) + 1) * level)), len(scores))
    radius = scores[rank - 1] * (np.asarray(mean) + 1) ** 0.75
    return np.floor(np.maximum(0, mean - radius)), np.ceil(mean + radius)


def short_gap_mask(rows):
    """Select three adjacent effort intervals, rotating early/middle/late by calendar day."""
    selected = rows["date"].eq("")
    for _, day in rows.groupby("date"):
        day = day.sort_values("start")
        runs = day.start.ne(day.end.shift()).cumsum()
        run = day[runs.eq(runs.value_counts().idxmax())]
        if len(run) < 6:
            continue
        position = [0, (len(run) - 3) // 2, len(run) - 3][int(run.doy.iloc[0]) % 3]
        selected.loc[run.index[position : position + 3]] = True
    return selected
