"""Compare production's minimum daily coverage on fixed realistic development masks.

Run from the repository root with BLAS threads set to one:
    uv run python scripts/hierarchical/coverage_threshold.py --workers 4

Each fold learns its profile from retained hourly counts, then refits production's daily weather
GAM at every cutoff. Scores target exactly the same dates and observations, including zeros.
Posterior predictive means integrate coefficient uncertainty by Gaussian quadrature; Gamma and
flock sampling are integrated analytically. No production constant or export is changed.
"""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from common import CORE, LOGS, MASKS, ROOT, apply_mask, load_species
from numpy.polynomial.hermite import hermgauss
from run_steps import TIMED_FROM, interval_slots, training_profile

from defile_passage import export as E
from defile_passage import profile as P
from defile_passage import trend as T
from defile_passage import weather as W

THRESHOLDS = (0, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5)
QUADRATURE = 64
BOOTSTRAPS = 2000
SEED = 20261028
REFERENCE_COVERAGE = 0.1  # the production default when this experiment was run


def rate_mean(fit, target, nodes=QUADRATURE):
    """Mean conditional daily intensity, integrating its marginal Gaussian log intensity."""
    X = fit.design.X(target.year.to_numpy(), target.doy.to_numpy())
    mean = X @ fit.beta
    sd = np.sqrt(np.square(X @ fit.H.draws(np.eye(len(fit.beta)))).sum(axis=1))
    x, w = hermgauss(nodes)
    mu = np.exp(mean[:, None] + np.sqrt(2) * sd[:, None] * x)
    rate = (fit.theta + target.y.to_numpy()[:, None]) / (
        fit.theta / mu + target.c.to_numpy()[:, None]
    )
    result = rate @ w / np.sqrt(np.pi)
    unobserved = target.c.eq(0).to_numpy()
    result[unobserved] = (1 + target.y.to_numpy()[unobserved] / fit.theta) * np.exp(
        mean[unobserved] + sd[unobserved] ** 2 / 2
    )
    return result


def retained_profile(obs, parts, hidden):
    """Production profile learned only from surviving hourly observations."""
    timed = obs[~hidden & obs.year.ge(TIMED_FROM) & obs.exposure_hours.le(1) & ~obs.weather_stop]
    sample = parts[parts.observation_id.isin(timed.observation_id)].merge(
        timed[["observation_id", "count"]], on="observation_id"
    )
    sample = sample[~sample.observation_id.duplicated(keep=False)].copy()
    sample["exposure_hours"] = sample.fraction
    return training_profile(sample)


def low_coverage_mask(obs, parts, obs_slots, mask, fold):
    """End selected recent days near a fixed grid of low retained coverages, at whole intervals."""
    eligible = obs.groupby("date").agg(
        n=("observation_id", "size"),
        longest=("exposure_hours", "max"),
        stop=("weather_stop", "any"),
    )
    dates = mask.loc[mask.kind.eq("day"), "date"]
    dates = eligible.index[
        eligible.index.isin(dates) & eligible.n.ge(6) & eligible.longest.le(1) & ~eligible.stop
    ]
    profile = retained_profile(obs, parts, obs.date.isin(dates).to_numpy())
    c = (
        obs_slots
        * profile[
            np.clip(T.season_day(pd.DatetimeIndex(obs.date)), *P.PROFILE_DOY) - P.PROFILE_DOY[0]
        ]
    ).sum(axis=1)
    rng = np.random.default_rng(SEED + fold)
    desired = rng.permutation(np.resize(np.array(THRESHOLDS[1:]), len(dates)))
    rows = []
    for date, share in zip(dates, desired):
        day = obs[obs.date.eq(date)].sort_values("start")
        cumulative = np.cumsum(c[day.index.to_numpy()])[:-1]
        keep = np.argmin(np.abs(cumulative - share)) + 1
        rows.append(
            dict(date=date, kind="end", hide_from=day.start.iloc[keep], desired_coverage=share)
        )
    return pd.DataFrame(rows)


