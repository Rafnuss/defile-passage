# Weather gap filling: consolidated research

Development is paused as of 12 October 2026. [MODEL_SPECIFICATION.md](MODEL_SPECIFICATION.md) is the authoritative model choice, specification, results and limitations. [GAP_FILL_PLAN.md](GAP_FILL_PLAN.md) records the final status of the original five goals.

**Retain one weather candidate:** the hourly count-rate model with current rain, wind, season, year, clock time, night status, solar radiation and low cloud. Its saved implementation is `weather_soaring` (runner variant `soaring`). **Keep the original production model for historical season totals:** the weather candidate has not passed that replacement criterion. There is no wet/dry or species-specific switching between models.

## Code and saved evidence

Run commands from the `defile-passage` repository root. The selected model uses `simple_rate_model.py` and `run_era5_features.py --variants soaring`. `prepare_historical_transfer.R` defines the base design; `prepare_era5_features.py` defines the added predictors. The runner reads the frozen forty-context designs in `logs/history-episode/design/`, not arbitrary new surveys. This is a reproducible research candidate, not a new production pipeline.

Existing results need no refitting. The selected outputs are in `logs/era5-features/soaring/`: `group_scores.csv`, `era_scores.csv`, `species_scores.csv`, `season_scores.csv`, `paired_scores.csv`, `paired_season_scores.csv`, `runtime.csv`, `diagnostics.csv`, `cv_checks.csv`, and `fits/`. Input hashes and feature audits are under `logs/era5-features/`. Generated data and fits remain ignored by Git and must be preserved locally for reproduction.

To recompute the selected candidate deliberately, using the existing frozen designs and weather snapshot:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_era5_features.py --variants soaring > logs/era5-features/selected-run.log 2>&1
uv run python scripts/research/review_era5_features.py --variants soaring > logs/era5-features/selected-review.log 2>&1
```

These commands refit or regenerate outputs; they were not run during consolidation. Feature preparation and source conventions remain in [ERA5_FEATURES.md](ERA5_FEATURES.md). They require the local ERA5 cache as data only; no forecast code is imported.

## Archived work

All other research model reports and experimental scripts are historical evidence, not an active queue. Scripts stay in place to preserve existing reproduction commands and imports; no fitted evidence has been deleted. Earlier proposals to run additional station, smoothing or daily-state tests are superseded by the consolidated decision.

| Record                                                | Purpose                                                         |
| ----------------------------------------------------- | --------------------------------------------------------------- |
| [Experiment history](archive/EXPERIMENT_HISTORY.md)   | Previous research README and chronological results              |
| [Model experiments](archive/MODEL_EXPERIMENTS.md)     | Previous specification, including abandoned hurdle/Gamma models |
| [Development history](archive/DEVELOPMENT_HISTORY.md) | Full previous five-step plan and progression                    |
| [Historical diagnosis](HISTORY_DIAGNOSIS.md)          | Why recent gains did not imply better historical reconstruction |
| [Daily-state closure](PASSAGE_SELECTION_WRAPUP.md)    | Why daily passage states were rejected despite local gains      |
| [ERA5 comparison](ERA5_FEATURES.md)                   | Rain-history and radiation/cloud protocols and full results     |
| [Direct lift comparison](ERA5_LIFT.md)                | Boundary-layer height and heat-flux test, not selected          |

## Bounded follow-up

[Original model plus rain](ORIGINAL_RAIN.md): user-requested direct addition tested after consolidation. Wet-day error improves, but dry-day and reconstructed-season error worsen against matched original controls. Not adopted; no further variants queued. The report also records a fold-profile issue in the earlier recent original benchmark and the fresh controls used here.
