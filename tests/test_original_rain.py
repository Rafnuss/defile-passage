"""Check rain insertion, unchanged original penalties and recovery of a known rain response."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from defile_explore import trend as T

spec = importlib.util.spec_from_file_location(
    "original_rain_model", Path(__file__).parents[1] / "scripts/research/original_rain_model.py"
)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
RAIN_TERMS, rain_design = model.RAIN_TERMS, model.rain_design


def test_rain_preserves_original_design_and_prior():
    years = np.arange(2022, 2026)
    year = np.repeat(years, 124)
    doy = np.tile(np.arange(199, 323), len(years))
    rain = pd.DataFrame(
        np.random.default_rng(53).uniform(size=(len(year), 2)),
        columns=RAIN_TERMS,
        index=pd.MultiIndex.from_arrays([year, doy]),
    )
    original = T.design("gam", years, (199, 322))
    candidate = rain_design("gam", years, (199, 322), rain=rain)
    split = original.grouped.columns.start
    keep = np.r_[np.arange(split), np.arange(split + 2, candidate.n_columns)]
    assert candidate.grouped.groups == original.grouped.groups
    assert candidate.hyper_names == original.hyper_names
    assert np.array_equal(
        candidate.X(year, doy)[:, keep].toarray(), original.X(year, doy).toarray()
    )
    assert np.array_equal(candidate.X(year, doy)[:, split : split + 2].toarray(), rain.to_numpy())
    hyper = dict.fromkeys(original.hyper_names, 2.0)
    original_Q, candidate_Q = original.prior(hyper), candidate.prior(hyper)
    assert np.array_equal(original_Q.dense, candidate_Q.dense[:split, :split])
    assert np.array_equal(original_Q.group, candidate_Q.group)
    assert np.array_equal(candidate_Q.dense[split:, split:], np.eye(2))
    assert np.count_nonzero(candidate_Q.dense[:split, split:]) == 0


def test_known_rain_response(monkeypatch):
    year = np.repeat([2022, 2023], 124)
    doy = np.tile(np.arange(199, 323), 2)
    rain = pd.DataFrame(
        np.random.default_rng(19).uniform(0, 2, (len(year), 2)),
        columns=RAIN_TERMS,
        index=pd.MultiIndex.from_arrays([year, doy]),
    )
    frame = pd.DataFrame(dict(year=year, doy=doy, c=1.0))
    frame["y"] = np.exp(5 - 0.8 * rain.log_rain.to_numpy() + 0.2 * rain.rain_hinge.to_numpy())
    design = rain_design("gam", np.array([2022, 2023]), (199, 322), rain=rain)
    monkeypatch.setattr(T, "design", lambda *args: design)
    hyper = dict.fromkeys(design.hyper_names, np.log(1000)) | {"theta": np.log(100)}
    fit = T.fit("gam", frame, np.array([2022, 2023]), (199, 322), hyper=hyper)
    assert np.allclose(fit.beta[design.columns_of("rain")], [-0.8, 0.2], atol=0.01)
