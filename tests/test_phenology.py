import numpy as np
import pandas as pd

from defile_explore.phenology import passage_draws, phenology_block


def test_known_linear_change_and_joint_offsets():
    years = np.arange(1993, 2026)
    offsets = np.linspace(-5, 5, 1000)
    joint = {"year": years.tolist()}
    for q, start, slope in ((10, 250, 0.1), (50, 270, 0.2), (90, 300, 0.3)):
        joint[f"q{q}"] = (start + (years - 1993) * slope + offsets[:, None]).tolist()
    result = phenology_block({"source": "gam"}, joint)
    for key, slope in (("q10", 0.1), ("q50", 0.2), ("q90", 0.3)):
        fit = result["quantiles"][key]
        assert np.isclose(fit["slope"], slope)
        assert np.isclose(fit["slope_lo"], slope)
        assert np.isclose(fit["slope_hi"], slope)
        assert np.all(np.array(fit["annual_hi"]) > fit["annual_lo"])
    assert result["reconstruction_uncertainty_propagated"]


def test_uncertain_slopes_propagate_and_draws_are_reproducible():
    years = np.arange(2000, 2020)
    slopes = np.linspace(0, 0.4, 1000)
    joint = {
        "year": years.tolist(),
        **{f"q{q}": (270 + slopes[:, None] * (years - 2000)).tolist() for q in (10, 50, 90)},
    }
    a = phenology_block({"source": "gam"}, joint)
    assert a == phenology_block({"source": "gam"}, joint)
    fit = a["quantiles"]["q50"]
    assert np.isclose(fit["slope"], 0.2)
    assert fit["slope_lo"] < 0.02
    assert fit["slope_hi"] > 0.38
    assert fit["reconstruction_draws"] == 1000
    assert fit["trend_draws"] == 2000


def test_passage_draws_preserve_year_and_draw_order():
    frame = pd.DataFrame(
        {
            "year": [2000, 2000, 2001, 2001],
            "doy": [250, 251, 250, 251],
            "y": [1, 1, 1, 1],
            "extra": [0, 0, 0, 0],
        }
    )
    draws = np.array([[9, 1, 1, 9], [1, 9, 9, 1]])
    out = passage_draws(frame, draws)
    assert out["year"] == [2000, 2001]
    assert out["q50"][0][0] < out["q50"][0][1]
    assert out["q50"][1][0] > out["q50"][1][1]


def test_no_joint_draws_does_not_fabricate_intervals():
    assert phenology_block({"source": "gam"})["quantiles"] == {}
    assert phenology_block({"source": "counts"})["quantiles"] == {}


def test_between_year_variation_retains_uncertainty_with_exact_reconstruction():
    years = np.arange(2000, 2020)
    annual = 270 + 0.2 * (years - 2000) + np.tile([-3, 3], 10)
    joint = {
        "year": years.tolist(),
        **{f"q{q}": np.tile(annual, (1000, 1)).tolist() for q in (10, 50, 90)},
    }
    fit = phenology_block({"source": "gam"}, joint)["quantiles"]["q50"]
    assert fit["annual_lo"] == fit["annual_hi"]
    assert fit["slope_lo"] < fit["slope"] < fit["slope_hi"]
