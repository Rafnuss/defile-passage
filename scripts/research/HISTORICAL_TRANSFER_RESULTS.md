# Historical coverage transfer: completed experiment

All 640 contexts completed and passed the unchanged numerical thresholds. The frozen 22-coefficient weather mean model remains a research candidate; production is unchanged. This experiment supports its mean aggregation across hourly and intact-survey input and its advantage for weather-dependent missingness in core large birds. It does not establish universal superiority for ordinary partial days, exceptionally sparse years, passerines or actual historical reconstruction.

## Design and truth

See [HISTORICAL_GAP_ASSESSMENT.md](HISTORICAL_GAP_ASSESSMENT.md) for choices frozen before fitting. Sixteen species, four modern target years, five masks and two target-year recording resolutions give 640 contexts. Only the target year is thinned/coarsened; the other three years retain hourly observations. Shared time/weather/season shapes therefore have dense outside-year support. This is a test of sparse-year abundance offsets and input resolution, not a test with every training year coarse or sparse.

The median-effort historical templates are 2007, 2015 and 2021. Their realized retained fractions of eligible modern effort are 52.0%, 67.9% and 75.9%; the 1978 stress template retains 4.9%. The weather mask retains 64.8%, hiding observed wet hours and count-independent dry three-day runs. It is a prespecified weather-selection sensitivity rather than an empirically matched distribution of historical storm closures. Both input-resolution arms keep precisely the same counts and exposure; coarse observations sum connected retained intervals. No observed bird count is split proportionally across hours.

Scoring covers eligible observed modern windows only. Across species and years these supply 88.4–100% of released actually counted effort, before accounting for entirely unobserved daylight. The corresponding core truth total is 255,288 birds across the four modern years. It is identical across masks; it is not a verified full-daylight seasonal total. Each date/species counts once per mask/resolution/method, and all hidden target counts are excluded from fitting, smoothing and retained-update calibration. Remaining modern years provide calibration truth under analogous masks and resolutions.

The original model's diurnal profile is learned only from other years in both arms, so it does not see target-year hourly detail in the coarse arm. The hourly comparison also fixes that outside-year profile: it is a controlled architecture comparison, not the original model using every available target-year timing datum. Its daily count/coverage objective sees identical retained information in both arms. Original point predictions analytically average conditional count/day-state draws while integrating 500 coefficient draws; original predictive intervals were not generated in this batch and their coverage is unavailable.

## Core species-season totals

The primary summary is the mean absolute relative reconstruction error across the ten core species × four target years. Take the absolute error within each species-year before averaging; pooled signed errors cannot hide cancellation. Survey-input results:

| Mask                    | Original | Weather mean | Weather plus retained update |
| ----------------------- | -------- | ------------ | ---------------------------- |
| 2007 attendance         | 12.41%   | 9.69%        | 9.95%                        |
| 2015 attendance         | 8.70%    | 7.20%        | 7.55%                        |
| 2021 attendance         | 5.44%    | 5.19%        | 5.38%                        |
| Weather-driven gaps     | 15.89%   | 8.02%        | 7.70%                        |
| 1978 sparse stress test | 61.38%   | 69.99%       | 68.61%                       |

Hourly-input weather errors are 10.57%, 7.41%, 5.36%, 7.90% and 64.00%, respectively. Survey aggregation does not systematically worsen the three post-1993 attendance cases. Its working variance criterion changes observation weighting when observations are aggregated, so the fitted coefficients need not be identical across resolutions even though predicted means aggregate coherently.

Mean improvements do not imply most species improve. For the three post-1993 survey templates, weather improves mean seasonal error in only four, five and five of ten core species; median within-species error ratios versus original are 1.135, 1.023 and 1.048. Corresponding modern-year-cluster bootstrap differences in absolute relative error are −2.72, −1.49 and −0.25 percentage points, with 95% intervals [−5.87, +0.97], [−4.09, +0.87] and [−1.87, +1.08]. With just four independent modern years and one template per era, ordinary-attendance superiority is not established.

Weather-driven seasonal error improves for nine of ten species with survey inputs, median species ratio 0.516. Its paired difference is −7.87 percentage points [−12.01, −3.99], and the average seasonal error improves in all four target years. This is the clearer core result. Nevertheless, individual weather-mask species-years remain biased: Marsh Harrier 2024 +32.7%, Grey Heron 2024 +31.8%, and Honey Buzzard 2022 −20.5%. No species exception or response-function retuning is introduced.

The 1978 case fails as a reconstruction strategy for both architectures. About 95% of modern effort and most of the season's information are hidden; weather survey-input mean seasonal error reaches 136.6% in target year 2022. This is information/transfer uncertainty despite numerical convergence. It calls for a separate rule about whether full-season reconstruction is scientifically supportable at such coverage, not another optimizer fix or automatic same-day correction.

## Daily gaps and the optional adjustment

