# Small ERA5 boundary-layer and sensible-heat test

> Completed experiment record. Its results are preserved; earlier next-step proposals below are superseded by the [consolidated model decision](MODEL_SPECIFICATION.md). Further experimentation is paused.

## Protocol fixed before fitting

Following the completed [existing-variable tests](ERA5_FEATURES.md), the user authorized the next small test. Add exactly two species-specific linear effects to the retained 51-coefficient hourly mean: log(1 + boundary-layer height in kilometres) and signed upward surface sensible heat flux divided by 100 W/m². The candidate has 53 coefficients, matching the previous radiation/cloud candidate. It replaces that pair as an alternative experiment rather than stacking all weather blocks. Boundary-layer depth includes stable boundary layers and is a proxy, not a direct thermal ceiling; heat flux describes surface-atmosphere heat transfer rather than measured bird-scale updrafts. No convective-velocity composite, interaction, extra spline, new daily state or transformation search is added.

Retrieve 1993–2025 hourly ERA5 at the nearest 0.25° grid point to 46.117215° N, 5.914877° E from ECMWF’s authenticated ARCO archive, including endpoints needed for interval alignment. Read existing local CDS credentials without copying them into code, metadata or logs. Snapshot raw values, grid coordinates, native variable attributes and SHA-256. Download precipitation and solar radiation only as independent source/alignment controls against the existing Open-Meteo ERA5 cache; do not change the reference predictors. Check the actual returned grid and control agreement before fitting. Source differences must be reported rather than silently interpreted as model effects.

For a slot \[t,t+1), average the instantaneous boundary-layer heights at its endpoints. Sensible heat is an hourly accumulation at t+1 in J/m², divided by 3,600 for W/m² and negated to express upward heat positively under ECMWF’s positive-downward convention. Preserve negative upward heat, representing atmosphere-to-surface transfer. No missing predictor is replaced by zero. Require finite values for every original component and preserve all counts, exposure fractions and masks.

Use the unchanged forty contexts, ten core species, intact-interval mean aggregation, 51 original terms, power-1.5 criterion, coefficient ridge one, three training week folds and smoothing grid 0.1/1/10. Reuse the bounded BFGS solver and independent gradient/directional thresholds of 0.001. Save all inner/final endpoints, raw solver status and out-of-fold predictions. Replay all forty weather references. Review only after the whole batch finishes; no numerical retry, fallback or target-informed tuning.

Use the existing historical dry, early dry and reconstructed-season gates against original, wet/recent protection limits of 2% against the retained weather mean and median final runtime limits of five seconds/five times reference. Also compare with the saved radiation/cloud candidate on exactly matching targets. Report species/year/era, rain bands, dry recovery, fixed-week masked totals, shared year/week bootstrap differences, species-relative scores and Honey Buzzard sensitivity. The historical reconstructed totals refer to recorded eligible intervals, not unknowable full-season truth; sustained storm closures have no count truth. Reused masks are exploratory, and no joint predictive uncertainty or production adoption follows.

## Sources

