"""The weather effects of every taxon with a production trend, found on odd years and confirmed on
even ones (`WEATHER_PLAN.md`, "the broad panel").

Run from the repository root, one thread a process, at low priority: OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 10 uv run --with 'pyarrow<20' python
scripts/hierarchical/weather_panel.py > logs/hierarchical/weather_panel.log

Each taxon's daily frame is production's (`pipeline` job, `settings`: start year, model window,
trend or not; species only, not the groups of species), its daily weather terms the production
profile's weighted means, standardised on its counted days. Each of `--arms` (`run_steps.ARMS`) is
fitted three times: all years, odd years, even years (the other years' days left uncounted). Writes
`logs/hierarchical/panel/fits_<arms>.csv` (one row per taxon, arm and half) and
`evidence_<arms>.csv`: the counted days in bins of each term (`BINS`) and in wind sectors, with
their birds over the usual for the date and year (the last arm's fit on all years without its
weather and episodes).
"""

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from common import LOGS, ROOT
from run_steps import ARMS, COEF_DRAWS, SEED, daily_terms, hourly_weather
from weather_design import fit as fit_arm

from defile_explore import accounts as A
from defile_explore import export as E
from defile_explore import pipeline as L
from defile_explore import profile as P
from defile_explore import settings as X
from defile_explore import trend as T
from defile_explore import window as W

OUT = LOGS / "panel"
HALVES = {"all": None, "odd": 1, "even": 0}
# The counted days beside each effect: bins of the daily term (its own units), lower edges.
BINS = {
    "rain": ([-np.inf, 0.05, np.log1p(0.5)], ["dry", "light rain", "rain"]),
    "rain_yesterday": ([-np.inf, 0.05, np.log1p(0.5)], ["dry", "light rain", "rain"]),
    "sunshine": ([-np.inf, 0.25, 0.75], ["overcast", "mixed", "sunny"]),
    "boundary_layer": ([-np.inf, 0.4, 0.8], ["shallow", "medium", "deep"]),
    "wind_speed": ([-np.inf, 2.0, 4.0], ["light", "moderate", "strong"]),
    "pressure_change": ([-np.inf, -3.0, 3.0], ["falling", "steady", "rising"]),
    "temperature_anomaly": ([-np.inf, -2.0, 2.0], ["cold", "usual", "warm"]),
}
CALM = 2.0  # m/s: a day's mean wind below this has no sector
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
weather = None
ARGS = None


def setup(args):
    global weather, ARGS
    weather, ARGS = hourly_weather(), args


def taxon_fits(job: dict) -> list[dict]:
    """The rows of one taxon (none without a trend, or if it fails: reported)."""
    try:
        return fits_of(job)
    except Exception as error:  # one taxon's failure must not lose the others
        print(f"{job['taxon']['english_name']}: FAILED {error!r}", flush=True)
        return [], []


