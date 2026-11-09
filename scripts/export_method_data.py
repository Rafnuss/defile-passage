"""Export date-specific coverage inputs for the illustrated methods, without refitting models."""

import json
import pickle
from pathlib import Path

import numpy as np

from defile_passage.export import EXPORT_DIR, STEPS_PER_HOUR
from defile_passage.pipeline import CACHE_DIR
from defile_passage.profile import PROFILE_DOY

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "website/public/data/methods"
    target.mkdir(parents=True, exist_ok=True)
    for path in target.glob("*.json"):
        path.unlink()
    manifest = json.loads((ROOT / "data" / EXPORT_DIR / "manifest.json").read_text())
    for path in sorted(
        (ROOT / "data" / CACHE_DIR).glob("shared-*.pkl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        with path.open("rb") as f:
            shared = pickle.load(f)
        if shared.metadata["built_at"] == manifest["dataset_built_at"]:
            break
    else:
        print("Date-specific methods inputs unavailable: no matching shared cache.")
        return
    effort = {}
    for row in shared.effort.itertuples():
        slots = np.asarray(row.slots)
        on = np.flatnonzero(slots > 0)
        effort[str(row.date.date())] = [[int(i), round(float(slots[i]), 8)] for i in on]
    (target / "effort.json").write_text(json.dumps(effort, separators=(",", ":")))
    for path in (ROOT / "data" / EXPORT_DIR / "species").glob("*.json"):
        data = json.loads(path.read_text())
        source = shared.source[data["taxon_id"]]
        profile = shared.profiles[data["taxon_id"] if source == "own" else source]
        out = {
            "doy_start": PROFILE_DOY[0],
            "per_hour": STEPS_PER_HOUR,
            "p": np.round(profile * STEPS_PER_HOUR, 7).tolist(),
        }
        (target / path.name).write_text(json.dumps(out, separators=(",", ":")))
    print("Exported matched date-specific profiles and counting slots for the methods.")


if __name__ == "__main__":
    main()
