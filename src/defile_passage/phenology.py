"""Linear change in annual passage dates, fitted separately to joint reconstruction draws."""

import numpy as np

from defile_passage.season import quantiles_of_draws

METHOD = "annual-date-linear@2"
SEED = 19647
QUANTILES = (10, 50, 90)
BAND = (0.025, 0.975)
RESAMPLES_PER_DRAW = 2


def passage_draws(frame, totals: np.ndarray) -> dict:
    """Retain draw identities across years and all three passage thresholds."""
    years, dates = [], []
    for year, rows in frame.groupby("year"):
        if (rows["y"] + rows["extra"]).sum() <= 0:
            continue
        rows = rows.sort_values("doy")
        years.append(int(year))
        dates.append(quantiles_of_draws(rows["doy"].to_numpy(), totals[:, rows.index]))
    out = {"year": years}
    for j, q in enumerate(QUANTILES):
        out[f"q{q}"] = (
            np.stack([d[:, j] for d in dates], axis=1).round(4).tolist() if dates else []
        )
    return out


def phenology_block(season: dict, joint: dict | None = None) -> dict:
    joint = joint if joint is not None else season.get("phenology", {}).get("draws")
    out = {
        "method": METHOD,
        "source": season["source"],
        "uncertainty": "joint-reconstruction-and-residual-bootstrap",
        "reconstruction_uncertainty_propagated": True,
        "quantiles": {},
    }
    if season["source"] != "gam" or joint is None:
        return out
    out["draws"] = joint
    x = np.array(joint["year"])
    if len(x) < 3:
        return out
    dx = x - x.mean()
    ss = dx @ dx
    for q in QUANTILES:
        y = np.asarray(joint[f"q{q}"], float)
        means = y.mean(axis=1)
        slopes = y @ dx / ss
        fitted = means[:, None] + slopes[:, None] * dx
        residuals = y - fitted
        rng = np.random.default_rng(SEED + q)
        # Each joint draw supplies one date per year. Residual resampling adds between-year
        # regression uncertainty, including when complete counts make reconstruction exact.
        indices = rng.integers(len(x), size=(len(y), RESAMPLES_PER_DRAW, len(x)))
        sample = fitted[:, None, :] + np.take_along_axis(residuals[:, None, :], indices, axis=2)
        sample = sample.reshape(-1, len(x))
        b = sample @ dx / ss
        curves = sample.mean(axis=1)[:, None] + b[:, None] * dx
        lo, hi = np.quantile(curves, BAND, axis=0)
        slope_lo, slope_hi = np.quantile(b, BAND)
        annual_lo, annual_date, annual_hi = np.quantile(y, [0.1, 0.5, 0.9], axis=0)
        out["quantiles"][f"q{q}"] = {
            "year": x.tolist(),
            "date": fitted.mean(axis=0).round(4).tolist(),
            "lo": lo.round(4).tolist(),
            "hi": hi.round(4).tolist(),
            "slope": round(float(slopes.mean()), 6),
            "slope_lo": round(float(slope_lo), 6),
            "slope_hi": round(float(slope_hi), 6),
            "annual": annual_date.round(4).tolist(),
            "annual_lo": annual_lo.round(4).tolist(),
            "annual_hi": annual_hi.round(4).tolist(),
            "reconstruction_draws": len(y),
            "trend_draws": len(b),
        }
    return out