def evidence(f: pd.DataFrame, raw: pd.DataFrame, usual: np.ndarray, taxon: dict) -> list[dict]:
    """The counted days in bins of each term and in wind sectors: days, birds, and birds over the
    usual for the date and year (`usual`: the fit without its weather and episodes)."""
    on = f.c.gt(0).to_numpy()
    expected = f.c.to_numpy() * usual
    groups = {}
    for term, (edges, labels) in BINS.items():
        if term in raw:
            groups[term] = pd.cut(
                raw[term].to_numpy(), [*edges, np.inf], labels=labels, right=False
            )
    speed = np.hypot(raw.wind_u100, raw.wind_v100).to_numpy()
    origin = (np.degrees(np.arctan2(raw.wind_u100, raw.wind_v100)).to_numpy() + 180) % 360
    sector = np.array(SECTORS)[((origin + 22.5) // 45).astype(int) % 8]
    groups["wind_sector"] = np.where(speed < CALM, "calm", sector)
    rows = []
    for term, labels in groups.items():
        t = pd.DataFrame({"bin": np.asarray(labels)[on], "y": f.y[on], "e": expected[on]})
        for label, g in t.groupby("bin", observed=True):
            rows.append(
                {
                    "taxon_id": taxon["taxon_id"],
                    "term": term,
                    "bin": label,
                    "days": len(g),
                    "birds": g.y.sum(),
                    "relative": g.y.sum() / g.e.sum(),
                }
            )
    return rows


def fits_of(job: dict) -> list[dict]:
    """The rows of one taxon, following `pipeline.build_taxon`."""
    taxon, days, effort, profile, last = (
        job["taxon"],
        job["days"],
        job["effort"],
        job["profile"],
        job["last_year"],
    )
    counted = days.groupby(days["date"].dt.year)["count"].sum()
    settings, _ = X.resolve(taxon, job["demography"], counted, job["overrides"], last)
    start = settings["start_year"].value
    c = P.coverage(effort, profile)
    rule = W.windows(effort, last)
    settings |= X.resolve_windows(taxon["taxon_id"], rule, job["overrides"])
    if not settings["trend"].value:
        return [], []
    frame = T.model_frame(days, effort, c, start, last, settings["model_window"].value)
    years = np.arange(start, last + 1)
    doy_range = (int(frame.doy.min()), int(frame.doy.max()))
    raw = daily_terms(frame, profile, weather)
    on = frame.c.gt(0).to_numpy()
    terms = (raw - raw[on].mean()) / raw[on].std()
    rows, support = [], []
    for half, parity in HALVES.items():
        f = frame.copy()
        if parity is not None:
            f.loc[f.year % 2 != parity, ["y", "c", "extra"]] = 0.0
        for arm in ARGS.arms:
            started = time.perf_counter()
            fit = fit_arm(f, years, doy_range, terms[ARMS[arm]])
            if half == "all" and arm == ARGS.arms[-1]:
                usual = np.exp(
                    T.eta_draws(
                        fit, f.year, f.doy, fit.beta[None], without=("weather", "episode")
                    )[0]
                )
                support = evidence(f, raw, usual, taxon)
            columns = fit.design.columns_of("weather")
            spread = fit.draws(COEF_DRAWS, np.random.default_rng(SEED))[:, columns].std(axis=0)
            rows.append(
                {
                    "taxon_id": taxon["taxon_id"],
                    "english_name": taxon["english_name"],
                    "family": taxon["family"],
                    "arm": arm,
                    "half": half,
                    "first_year": start,
                    "counted_days": int(f.c.gt(0).sum()),
                    "birds": float(f.y.sum()),
                    "theta": fit.theta,
                    "seconds": time.perf_counter() - started,
                    **{f"beta_{k}": v for k, v in zip(ARMS[arm], fit.beta[columns])},
                    **{f"se_{k}": v for k, v in zip(ARMS[arm], spread)},
                    **{f"sd_{k}": raw[k][on].std() for k in ARMS[arm]},
                }
            )
    print(f"{taxon['english_name']}: {len(rows)} fits, {frame.c.gt(0).sum()} days", flush=True)
    return rows, support


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) // 3))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--arms", nargs="+", default=["W3"], help="the last gives the evidence")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ebird = pd.read_csv(args.data_dir / E.EBIRD_TAXONOMY_FILE)
    shared = L.load_shared(str(args.data_dir), ebird)
    ids = shared.taxa.loc[shared.taxa.taxon_rank.eq("species"), "taxon_id"]
    jobs = L.taxon_jobs(
        shared,
        ids,
        X.load_overrides(),
        A.load_accounts(taxon_ids=shared.taxa["taxon_id"]),
        str(args.data_dir),
        benchmark=False,
    )
    with ProcessPoolExecutor(args.workers, initializer=setup, initargs=(args,)) as pool:
        results = list(pool.map(taxon_fits, jobs))
    rows = [r for rs, _ in results for r in rs]
    name = "_".join(args.arms)
    pd.DataFrame(rows).to_csv(OUT / f"fits_{name}.csv", index=False)
    pd.DataFrame([r for _, rs in results for r in rs]).to_csv(
        OUT / f"evidence_{name}.csv", index=False
    )
    print(f"done: {len({r['taxon_id'] for r in rows})} taxa", flush=True)


if __name__ == "__main__":
    main()
