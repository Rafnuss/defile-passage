"""Shared constants and helpers of the hierarchical line (scripts in this folder only)."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs/hierarchical"
AUDIT = LOGS / "audit"
MASKS = LOGS / "masks"
CORE = tuple(
    pd.read_csv(ROOT / "scripts/research/historical_core_scope.tsv", sep="\t")["english_name"]
)
# The defile-dataset release (copied by `build_explore.py --dataset`) and the observations built
# from it (`build_inputs.py`).
RELEASE = ROOT / "raw/dataset"
INPUTS = LOGS / "inputs"
WEATHER_DIR = ROOT / "raw/weather"  # hourly ERA5 at Defile (`fetch_weather.py`)
# The research line's inputs (old release, weather stops left out), replayed by the reference runs.
RESEARCH_DESIGN = ROOT / "logs/history-episode/design"
LOCKBOX_YEARS = (1993, 2021)  # the historical calendar masks' years
LOCKBOX_PHASES = (1, 2, 3, 4, 8, 9, 10, 11)  # two four-day masks, never scored before the end
CALENDAR_PHASES = {"1 day": (0,), "3 days": (5, 6, 7), "7 days": tuple(range(12, 19))}


def season_doy(dates: pd.Series) -> pd.Series:
    """Day of the year on a non-leap calendar (as the research masks use)."""
    dates = pd.to_datetime(dates)
    return dates.dt.dayofyear - (dates.dt.is_leap_year & dates.dt.month.gt(2))


def calendar_phase(dates: pd.Series) -> pd.Series:
    """Phase of the research's historical calendar masks: 21-day cycle shifted 4 days a year."""
    dates = pd.to_datetime(dates)
    return (season_doy(dates) - 3 + 4 * (dates.dt.year - 1993)) % 21


def in_lockbox(dates: pd.Series) -> pd.Series:
    dates = pd.to_datetime(dates)
    return dates.dt.year.between(*LOCKBOX_YEARS) & calendar_phase(dates).isin(LOCKBOX_PHASES)


def logistic(X: np.ndarray, y: np.ndarray, ridge: float = 1e-4) -> np.ndarray:
    """Logistic regression coefficients by Newton steps (a small ridge keeps empty cells
    finite)."""
    b = np.zeros(X.shape[1])
    for _ in range(100):
        p = 1 / (1 + np.exp(-(X @ b)))
        hess = X.T @ (X * (p * (1 - p))[:, None]) + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(hess, X.T @ (y - p) - ridge * b)
        b += step
        if np.abs(step).max() < 1e-9:
            break
    return b


def load_species(name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Observations (`weather_stop` flagged) and their hourly components of one species, 1993-2025,
    from `build_inputs.py`."""
    stem = INPUTS / name.replace(" ", "_")
    obs = pd.read_csv(f"{stem}_observations.csv")
    parts = pd.read_csv(f"{stem}_components.csv")
    for f, columns in ((obs, ("start", "end")), (parts, ("slot_start", "start", "end"))):
        for column in columns:
            f[column] = pd.to_datetime(f[column], utc=True, format="ISO8601")
    obs["date"] = pd.to_datetime(obs.date, format="ISO8601")
    parts = parts.merge(obs[["observation_id", "date", "year"]], on="observation_id")
    return obs, parts


def apply_mask(obs: pd.DataFrame, mask: pd.DataFrame) -> pd.Series:
    """Hidden observations under one mask draw: every observation of a hidden day, and those
    starting at or after a day's `hide_from` (an early end)."""
    whole = obs.date.isin(mask.loc[mask.kind.eq("day"), "date"])
    ends = mask[mask.kind.eq("end")].set_index("date").hide_from
    cut = obs.date.map(ends)
    return whole | (cut.notna() & obs.start.ge(cut))
