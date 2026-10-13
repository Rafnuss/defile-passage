"""Independent checks of retained-count shrinkage and empirical count intervals."""

import numpy as np
import pandas as pd
from simple_rate_prediction import (
    count_interval,
    retained_prediction,
    select_retained_strength,
    short_gap_mask,
)

# Missing counts use only retained information, and observed totals are conserved.
missing = np.array([2.0, 20.0, 100.0])
assert np.array_equal(retained_prediction(missing, 0, 0, 10), missing)
assert np.array_equal(retained_prediction(missing, 5, 0, np.inf), missing)
assert np.all(retained_prediction(missing, 5, 0, 10) < missing)
assert np.allclose(retained_prediction(missing, 5, 15, 10), missing * 25 / 15)

# Outward integer rounding prevents empty count intervals at small means.
lower, upper = count_interval(np.array([0.4, 20.0]), np.zeros(40), 0.95)
assert np.array_equal(lower, [0, 20]) and np.array_equal(upper, [1, 20])
retained = np.array([3, 17])
assert np.array_equal((retained + upper) - (retained + lower), upper - lower)

# A training-selected update improves an independent sample with shared daily activity.
rng = np.random.default_rng(20261012)
activity = rng.gamma(2, 0.5, 6000)
frame = pd.DataFrame(
    dict(
        missing_mean=np.full(6000, 10.0),
        retained_mean=np.full(6000, 20.0),
        retained_count=rng.poisson(20 * activity),
        missing_count=rng.poisson(10 * activity),
    )
)
strength = select_retained_strength(frame.iloc[:3000])
test = frame.iloc[3000:]
point = retained_prediction(test.missing_mean, test.retained_mean, test.retained_count, strength)
assert np.mean((test.missing_count - point) ** 2) < np.mean(
    (test.missing_count - test.missing_mean) ** 2
)

# Independently sampled predictive counts have approximately nominal empirical coverage.
y = rng.poisson(20, 10000)
scores = abs(y[:5000] - 20) / 21**0.75
for level in [0.8, 0.95]:
    lower, upper = count_interval(np.full(5000, 20.0), scores, level)
    coverage = np.mean((y[5000:] >= lower) & (y[5000:] <= upper))
    assert level - 0.02 <= coverage <= min(1, level + 0.08), coverage
print(
    "Prediction checks passed: shrinkage, zero retained counts, count bounds, conservation and simulated coverage."
)

# Effort breaks constrain pseudo gaps; bird counts cannot influence their selection.

hours = pd.date_range("2025-09-01T06:00Z", periods=10, freq="h")
rows = pd.DataFrame(
    dict(
        date=["2025-09-01"] * 10,
        start=hours.astype(str),
        end=(hours + pd.Timedelta(hours=1)).astype(str),
        doy=[244] * 10,
        count=np.arange(10),
    )
)
selected = short_gap_mask(rows)
assert selected.sum() == 3 and np.array_equal(np.flatnonzero(selected), [3, 4, 5])
assert np.array_equal(short_gap_mask(rows.assign(count=0)), selected)
rows.loc[3:, "start"] = (hours[3:] + pd.Timedelta(hours=2)).astype(str)
rows.loc[3:, "end"] = (hours[3:] + pd.Timedelta(hours=3)).astype(str)
selected = short_gap_mask(rows)
assert selected.sum() == 3 and not selected.iloc[:3].any()
print("Short-gap masks respect effort breaks and are count-independent.")
