"""Each taxon's weather effects from `W` fitted on all counted days, as the page would show them.

Run from the repository root after the full fits (`run_steps.py --arms W We --masks
logs/hierarchical/full --draws 0 --out logs/hierarchical/full-fits`): uv run python
scripts/hierarchical/weather_effects.py > logs/hierarchical/weather_effects.log

An effect is the multiplier of the day's expected passage for a fixed contrast in physical units
(`CONTRASTS`), with its 95% interval (normal on the log scale, from the posterior draws' standard
error; covariances between terms ignored). Wind: the u and v terms are a preferred direction (the
wind's origin that raises passage most) and an effect per m/s of wind from it; with the speed term,
the effect of `WIND_SPEED` from a given direction against calm (`WIND_FROM`). Display rule
(`WEATHER_PLAN.md`): `show` when the interval excludes 1 and the effect is at least `MIN_EFFECT`;
`caveat` when shown but the 1993-2013 effect departs from the later one (`We`: its departure's
interval excludes 0); `hide` otherwise.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from common import LOGS

Z95 = 1.96
CHI2_95 = 5.99  # two degrees of freedom: the wind's u and v together
MIN_EFFECT = 0.10  # at least x1.10 or x0.91 for its contrast
# term: (contrast in the daily term's own units, label)
CONTRASTS = {
    "rain": (np.log1p(1.0), "1 mm/h all day vs dry"),
    "rain_yesterday": (np.log1p(1.0), "1 mm/h all day yesterday vs dry"),
    "sunshine": (1.0, "sunny vs overcast"),
    "low_cloud": (1.0, "low cloud vs none"),
    "boundary_layer": (0.5, "500 m deeper mixing"),
    "wind_speed": (5.0, "5 m/s more wind, any direction"),
    "pressure_change": (5.0, "+5 hPa in 24 h"),
    "temperature_change": (-3.0, "3 °C colder than yesterday"),
    "temperature_anomaly": (-3.0, "3 °C colder than usual"),
}
WIND_SPEED = 5.0  # m/s
WIND_FROM = {"wind_from_NE": 45.0, "wind_from_SW": 225.0}  # origin, degrees
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def clear(log_effect: float, se: float) -> bool:
    return abs(log_effect) > Z95 * se and abs(log_effect) >= np.log1p(MIN_EFFECT)


def per_unit(row: pd.Series, term: str) -> tuple[float, float]:
    """A term's coefficient and standard error per unit of the daily term."""
    return row[f"beta_{term}"] / row[f"sd_{term}"], row[f"se_{term}"] / row[f"sd_{term}"]


def effects(row: pd.Series) -> pd.DataFrame:
    """The effects of one fit (`run_steps.py`'s `_fit.csv` row): one row per contrast, with
    `log_effect`, `se`, `clear`; the wind's preferred direction (`origin`, degrees) and its test
    (`chi2`) on the `wind_direction` row."""
    rows = []
    for term, (contrast, label) in CONTRASTS.items():
        if f"beta_{term}" not in row or pd.isna(row[f"beta_{term}"]):
            continue
        b, s = per_unit(row, term)
        rows.append(
            {"term": term, "contrast": label, "log_effect": b * contrast, "se": s * abs(contrast)}
        )
    (a, sa), (b, sb), (c, sc) = (
        per_unit(row, k) for k in ("wind_u100", "wind_v100", "wind_speed")
    )
    strength = np.hypot(a, b)
    origin = (np.degrees(np.arctan2(a, b)) + 180) % 360  # the vector is where the wind blows to
    rows.append(
        {
            "term": "wind_direction",
            "contrast": f"{WIND_SPEED:g} m/s from {COMPASS[int((origin + 22.5) // 45) % 8]}"
            f" ({origin:.0f}°), direction only",
            "log_effect": strength * WIND_SPEED,
            "se": np.hypot(a * sa, b * sb) / strength * WIND_SPEED,
            "origin": origin,
            "chi2": (a / sa) ** 2 + (b / sb) ** 2,
        }
    )
    for name, degrees in WIND_FROM.items():
        u, v = -np.sin(np.radians(degrees)), -np.cos(np.radians(degrees))
        rows.append(
            {
                "term": name,
                "contrast": f"{WIND_SPEED:g} m/s from {name[-2:]} vs calm",
                "log_effect": WIND_SPEED * (a * u + b * v + c),
                "se": WIND_SPEED * np.sqrt((u * sa) ** 2 + (v * sb) ** 2 + sc**2),
            }
        )
    out = pd.DataFrame(rows)
    out["clear"] = [clear(e, s) for e, s in zip(out.log_effect, out.se)]
    wind = out.term.eq("wind_direction")
    out.loc[wind, "clear"] = (out.chi2[wind] > CHI2_95) & (
        out.log_effect[wind] >= np.log1p(MIN_EFFECT)
    )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fits", type=Path, default=LOGS / "full-fits")
    args = parser.parse_args()
    fits = pd.concat(pd.read_csv(p) for p in args.fits.glob("*_fit.csv")).set_index(
        ["english_name", "arm"]
    )
    tables = []
    for species in sorted(fits.index.get_level_values(0).unique()):
        w, era = fits.loc[(species, "W")], fits.loc[(species, "We")]
        t = effects(w).assign(english_name=species)
        late = effects(era)
        unstable = {}
        for term in CONTRASTS:
            if f"beta_{term}_early" in era:
                shift, shift_se = era[f"beta_{term}_early"], era[f"se_{term}_early"]
                unstable[term] = abs(shift) > Z95 * shift_se
                b = late.set_index("term").log_effect.get(term)
                t.loc[t.term.eq(term), "effect_2014_2025"] = np.exp(b)
                t.loc[t.term.eq(term), "effect_1993_2013"] = np.exp(
                    b + shift / era[f"sd_{term}"] * CONTRASTS[term][0]
                )
        ea, eb = (era[f"beta_wind_{k}100_early"] for k in ("u", "v"))
        sea, seb = (era[f"se_wind_{k}100_early"] for k in ("u", "v"))
        unstable["wind_direction"] = (ea / sea) ** 2 + (eb / seb) ** 2 > CHI2_95
        t["class"] = np.where(
            ~t.clear, "hide", np.where(t.term.map(unstable).fillna(False), "caveat", "show")
        )
        tables.append(t)
    table = pd.concat(tables, ignore_index=True)
    table["effect"] = np.exp(table.log_effect)
    table["lo"] = np.exp(table.log_effect - Z95 * table.se)
    table["hi"] = np.exp(table.log_effect + Z95 * table.se)
    table.to_csv(args.fits / "effects.csv", index=False)
    pd.set_option("display.width", 250)
    for term, t in table.groupby("term", sort=False):
        print(f"\n## {term}: {t.contrast.iloc[0]}\n")
        cols = ["english_name", "effect", "lo", "hi", "class"]
        cols += [
            c for c in ("effect_1993_2013", "effect_2014_2025") if c in t and t[c].notna().any()
        ]
        cols += ["contrast"] if term == "wind_direction" else []
        print(t[cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print("\n## Classes\n")
    print(table.pivot(index="english_name", columns="term", values="class").to_string())


if __name__ == "__main__":
    main()