[ECMWF ARCO product guide](https://confluence.ecmwf.int/spaces/CKB/pages/505390919/ERA5+hourly+Analysis+Ready+Cloud+Optimised+ARCO+data+on+single+levels+from+1940+to+present+Product+User+Guide+PUG) documents both variables, their units, point access and nearest-grid selection. [ERA5 documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=414588701) documents the instantaneous and hourly accumulation conventions. The existing cache remains the source of original rain/wind and radiation/cloud comparison inputs. No code is imported from the forecast repository.

## Reproduce

```sh
uv run --with xarray==2025.12.0 --with zarr==2.18.7 --with fsspec==2026.9.0 --with aiohttp==3.14.5 python scripts/research/prepare_lift_features.py
uv run python scripts/research/check_lift_sources.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_era5_features.py --root logs/era5-lift --variants lift > logs/era5-lift/run.log 2>&1
uv run python scripts/research/review_lift_features.py > logs/era5-lift/comparison-review.log 2>&1
```

The optional species shards work as in the previous screen. All data and results stay in ignored `logs/era5-lift/`; the original experiments are preserved.

## Completed input audit

Authenticated direct ECMWF access succeeds and selects 46.0° N, 6.0° E. All 289,272 hourly slots in 1993–2025 have both new fields. Over July 18–November 18, control correlations with the existing cache are 0.99943 for rain and 0.9999996 for radiation; mean absolute differences are 0.00981 mm/hour and 0.1372 W/m², with maxima 0.09966 mm and 0.5067 W/m². Neither control improves with an additional ±1-hour shift. The caches therefore agree closely in the analysis season, but are not bit-identical; no existing predictor is replaced. Larger isolated winter differences remain in the all-year source audit, outside the migration-season model. Upward heat ranges from approximately −100 to +342 W/m² and boundary-layer height from 10 to 3,548 m. Native sensible-heat metadata uses an upward CF name while ECMWF values use the documented positive-downward convention; the conversion explicitly negates those values. Runtime package versions are recorded with the source metadata.

## Completed model results

All forty contexts finish. All 360 inner fits and eighty final fits, including forty saved-reference replays, pass the unchanged independent numerical checks. Maximum gradient is 0.000166, maximum directional derivative error 3.79e-8 and maximum iteration count 100, below the BFGS cap of 200. There are 163 raw precision-loss flags among 440 fits; these remain saved despite passing independent numerical checks. No retry, fallback or new tuning is used. All 104 repository tests pass.

| Measure                                      | Retained weather | Radiation/cloud | Boundary layer + heat | Original benchmark |
| -------------------------------------------- | ---------------: | --------------: | --------------------: | -----------------: |
| Historical dry MAE                           |            33.40 |           32.96 |                 33.48 |              31.52 |
| Early historical dry MAE                     |            24.45 |           23.89 |                 24.43 |              21.52 |
| Historical wet MAE                           |            20.77 |           19.92 |                 20.06 |              24.31 |
| Recent dry MAE                               |            47.71 |           47.55 |                 47.73 |              47.85 |
| Recent wet MAE                               |            29.91 |           28.85 |                 29.27 |              44.68 |
| Reconstructed-season absolute relative error |           15.83% |          15.75% |                15.78% |             13.27% |

Against the retained weather mean, the lift pair improves historical wet MAE 3.41% and recent wet MAE 2.15%; historical dry worsens 0.25% and recent dry is effectively unchanged (+0.03%). Early dry improves only 0.06%. Reconstructed-season improvement is only −0.049 percentage points with paired year-bootstrap interval [−0.244, +0.141]. It remains +2.51 percentage points worse than the original model [1.11, 3.85]. The candidate passes the wet/recent protection and speed gates and fails all three historical-original gates.

The wet improvements over the retained weather reference have paired differences −0.709 birds [−1.547, −0.136] historically and −0.644 [−1.153, −0.190] recently. Dry differences overlap zero: historical +0.083 [−0.392, +0.627], recent +0.014 [−0.527, +0.546]. Against the previous radiation/cloud candidate, every main point estimate is worse: historical dry +0.519 birds, historical wet +0.146, recent dry +0.177 and recent wet +0.413. All corresponding paired intervals overlap zero, so this comparison does not establish a clear difference between those two candidates. It provides no evidence to promote the additional data source over the earlier pair. The total-error difference versus radiation/cloud is +0.035 percentage points [−0.202, +0.273].

Species findings are mixed. Historical dry MAE improves for five of ten species, recent dry for six. Historical wet improves for eight and recent wet for five. Common Buzzard's wet error improves 13.3% historically and 9.0% recently; Red Kite improves 6.8% and 6.3%. Honey Buzzard receives no major benefit: historical dry is slightly worse, and wet worsens 1.9% historically and 0.4% recently. Excluding Honey Buzzard diagnostically still leaves historical/recent dry worsening of 0.28%/0.05%; the unsuccessful dry result is not driven by that species. Grey Heron dry error improves 3.7% historically and 4.2% recently, while White Stork recent dry worsens 1.8%. Nine of ten core species remain worse than original on reconstructed-season error. Grey Heron is the exception: 21.48% versus original 22.21%, retained weather 22.39% and radiation/cloud 23.06%. Its dry-day and total gains are useful species-specific evidence, without supporting a universal model switch.

Historical dry-after-rain MAE improves from 38.20 to 37.95, but background dry worsens from 31.55 to 31.77. Recent corresponding changes are 52.86 → 52.70 and 46.11 → 46.18. Fixed-week masked-total MAE is essentially unchanged historically (83.84 → 83.86) and improves slightly recently (98.91 → 98.41). Mean-rain 1–3 mm/hour days worsen slightly historically (6.73 → 6.82) and improve slightly recently (18.90 → 18.80); only ten recent species-day observations have covered mean rain ≥3 mm/hour and no historical ones do. No heavy-rain closure claim is justified.

Median final fitting takes 0.155 seconds versus 0.149 for the paired reference; median paired ratio is 1.045. Training selection plus final fitting takes 2.09 seconds. The two new predictors remain computationally cheap, but fail the accuracy objective.

## Decision

Do not adopt the boundary-layer/sensible-heat pair or stack it onto radiation/cloud. Preserve the downloaded data and completed results for reproducibility. Radiation/cloud remains the stronger tested weather extension; rain history retains its modest, species-dependent evidence. The physical motivation is sound, but this simple additive specification does not improve the practical reconstruction target. This does not establish that ERA5 perfectly represents local thermals, or that these variables could never help with a different design; it does not justify searching transformations, interactions or more lift variables on the same development targets.

Keep original production and the retained weather research reference. The next useful input-quality comparison is station-based rainfall, rather than an automatic further model-term search. Historical partial-day conditioning, joint uncertainty and independent confirmation remain open. Results stay under `logs/era5-lift/lift/`, with matched radiation/cloud comparisons under `logs/era5-lift/comparison_*.csv`.
