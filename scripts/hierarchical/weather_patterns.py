"""Patterns in the broad panel's weather effects: odd years find, even years confirm.

Run from the repository root after `weather_panel.py` (every `fits_<arms>.csv` is read): uv run
--with matplotlib python scripts/hierarchical/weather_patterns.py \     >
logs/hierarchical/weather_patterns.log

Effects from `weather_effects.effects`, per taxon, arm and half. A taxon's effect is `replicated`
when it is clear on odd years and clear with the same sign on even years (for the wind's direction:
a clear direction within `MAX_ANGLE` of the odd years'); `not confirmed` when clear on odd years
only; `opposite` when the halves are clear with opposite signs; `none` when not clear on odd years.
Groups by family (`flight_groups.tsv`). Writes `logs/hierarchical/panel/` `effects.csv`,
`status.csv`, `groups.csv` and `heatmap_<arm>.png` (all years' effects, every cell drawn; faded
when not clear on all years; a dot when replicated).
"""

import argparse

import matplotlib
import numpy as np
import pandas as pd
from common import LOGS, ROOT
from weather_effects import clear, effects

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PANEL = LOGS / "panel"
GROUPS = ROOT / "scripts/hierarchical/flight_groups.tsv"
GROUP_ORDER = ["soaring", "falcons", "waterbirds", "pigeons", "aerial insectivores", "passerines"]
FADE = 0.15  # share of its colour a cell keeps when not clear
MAX_ANGLE = 60.0  # degrees between the halves' preferred wind directions
COLUMNS = {  # heat-map column: header
    "rain": "rain\n1 mm/h",
    "rain_yesterday": "rain\nyesterday",
    "sunshine": "sunny vs\novercast",
    "low_cloud": "low\ncloud",
    "boundary_layer": "mixing\n+500 m",
    "wind_from_NE": "5 m/s\nfrom NE",
    "wind_from_SW": "5 m/s\nfrom SW",
    "wind_speed": "wind\n+5 m/s",
    "pressure_change": "pressure\n+5 hPa",
    "temperature_change": "3 °C colder\nthan yesterday",
    "temperature_anomaly": "3 °C colder\nthan usual",
}


def status(odd: pd.Series, even: pd.Series) -> str:
    if not odd.clear:
        return "none"
    if odd.term == "wind_direction":
        angle = abs((even.origin - odd.origin + 180) % 360 - 180)
        return "replicated" if even.clear and angle <= MAX_ANGLE else "not confirmed"
    if clear(even.log_effect, even.se):
        return "replicated" if np.sign(even.log_effect) == np.sign(odd.log_effect) else "opposite"
    return "not confirmed"