Survey-input equal-species daily missing-count MAE:

| Mask                | Original | Weather mean | Weather plus retained update |
| ------------------- | -------- | ------------ | ---------------------------- |
| 2007 attendance     | 17.35    | 18.61        | 16.67                        |
| 2015 attendance     | 11.25    | 12.70        | 11.29                        |
| 2021 attendance     | 11.22    | 11.28        | 11.12                        |
| Weather-driven gaps | 32.09    | 22.26        | 21.66                        |

The unconditional weather model does not beat the original daily error for ordinary attendance gaps, even where average seasonal reconstruction error improves. For example, dry daily error under 2015 attendance is 14.54 versus original 12.82; the retained update brings it to 12.90. Daily and seasonal objectives must remain separately visible.

The unchanged adjustment often lowers daily error but slightly worsens mean seasonal error under all three post-1993 survey templates. It does not rescue pre-1993 sparse reconstruction. Its additional benefit in the weather mask is small. Keep the general weather mean as the primary specification; retain the same-day update as a separately scored optional research arm rather than a required correction layer. A day with no retained observation always receives the unconditional prediction.

The empirical daily intervals were recalibrated using other-year masked calibration observations, with the same coarse/hour resolution in calibration dates. Core weather-mean 95% coverage is 95.7%, 95.7%, 95.9% and 95.4% for the three post-1993 survey templates and weather mask; the sparse stress test reaches 93.2%. These are approximate cross-validation residual intervals with outer training bases/scaling/smoothing reused, not strict conformal guarantees or joint seasonal uncertainty. Original interval coverage is unavailable, not zero. Good marginal daily coverage does not repair inaccurate reconstructed seasonal totals.

## Secondary groups and year coverage

Species-specific and year-specific outputs remain in `logs/historical-transfer/`. Passerine survey-input mean seasonal error is 32.9% versus original 18.5% for 2007 attendance, and 30.4% versus 23.5% under the weather mask. Pigeons improve markedly under the weather mask (7.0% versus 31.8%) but worsen under 2015/2021 attendance. These groups do not determine the core model decision; the weather model is not a universal species-group replacement.

The target year retains observations sufficient to estimate an abundance offset; completely unobserved years were not tested. Each scenario/year is refitted independently. The next actual-historical experiment must preserve verified recording scope and assess year-level information rather than treating all absent species entries as zeros. Historical passerine scope remains unresolved outside complete 2022–2025 surveys.

## Historical weather and numerical verification

The existing Defile ERA5 cache contains consecutive hourly timestamps from 1965-01-01 through 2026-07-30 23:00, with no duplicated/missing timestamps, no missing values in the five cached predictors, and no negative precipitation values. See `weather_cache_inventory.csv`, `weather_cache_years.csv` and `weather-audit.log`. It requires assembly and the existing UTC accumulation alignment, but new historical retrieval is unnecessary for the tested years. This is a cache integrity audit, not independent verification of historical rainfall accuracy or local visibility.

All 640 outer fits pass: median fit time including smoothing selection 0.174 seconds, maximum 0.442 seconds; maximum gradient 0.0000667 and derivative error 0.0000000201. All 1,920 calibration fits pass gradient checks, maximum 0.0000845. The complete assessment context, including process launch, calibration and benchmark work, takes a median 1.29 seconds. All 320 paired mask checks pass. The repository suite has 104 passing tests; pre-commit checks pass. No thresholds were relaxed and no model terms were added.

## Next scientific step

Keep the simple weather model frozen. The appropriate next data test is a matched historical mixed-interval fit/holdout on verified core-species survey scope, using the already cached historical weather, with actual historical year effort and intact daily totals. It should evaluate seasonal reconstruction and daily error separately, and state which years do not support a seasonal claim. Broader attendance-template sampling can check sensitivity before interpreting a median template as representative of an era. Neither step requires further adjustment-function selection. Do not promote the current candidate universally or reconstruct pre-1993 seasons as established totals from this result.

## Reproduce

Run from the Explore repository; generated outputs stay in `logs/`:

```sh
uv run python scripts/research/audit_gap_target.py
uv run python scripts/research/prepare_historical_transfer.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 Rscript scripts/research/prepare_historical_transfer.R
uv run python scripts/research/check_historical_transfer.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_historical_transfer.py
uv run python scripts/research/review_historical_transfer.py
uv run python scripts/research/plot_historical_transfer.py
uv run --with 'pyarrow<20' python scripts/research/audit_historical_weather.py
```

For independent worker processes, use `--shard INDEX 4` for indices 0–3; species are assigned to one worker so the two resolution arms share a benchmark without concurrent writes. `--resume` reuses completed assessments and must only be used for an unchanged design/model. Input hashes are recorded in `logs/historical-transfer/sources.json`. Core comparison plots are `core_comparison.png` and `core_comparison.pdf`.
