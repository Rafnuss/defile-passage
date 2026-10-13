"""Production's daily GAM with daily weather terms and, for step `D`, a daily AR(1) process.

Weather terms (steps `R`, `RS`, `RSW` of the README) are linear, standardised by the caller, with a
fixed unit prior precision (a ridge): no smoothing parameter of their own. They are inserted before
the grouped episode block so that production's block-sparse factorisation is kept.

Step `D` replaces the episode block (25 knots a year) by one value per window day and year: a
stationary AR(1) prior with unit variance scaled by its own smoothing parameter (`1 / sigma^2`,
Fellner-Schall like every other), centred over each year's window so that the year's level stays
with `year`. Its correlation `rho = exp(-1 / tau)` is chosen over `AR1_TAU_DAYS` by the Laplace
marginal likelihood, never on held-out counts (14 days, the first grid's edge, was chosen for
four species: the grid goes to 30).
"""

from dataclasses import replace

import numpy as np
import pandas as pd
from scipy import sparse

from defile_explore import trend as T

PRODUCTION_DESIGN = T.design
WEATHER_BLOCK = "weather"
DAILY_BLOCK = "daily"
AR1_TAU_DAYS = (2, 4, 7, 14, 21, 30)


class WeatherDesign(T.Design):
    def block_precision(self, block, hyper):
        if block.name == WEATHER_BLOCK:
            return np.eye(block.size)
        return super().block_precision(block, hyper)


def weather_design(variant, years, doy_range, *, terms: pd.DataFrame):
    """Production's design plus the columns of `terms`, indexed by (year, doy)."""
    base = PRODUCTION_DESIGN(variant, years, doy_range)
    episode = base.blocks[-1]
    split, k = episode.columns.start, terms.shape[1]
    blocks = base.blocks[:-1] + [
        T.Block(WEATHER_BLOCK, slice(split, split + k), []),
        replace(episode, columns=slice(split + k, episode.columns.stop + k)),
    ]

    def basis(year, doy):
        X = base.X(year, doy)
        values = terms.reindex(list(zip(year, doy))).to_numpy()
        assert np.isfinite(values).all(), "weather term missing for a modelled day"
        return sparse.hstack([X[:, :split], values, X[:, split:]], format="csr")

    return WeatherDesign(variant, base.years, base.doy_range, blocks, basis)


def ar1_precision(n: int, rho: float) -> np.ndarray:
    """Precision of a stationary AR(1) series of `n` values with unit variance."""
    R = np.diag(np.r_[1.0, np.full(n - 2, 1 + rho**2), 1.0]) - rho * (
        np.eye(n, k=1) + np.eye(n, k=-1)
    )
    return R / (1 - rho**2)


def daily_design(variant, years, doy_range, *, terms: pd.DataFrame | None, rho: float):
    """The design of `weather_design` (or production's) with the episode block replaced by a
    centred daily AR(1) block per year."""
    base = (
        weather_design(variant, years, doy_range, terms=terms)
        if terms is not None
        else PRODUCTION_DESIGN(variant, years, doy_range)
    )
    split = base.blocks[-1].columns.start
    d0, d1 = doy_range
    k = d1 - d0 + 1
    Z = T.sum_to_zero(np.eye(k))
    S = Z.T @ ar1_precision(k, rho) @ Z
    y0, n_years = int(base.years.min()), len(base.years)
    blocks = base.blocks[:-1] + [
        T.Block(DAILY_BLOCK, slice(split, split + n_years * (k - 1)), [(DAILY_BLOCK, S)], n_years)
    ]

    def basis(year, doy):
        X = base.X(year, doy)[:, :split]
        day = Z[np.clip(np.asarray(doy) - d0, 0, k - 1)]
        return sparse.hstack([X, T._per_year(np.asarray(year) - y0, n_years, day)], format="csr")

    cls = WeatherDesign if terms is not None else T.Design
    return cls(variant, base.years, base.doy_range, blocks, basis)


def fit(
    frame: pd.DataFrame, years, doy_range, terms: pd.DataFrame | None, ar1: bool = False
) -> T.Fit:
    """Production's fit, with daily weather terms when given, and with `ar1` the daily process in
    place of the episode block (the `rho` of the highest marginal likelihood)."""
    if terms is not None and terms.shape[1] == 0:
        terms = None
    if not ar1:
        if terms is None:
            return T.fit("gam", frame, years, doy_range)
        designs = [lambda v, y, d: weather_design(v, y, d, terms=terms)]
    else:
        designs = [
            lambda v, y, d, rho=np.exp(-1 / tau): daily_design(v, y, d, terms=terms, rho=rho)
            for tau in AR1_TAU_DAYS
        ]
    fits = []
    for make in designs:
        T.design = make
        try:
            fits.append(T.fit("gam", frame, years, doy_range))
        finally:
            T.design = PRODUCTION_DESIGN
    best = max(range(len(fits)), key=lambda i: fits[i].log_marginal)
    if ar1:
        fits[best].hyper["tau"] = AR1_TAU_DAYS[best]
    return fits[best]
