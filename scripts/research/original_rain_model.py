"""Original daily GAM plus two fixed-ridge, passage-weighted daily rain covariates."""

from dataclasses import replace

import numpy as np
from scipy import sparse

from defile_explore import trend as T

ORIGINAL_DESIGN = T.design
RAIN_TERMS = ["log_rain", "rain_hinge"]


class RainDesign(T.Design):
    """Keep original smoothing selection; rain coefficients have fixed unit precision."""

    def block_precision(self, block, hyper):
        if block.name == "rain":
            return np.eye(len(RAIN_TERMS))
        return super().block_precision(block, hyper)


def rain_design(variant, years, doy_range, *, rain):
    """Insert rain before grouped episodes, preserving the original sparse factorization."""
    original = ORIGINAL_DESIGN(variant, years, doy_range)
    episode = original.blocks[-1]
    split = episode.columns.start
    blocks = original.blocks[:-1] + [
        T.Block("rain", slice(split, split + 2), []),
        replace(episode, columns=slice(split + 2, episode.columns.stop + 2)),
    ]

    def basis(year, doy):
        X = original.X(year, doy)
        values = rain.reindex(list(zip(year, doy))).to_numpy()
        return sparse.hstack([X[:, :split], values, X[:, split:]], format="csr")

    return RainDesign(variant, original.years, original.doy_range, blocks, basis)