def heatmap(table: pd.DataFrame, arm: str, path):
    t = table[table.arm.eq(arm) & table.half.eq("all") & table.term.isin(COLUMNS)]
    rows = (
        t.drop_duplicates("english_name")
        .assign(order=lambda f: f.group.map(GROUP_ORDER.index))
        .sort_values(["order", "birds"], ascending=[True, False])
    )
    names, cols = list(rows.english_name), [c for c in COLUMNS if c in set(t.term)]
    cell = t.set_index(["english_name", "term"])
    fig, ax = plt.subplots(figsize=(1.0 * len(cols) + 3, 0.22 * len(names) + 1.5))
    for i, name in enumerate(names):
        for j, term in enumerate(cols):
            if (name, term) not in cell.index:
                continue
            r = cell.loc[(name, term)]
            v = np.clip(r.log_effect / np.log(4), -1, 1)  # x4 and x1/4 at the ends
            colour = np.array(plt.cm.RdBu(0.5 - v / 2)[:3])
            if not r.clear:  # faded towards white
                colour = 1 - FADE * (1 - colour)
            ax.add_patch(plt.Rectangle((j, i), 1, 1, color=colour))
            mark = " ●" if r.status == "replicated" else ""
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{np.exp(r.log_effect):.2g}{mark}",
                ha="center",
                va="center",
                fontsize=6,
                color="black" if r.clear else "0.5",
            )
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(names), 0)
    ax.set_xticks(np.arange(len(cols)) + 0.5, [COLUMNS[c] for c in cols], fontsize=7)
    ax.xaxis.tick_top()
    labels = [f"{n} ({g})" for n, g in zip(names, rows.group)]
    ax.set_yticks(np.arange(len(names)) + 0.5, labels, fontsize=6)
    for k in np.flatnonzero(np.diff(rows.order.to_numpy())) + 1:
        ax.axhline(k, color="black", lw=0.8)
    ax.set_title(
        f"Weather effects, arm {arm}, all years: the day's passage x (red > 1, blue < 1);"
        " faded: not clear; ●: replicated (odd years find, even confirm)",
        fontsize=8,
        loc="left",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    fits = pd.concat(pd.read_csv(p) for p in sorted(PANEL.glob("fits_*.csv")))
    groups = pd.read_csv(GROUPS, sep="\t").set_index("family").group
    fits["group"] = fits.family.map(groups)
    assert (
        fits.group.notna().all()
    ), f"families without a group: {set(fits.family[fits.group.isna()])}"
    keys = ["taxon_id", "english_name", "group", "arm", "half", "birds", "counted_days"]
    table = pd.concat(
        [effects(row).assign(**{k: row[k] for k in keys}) for _, row in fits.iterrows()],
        ignore_index=True,
    )
    wide = table.set_index(["taxon_id", "arm", "term", "half"])
    rows = []
    for (taxon, arm, term), _ in table.groupby(["taxon_id", "arm", "term"]):
        odd = wide.loc[(taxon, arm, term, "odd")].copy()
        odd["term"] = term
        verdict = status(odd, wide.loc[(taxon, arm, term, "even")])
        rows.append({"taxon_id": taxon, "arm": arm, "term": term, "status": verdict})
    found = pd.DataFrame(rows)
    table = table.merge(found, on=["taxon_id", "arm", "term"])
    table.to_csv(PANEL / "effects.csv", index=False)

    pd.set_option("display.width", 250)
    print(
        f"{fits.taxon_id.nunique()} taxa: "
        + ", ".join(
            f"{g} {n}" for g, n in fits.drop_duplicates("taxon_id").group.value_counts().items()
        )
    )
    for arm in sorted(table.arm.unique()):
        t = table[table.arm.eq(arm) & table.half.eq("all")]
        counts = t.pivot_table(index="term", columns="status", values="taxon_id", aggfunc="count")
        print(f"\n## {arm}: odd years find, even confirm (taxa)\n")
        print(
            counts.fillna(0)
            .astype(int)
            .reindex(columns=["replicated", "not confirmed", "opposite", "none"], fill_value=0)
            .to_string()
        )
        g = (
            t.groupby(["group", "term"])
            .agg(
                taxa=("taxon_id", "nunique"),
                median_effect=("log_effect", lambda e: np.exp(e.median())),
                clear_up=("log_effect", lambda e: (t.loc[e.index, "clear"] & e.gt(0)).sum()),
                clear_down=("log_effect", lambda e: (t.loc[e.index, "clear"] & e.lt(0)).sum()),
                replicated=("status", lambda s: s.eq("replicated").sum()),
            )
            .reset_index()
        )
        g.to_csv(PANEL / f"groups_{arm}.csv", index=False)
        print(f"\n## {arm}: by group (all years; median effect over the group's taxa)\n")
        print(
            g.pivot(index="term", columns="group", values="median_effect")[
                [c for c in GROUP_ORDER if c in set(g.group)]
            ].to_string(float_format=lambda v: f"{v:.2f}")
        )
        print(f"\n## {arm}: by group, taxa clearly up / down / replicated\n")
        g["summary"] = (
            g.clear_up.astype(str)
            + "/"
            + g.clear_down.astype(str)
            + "/"
            + g.replicated.astype(str)
            + " of "
            + g.taxa.astype(str)
        )
        print(
            g.pivot(index="term", columns="group", values="summary")[
                [c for c in GROUP_ORDER if c in set(g.group)]
            ].to_string()
        )
        wind = t[t.term.eq("wind_direction") & t.clear]
        print(f"\n## {arm}: preferred wind direction of the taxa with a clear one\n")
        print(
            wind.groupby("group")
            .origin.apply(lambda o: " ".join(f"{v:.0f}" for v in sorted(o)))
            .to_string()
        )
        heatmap(table, arm, PANEL / f"heatmap_{arm}.png")


if __name__ == "__main__":
    main()
