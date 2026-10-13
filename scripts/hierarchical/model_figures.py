"""The numbers drawn by the model page (`MODEL.html`): one fit of `P` and `D` and the saved
results.

Run from the repository root after `run_steps.py` and `score_steps.py` (and the lockbox): uv run
--with 'pyarrow<20' python scripts/hierarchical/model_figures.py > logs/hierarchical/figures.log

One species and mask draw (`--species`, `--draw`, `--year` for the year shown): its time-of-day
profile, an example day's coverage, the components of `D` (season, trend, year, weather, the daily
process for one year), the marginal likelihood over `tau`, and the fill of that year's hidden days
by `P` and `D`. Everything else (audit, scores, lockbox, every fit's `tau` and weather effects) is
read from the saved tables. Writes `logs/hierarchical/figures.json` and the page with its numbers,
`logs/hierarchical/model_page.html`.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from common import AUDIT, CORE, LOGS, MASKS, apply_mask, load_species
from run_steps import (
    ARMS,
    SEED,
    TIMED_FROM,
    daily_terms,
    hourly_weather,
    kappa_of,
    species_slots,
    training_profile,
)
from weather_design import AR1_TAU_DAYS, PRODUCTION_DESIGN, daily_design
from weather_design import fit as fit_arm

from defile_explore import export as E
from defile_explore import profile as P
from defile_explore import trend as T

OUT = LOGS / "figures.json"
TEMPLATE = Path(__file__).with_name("model_page.html")
PAGE = LOGS / "model_page.html"
DRAWS = 400
STEPS = ["P", "R", "RS", "RSW", "D", "I"]


def rounded(x, digits=4):
    return np.round(np.asarray(x, float), digits).tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--species", default="Black Kite")
    parser.add_argument("--draw", type=int, default=0)
    parser.add_argument("--year", type=int, default=2020)
    args = parser.parse_args()
    out = {"species": args.species, "draw": args.draw, "year": args.year}
    weather = hourly_weather()

    # --- the one fit ---------------------------------------------------------------------------
    obs, parts = load_species(args.species)
    slots = species_slots(args.species, parts)
    row_of = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    obs_slots = np.zeros((len(obs), E.SLOTS))
    np.add.at(obs_slots, row_of, slots)
    years = np.arange(1993, 2026)
    doy_range = (int(parts.doy.min()), int(parts.doy.max()))
    calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    calendar = calendar[E.in_window(pd.Series(calendar)).to_numpy()]
    doy = T.season_day(calendar)
    calendar = calendar[(doy >= doy_range[0]) & (doy <= doy_range[1])]
    mask = pd.read_csv(MASKS / f"draw{args.draw}.csv", parse_dates=["date"])
    mask["hide_from"] = pd.to_datetime(mask.hide_from, utc=True)
    hidden = apply_mask(obs, mask).to_numpy()
    timed = obs[~hidden & obs.year.ge(TIMED_FROM).to_numpy() & obs.exposure_hours.le(1).to_numpy()
        & ~obs.weather_stop.to_numpy()]
    sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
        timed[["observation_id", "count"]], on="observation_id"
    )
    sample = sample[~sample.observation_id.duplicated(keep=False)]
    sample["exposure_hours"] = sample.fraction
    profile = training_profile(sample)
    base = profile[
        np.clip(T.season_day(pd.DatetimeIndex(obs.date)), *P.PROFILE_DOY) - P.PROFILE_DOY[0]
    ]
    c = (obs_slots * base).sum(axis=1)
    obs_c = obs.assign(c=c)
    kappa = kappa_of(obs_c[~hidden], obs_slots[~hidden], profile)

    day = obs_c[~hidden].groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
    frame = pd.DataFrame({"date": calendar, "year": calendar.year, "doy": T.season_day(calendar)})
    frame = frame.join(day, on="date").fillna({"y": 0, "c": 0})
    low = frame.c.lt(T.MIN_COVERAGE)
    frame["extra"] = frame.y.where(low, 0)
    frame.loc[low, ["y", "c"]] = 0
    raw = daily_terms(frame, profile, weather)
    counted = frame.c.gt(0).to_numpy()
    terms = ((raw - raw[counted].mean()) / raw[counted].std())[ARMS["D"]]

    # Profile: the heat map (hourly shares) and four days' curves (five-minute slots).
    grid = np.arange(P.PROFILE_DOY[0], P.PROFILE_DOY[1] + 1)
    hourly = profile.reshape(len(grid), 24, E.STEPS_PER_HOUR).sum(axis=2)
    keep_days = np.arange(0, len(grid), 2)
    out["profile"] = {
        "doy": grid[keep_days].tolist(),
        "hourly": rounded(hourly[keep_days], 5),
        "curves": {
            str(d): rounded(profile[d - P.PROFILE_DOY[0]] * E.STEPS_PER_HOUR, 4)
            for d in (213, 244, 274, 305)
        },
    }

    # Coverage on an example day: the busiest day of the year shown with at least six hours timed.
    hours = sample.assign(hour=pd.to_datetime(sample.slot_start, utc=True)).merge(
        obs_c[["observation_id", "c"]], on="observation_id"
    )
    hours = hours[hours.date.dt.year.eq(args.year)]
    by_day = hours.groupby("date").agg(birds=("count", "sum"), n=("count", "size"))
    example = by_day[by_day.n.ge(6)].birds.idxmax()
    ex = hours[hours.date.eq(example)].sort_values("hour")
    shift = float(E.solar_shift(pd.Series([example])).iloc[0])
    local = E.to_local(ex.hour)
    solar = (local - local.dt.normalize()) / pd.Timedelta(hours=1) - shift
    ex_doy = int(T.season_day(pd.DatetimeIndex([example]))[0])
    day_rate = ex["count"].sum() / ex.c.sum()
    out["coverage_day"] = {
        "date": str(example.date()),
        "solar_hour": rounded(solar, 3),
        "count": ex["count"].astype(int).tolist(),
        "c": rounded(ex.c, 4),
        "c_total": round(float(ex.c.sum()), 3),
        "profile": rounded(profile[ex_doy - P.PROFILE_DOY[0]] * E.STEPS_PER_HOUR * day_rate, 2),
        "day_estimate": round(float(day_rate), 1),
    }

    # D at every tau (its marginal likelihood) and P.
    fits = {}
    curve = []
    for tau in AR1_TAU_DAYS:
        T.design = lambda v, y, d, rho=np.exp(-1 / tau): daily_design(
            v, y, d, terms=terms, rho=rho
        )
        try:
            f = T.fit("gam", frame, years, doy_range)
        finally:
            T.design = PRODUCTION_DESIGN
        fits[tau] = f
        curve.append(f.log_marginal)
        print(f"tau {tau}: log marginal {f.log_marginal:.1f}", flush=True)
    best = AR1_TAU_DAYS[int(np.argmax(curve))]
    fit_d = fits[best]
    fit_p = fit_arm(frame, years, doy_range, None)
    out["tau_curve"] = {
        "tau": list(AR1_TAU_DAYS),
        "log_marginal": rounded(np.array(curve) - max(curve), 2),
        "best": best,
    }
    out["theta"] = {"P": fit_p.theta, "D": fit_d.theta}
    out["kappa"] = kappa

    def part(f, name, year, d):
        X = f.design.X(np.asarray(year), np.asarray(d)).tocsc()
        cols = f.design.columns_of(name)
        return np.asarray(X[:, cols] @ f.beta[cols]).ravel()

    window = np.arange(*doy_range)
    yr = np.full(len(window), args.year)
    out["components"] = {
        "doy": window.tolist(),
        "season": rounded(part(fit_d, "season", yr, window), 3),
        "intercept": float(fit_d.beta[fit_d.design.columns_of("intercept")][0]),
        "years": years.tolist(),
        "trend": rounded(part(fit_d, "trend", years, np.full(len(years), doy_range[0])), 3),
        "year": rounded(part(fit_d, "year", years, np.full(len(years), doy_range[0])), 3),
        "beta": dict(zip(ARMS["D"], rounded(fit_d.beta[fit_d.design.columns_of("weather")], 3))),
    }

    # The year shown: log rate (posterior band), the daily process and the episode curve, counts,
    # and the fills of its hidden days.
    rows = frame.year.eq(args.year).to_numpy()
    f_year = frame[rows]
    rng = np.random.default_rng(SEED)
    year_out = {
        "doy": f_year.doy.tolist(),
        "date": f_year.date.dt.strftime("%Y-%m-%d").tolist(),
        "y": f_year.y.astype(int).tolist(),
        "c": rounded(f_year.c, 3),
        "rain": rounded(raw.log_rain[rows], 3),
        "daily": rounded(part(fit_d, "daily", f_year.year, f_year.doy), 3),
        "episode": rounded(part(fit_p, "episode", f_year.year, f_year.doy), 3),
        "weather": rounded(
            np.asarray(
                fit_d.design.X(f_year.year.to_numpy(), f_year.doy.to_numpy()).tocsc()[
                    :, fit_d.design.columns_of("weather")
                ]
                @ fit_d.beta[fit_d.design.columns_of("weather")]
            ).ravel(),
            3,
        ),
    }
    for arm, f in (("P", fit_p), ("D", fit_d)):
        eta = T.eta_draws(f, f_year.year, f_year.doy, f.draws(DRAWS, rng))
        year_out[f"log_rate_{arm}"] = {
            q: rounded(np.quantile(eta, p, axis=0), 3)
            for q, p in (("lo", 0.1), ("mid", 0.5), ("hi", 0.9))
        }
    test = obs_c[hidden].groupby("date").agg(count=("count", "sum"), hidden_c=("c", "sum"))
    missing = frame.date.map(test.hidden_c).fillna(0).to_numpy()
    for arm, f in (("P", fit_p), ("D", fit_d)):
        draws = T.fill_draws(
            f, frame, frame.c.to_numpy() + missing, n=DRAWS, seed=SEED, kappa=kappa
        )
        missed = (draws - frame.y.to_numpy() - frame.extra.to_numpy())[:, rows]
        year_out[f"fill_{arm}"] = {
            q: rounded(np.quantile(missed, p, axis=0), 1)
            for q, p in (("q10", 0.1), ("q50", 0.5), ("q90", 0.9))
        } | {"mean": rounded(missed.mean(axis=0), 1)}
    year_out["hidden_count"] = rounded(f_year.date.map(test["count"]).fillna(-1), 0)
    year_out["hidden_c"] = rounded(missing[rows], 3)
    year_out["hidden_kind"] = f_year.date.map(mask.set_index("date").kind).fillna("").tolist()
    out["year_series"] = year_out

    # --- saved tables ---------------------------------------------------------------------------
    steps = LOGS / "steps"
    fit_rows = pd.concat(pd.read_csv(p) for p in sorted(steps.glob("*_D_fit.csv")))
    out["fits_D"] = (
        fit_rows[
            ["english_name", "draw", "tau", "theta", "kappa"]
            + [c for c in fit_rows if c.startswith("beta_")]
        ]
        .round(4)
        .to_dict(orient="records")
    )
    i_rows = pd.concat(pd.read_csv(p) for p in sorted(steps.glob("*_I_fit.csv")))
    out["gamma_I"] = (
        i_rows[[c for c in i_rows if c.startswith("gamma_")]].median().round(3).to_dict()
    )
    scores = pd.read_csv(LOGS / "scores/scores.csv")
    out["scores"] = scores.round(5).fillna("").to_dict(orient="records")
    out["season_by_species"] = (
        pd.read_csv(LOGS / "scores/season_by_species.csv").round(5).to_dict(orient="records")
    )
    lock = pd.read_csv(LOGS / "lockbox-scores/scores.csv")
    out["lockbox"] = lock.round(5).fillna("").to_dict(orient="records")
    out["lockbox_by_species"] = (
        pd.read_csv(LOGS / "lockbox-scores/season_by_species.csv")
        .round(5)
        .to_dict(orient="records")
    )
    audit = {}
    for name in (
        "missing_by_rain",
        "missing_by_month",
        "missing_day_odds",
        "uncounted_by_tau",
        "days_by_era",
        "start_end_by_rain",
        "uncounted_hour_odds",
    ):
        audit[name] = pd.read_csv(AUDIT / f"{name}.csv").round(4).to_dict(orient="records")
    out["audit"] = audit
    masks = pd.concat(
        pd.read_csv(MASKS / f"draw{k}.csv", parse_dates=["date"]).assign(draw=k) for k in range(5)
    )
    out["mask_counts"] = (
        masks.assign(year=masks.date.dt.year)
        .groupby(["draw", "kind"])
        .size()
        .reset_index(name="n")
    ).to_dict(orient="records")
    out["core"] = list(CORE)
    text = json.dumps(out, allow_nan=False, default=float)
    OUT.write_text(text)
    PAGE.write_text(TEMPLATE.read_text().replace("/*__DATA__*/", text))
    print(f"wrote {OUT} and {PAGE}")


if __name__ == "__main__":
    main()