def run_species(work):
    """Refit every threshold and mask for one species; save predictions and fitting evidence."""
    species, thresholds, folds, out, mask_mode = work
    obs, parts = load_species(species)
    # Recompute interval slots: do not rely on the older cache's row-count-only key.
    slots = interval_slots(parts)
    row_of = obs.set_index("observation_id").index.get_indexer(parts.observation_id)
    obs_slots = np.zeros((len(obs), E.SLOTS))
    np.add.at(obs_slots, row_of, slots)
    years = np.arange(obs.year.min(), obs.year.max() + 1)
    bounds = (int(parts.doy.min()), int(parts.doy.max()))
    calendar = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    doy = T.season_day(calendar)
    calendar = calendar[
        E.in_window(pd.Series(calendar)).to_numpy() & (doy >= bounds[0]) & (doy <= bounds[1])
    ]
    weather = W.hourly(str(ROOT / "data"))
    truth = obs.groupby("year")["count"].sum()
    rows, diagnostics = [], []
    for fold in folds:
        mask = pd.read_csv(MASKS / f"draw{fold}.csv", parse_dates=["date"])
        mask["hide_from"] = pd.to_datetime(mask.hide_from, utc=True)
        if mask_mode == "low-coverage":
            mask = low_coverage_mask(obs, parts, obs_slots, mask, fold)
            mask.to_csv(out / f"{species.replace(' ', '_')}_mask{fold}.csv", index=False)
        hidden = apply_mask(obs, mask).to_numpy()
        profile = retained_profile(obs, parts, hidden)
        c = (
            obs_slots
            * profile[
                np.clip(T.season_day(pd.DatetimeIndex(obs.date)), *P.PROFILE_DOY)
                - P.PROFILE_DOY[0]
            ]
        ).sum(axis=1)
        observed = obs.assign(c=c)
        daily = observed[~hidden].groupby("date").agg(y=("count", "sum"), c=("c", "sum"))
        base = pd.DataFrame(
            {"date": calendar, "year": calendar.year, "doy": T.season_day(calendar)}
        )
        base = base.join(daily, on="date").fillna({"y": 0, "c": 0})
        raw = W.daily_terms(base.date, base.doy.to_numpy(), profile, weather)
        assert np.isfinite(raw.to_numpy()).all()
        target = (
            observed[hidden].groupby("date").agg(count=("count", "sum"), hidden_c=("c", "sum"))
        )
        selected = base.date.isin(target.index)
        target = target.reindex(base.date[selected]).reset_index()
        target["kept_c"] = base.loc[selected, "c"].to_numpy()
        target["kind"] = np.where(target.date.isin(mask.date[mask.kind.eq("day")]), "day", "end")
        target["year"] = target.date.dt.year
        target["observed_truth"] = target.year.map(truth)
        for threshold in thresholds:
            started = perf_counter()
            frame = base.copy()
            low = frame.c.lt(threshold)
            frame["extra"] = frame.y.where(low, 0)
            frame.loc[low, ["y", "c"]] = 0
            terms, _ = W.standardise(raw, frame.c.gt(0).to_numpy())
            frame = frame.assign(
                **{col: terms[name].to_numpy() for col, name in zip(T.WEATHER_COLUMNS, W.TERMS)}
            )
            fit = T.fit("gam", frame, years, bounds)
            rate = rate_mean(fit, frame[selected])
            check = rate_mean(fit, frame[selected], nodes=QUADRATURE // 2)
            result = target.copy()
            # Match fill_draws over the target's original observed coverage. Below the cutoff,
            # retained birds are extra, and their coverage is also predicted by production.
            dropped_c = target.kept_c.to_numpy() - frame.loc[selected, "c"].to_numpy()
            result["predicted"] = rate * (target.hidden_c.to_numpy() + dropped_c)
            result["hidden_only"] = rate * target.hidden_c.to_numpy()
            result["threshold"] = threshold
            result["fold"] = fold
            result["english_name"] = species
            rows.append(result)
            diagnostics.append(
                dict(
                    english_name=species,
                    fold=fold,
                    threshold=threshold,
                    fitted_days=int(frame.c.gt(0).sum()),
                    dropped_days=int((low & base.c.gt(0)).sum()),
                    affected_targets=int((dropped_c > 0).sum()),
                    theta=fit.theta,
                    log_marginal=fit.log_marginal,
                    seconds=perf_counter() - started,
                    quadrature_relative_difference=float(
                        np.max(np.abs(rate - check) / (1 + rate))
                    ),
                )
            )
        print(f"{species}, fold {fold}: {len(target)} target days", flush=True)
    stem = species.replace(" ", "_")
    pd.concat(rows, ignore_index=True).to_csv(out / f"{stem}_days.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(out / f"{stem}_fits.csv", index=False)


def summarise(out):
    """Equal-species scores and paired year-cluster bootstrap differences from the default."""
    days = pd.concat(pd.read_csv(p, parse_dates=["date"]) for p in out.glob("*_days.csv"))
    days["error"] = days.predicted - days["count"]
    days["hidden_error"] = days.hidden_only - days["count"]
    season = days.groupby(["english_name", "threshold", "fold", "year"], as_index=False).agg(
        error=("error", "sum"),
        hidden_error=("hidden_error", "sum"),
        observed_truth=("observed_truth", "first"),
    )
    season["relative"] = season.error / season.observed_truth
    season["hidden_relative"] = season.hidden_error / season.observed_truth
    season.to_csv(out / "season.csv", index=False)
    results = []
    for label, d in {
        "all": days,
        "partial": days[days.kind.eq("end")],
        "whole": days[days.kind.eq("day")],
        "coverage_below_10pct": days[days.kept_c.gt(0) & days.kept_c.lt(REFERENCE_COVERAGE)],
    }.items():
        per = d.groupby(["threshold", "english_name"]).agg(
            daily_mae=("error", lambda x: x.abs().mean()),
            bias=("error", "mean"),
            hidden_only_mae=("hidden_error", lambda x: x.abs().mean()),
        )
        score = per.groupby("threshold").mean().reset_index().assign(subset=label)
        score["n_days"] = d.groupby("threshold").size().reindex(score.threshold).to_numpy()
        results.append(score)
    summary = pd.concat(results, ignore_index=True)
    per_year = (
        season.groupby(["threshold", "english_name", "year"])
        .agg(
            season_error=("relative", lambda x: x.abs().mean()),
            season_bias=("relative", "mean"),
            hidden_only_season_error=("hidden_relative", lambda x: x.abs().mean()),
        )
        .reset_index()
    )
    s = (
        per_year.groupby(["threshold", "english_name"])
        .mean(numeric_only=True)
        .groupby("threshold")
        .mean()
    )
    summary = summary.merge(s.drop(columns="year"), on="threshold", how="left")
    daily_year = (
        days.groupby(["threshold", "english_name", "year"])
        .error.agg(total=lambda x: x.abs().sum(), n="size")
        .reset_index()
    )
    rng = np.random.default_rng(SEED)
    years = np.sort(days.year.unique())
    weights = rng.multinomial(len(years), np.full(len(years), 1 / len(years)), size=BOOTSTRAPS)
    intervals = []
    for metric, table in (("season_error", per_year), ("daily_mae", daily_year)):
        boot = {}
        for threshold, g in table.groupby("threshold"):
            by_species = []
            for _, sp in g.groupby("english_name"):
                sp = sp.set_index("year").reindex(years)
                if metric == "season_error":
                    by_species.append(
                        (weights @ sp[metric].fillna(0).to_numpy())
                        / (weights @ sp[metric].notna().to_numpy(float))
                    )
                else:
                    by_species.append(
                        (weights @ sp.total.fillna(0).to_numpy())
                        / (weights @ sp.n.fillna(0).to_numpy())
                    )
            boot[threshold] = np.mean(by_species, axis=0)
        for threshold in boot:
            lo, hi = np.quantile(boot[threshold] - boot[REFERENCE_COVERAGE], [0.025, 0.975])
            intervals.append(dict(threshold=threshold, metric=metric, delta_lo=lo, delta_hi=hi))
    summary.loc[summary.subset.ne("all"), list(s.drop(columns="year").columns)] = np.nan
    summary.to_csv(out / "summary.csv", index=False)
    pd.DataFrame(intervals).to_csv(out / "paired_intervals.csv", index=False)
    per_year.to_csv(out / "by_species_year.csv", index=False)
    import matplotlib.pyplot as plt

    overall = summary[summary.subset.eq("all")].set_index("threshold")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), layout="constrained")
    for ax, metric, label in zip(
        axes,
        ("daily_mae", "season_error"),
        ("Daily MAE (birds)", "Season reconstruction error (%)"),
    ):
        scale = 100 if metric == "season_error" else 1
        ax.plot(overall.index * 100, overall[metric] * scale, "o-", color="#28756c")
        ax.axvline(100 * REFERENCE_COVERAGE, color="#a65b32", linestyle="--", label="Previous 10%")
        ax.set(xlabel="Minimum coverage (%)", ylabel=label)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
    fig.suptitle(
        "Coverage cutoff: "
        + ("short mornings" if out.name.endswith("-low") else "realistic masks")
    )
    fig.savefig(out / "threshold_scores.png", dpi=180)
    plt.close(fig)
    print(summary[summary.subset.eq("all")].to_string(index=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--species", nargs="+", default=list(CORE))
    parser.add_argument("--thresholds", nargs="+", type=float, default=list(THRESHOLDS))
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--mask-mode", choices=["realistic", "low-coverage"], default="realistic")
    parser.add_argument("--out", type=Path, default=LOGS / "coverage-threshold")
    parser.add_argument("--summarise-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.summarise_only:
        sources = list((ROOT / "src/defile_passage").glob("*.py"))
        sources += list(Path(__file__).parent.glob("*.py"))
        sources += [MASKS / f"draw{k}.csv" for k in args.folds]
        sources += [
            LOGS / "inputs" / f"{s.replace(' ', '_')}_{kind}.csv"
            for s in args.species
            for kind in ("observations", "components")
        ]
        sources += list((ROOT / "data/weather").glob("*.csv"))
        metadata = dict(
            mask_mode=args.mask_mode,
            species=args.species,
            thresholds=args.thresholds,
            folds=args.folds,
            git_head=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            numpy=np.__version__,
            pandas=pd.__version__,
            quadrature=QUADRATURE,
            sha256={
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sources
            },
        )
        (args.out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
        work = [(s, args.thresholds, args.folds, args.out, args.mask_mode) for s in args.species]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(run_species, work))
    summarise(args.out)


if __name__ == "__main__":
    main()
