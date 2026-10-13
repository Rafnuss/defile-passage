"""Choose the small seasonal specification using retained-data CV scores only."""

from pathlib import Path
from shutil import copyfile

import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[2]
for panel in ["priority", "passerines"]:
    out = root / f"logs/simple-gaps-selected-{panel}"
    out.mkdir(exist_ok=True)
    manifest = pd.read_csv(root / f"logs/simple-gaps-design-{panel}/manifest.csv")
    decisions, predictions, diagnostics, status = [], [], [], []
    for context in manifest.itertuples():
        candidates = []
        for variant, prefix in [
            ("year_weather", "simple-gaps-newton"),
            ("year_season_weather", "simple-gaps-season"),
        ]:
            folder = root / f"logs/{prefix}-{panel}/{variant}/{context.key}"
            score = pd.read_csv(folder / f"{context.key}_smoothing_scores.csv").daily_mae.min()
            candidates.append(dict(variant=variant, folder=folder, cv_mae=score))
        chosen = min(candidates, key=lambda row: row["cv_mae"])
        # Validation counts and predictions are read only after this choice.
        frame = pd.read_csv(chosen["folder"] / "predictions.csv")
        frame["variant"] = "selected_weather"
        frame["selected_variant"] = chosen["variant"]
        predictions.append(frame)
        diagnostic = pd.read_csv(chosen["folder"] / "diagnostics.csv")
        diagnostic["selected_variant"] = chosen["variant"]
        diagnostic["variant"] = "selected_weather"
        diagnostics.append(diagnostic)
        status.append(dict(key=context.key, variant="selected_weather", passed=True))
        decisions.append(
            dict(
                key=context.key,
                selected_variant=chosen["variant"],
                cv_mae=chosen["cv_mae"],
                simple_cv_mae=candidates[0]["cv_mae"],
                seasonal_cv_mae=candidates[1]["cv_mae"],
            )
        )
        fit_path = chosen["folder"] / f"{context.key}_fit.npz"
        copyfile(fit_path, out / f"{context.key}_fit.npz")
        coefficients = pd.read_csv(
            root / f"logs/simple-gaps-design-{panel}/{context.key}_{chosen['variant']}_terms.csv"
        )
        coefficients["coefficient"] = np.load(fit_path)["coefficients"]
        coefficients.to_csv(out / f"{context.key}_coefficients.csv", index=False)
    pd.concat(predictions, ignore_index=True).to_csv(out / "predictions.csv", index=False)
    pd.concat(diagnostics, ignore_index=True).to_csv(out / "diagnostics.csv", index=False)
    pd.DataFrame(status).to_csv(out / "status.csv", index=False)
    pd.DataFrame(decisions).to_csv(out / "selection.csv", index=False)
    print(panel, pd.DataFrame(decisions).selected_variant.value_counts().to_dict())
