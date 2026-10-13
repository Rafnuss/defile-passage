# Bounded historical episode screen

## Prespecified protocol

The controlled diagnosis supports checking within-year variation on actual historical inputs. It does not invalidate the positive recent weather results. The previous recent-only seven-coefficient-per-year episode candidate worsened core-species MAE by 4.1% and remains rejected.

Test exactly one smaller candidate: add four centered cubic regression-spline coefficients per year (mgcv `k = 5`) to the frozen weather mean design. The episode basis uses retained inputs only, is centered across the retained seasonal range, and receives normalized roughness/null-space penalties plus an identity amplitude penalty, all multiplied by fixed strength 100. This value is prespecified rather than selected on the outer validation masks. Each species is fitted separately under this same rule; no species-specific candidate switches or corrections are introduced.

Keep season/time/weather specification, intact interval counts, exact sums of hourly expected counts, power-1.5 working criterion, annual ridge and training-only base smoothing selection unchanged. Replay every base fit and require coefficient agreement within 1e-7. No retained-count multiplier or daily latent integration is added. There are 51 base coefficients and 132 added episode coefficients over 1993–2025, compared with the original benchmark's 25 episode basis columns per year. Four coefficients can represent broad within-season episodes; this is not a claim to capture independent daily shocks or fine-scale hourly effects.

First screen: ten core species on the existing historical seven-day masks (fold 2), plus all three current recent whole-day masks with eligible historical training added. Historical targets and counts are unchanged. Recent targets match the accepted current mixed inputs and masks; history is training only. Fit a fresh weather baseline for these recent contexts so its comparison with the episode candidate has identical training. Original historical benchmark predictions are reused only for context; this screen compares candidates under identical weather-model fitting rules.

Acceptance gates set before fitting: historical dry equal-species MAE must improve by at least 5% relative to the weather baseline; recent dry and wet equal-species MAE may each deteriorate by at most 2%; historical wet MAE may deteriorate by at most 2%. Median final episode fitting time must be at most five seconds and at most five times the matched baseline final-fit time. Report paired uncertainty, species and era differences, and historical reconstructed-season errors; passing point gates warrants broader one-/three-day and short-gap validation, not production adoption. Reject this candidate if a gate fails and do not retune strength on these same outcomes.

All masks are reused exploratory masks. Assessments do not establish accuracy on unobserved storm closures, calibrated predictive intervals, or completely held-out years. Production gap filling remains unchanged.

## Completed results

All forty paired contexts completed. Eighty final fits pass the existing gradient and directional-derivative checks, and all forty base replays reproduce their saved coefficients within 1e-7. The base model has 51 coefficients and the candidate has 183. The following MAEs average daily absolute error within species, then give each of the ten core species equal weight:

| Task                      | Weather baseline | Weather plus episodes | Original benchmark | Change from weather baseline |
| ------------------------- | ---------------: | --------------------: | -----------------: | ---------------------------: |
| Historical seven-day, all |            30.84 |                 30.26 |              30.06 |                        −1.9% |
| Historical seven-day, dry |            33.40 |                 32.76 |              31.52 |                        −1.9% |
| Historical seven-day, wet |            20.77 |                 20.41 |              24.31 |                        −1.8% |
| Recent, all               |            42.54 |                 41.72 |              46.93 |                        −1.9% |
| Recent, dry               |            47.71 |                 46.63 |              47.85 |                        −2.3% |
| Recent, wet               |            29.91 |                 29.75 |              44.68 |                        −0.5% |

The recent weather baseline here trains on 1993–2025; it is not the prior recent-only baseline of 42.05 overall. Both weather candidates have exactly the same retained training and held-out observations. The displayed recent original refit trains on recent data only and is context for the earlier positive results, not a matched historical-training architecture control. The historical original benchmark has matching retained historical/recent inputs, under its original coverage and distribution architecture.

Historical dry error improves for all ten species, with median species improvement 1.7%. Buzzard contributes roughly half the macro absolute gain, but every other species also improves. Historical wet error improves for eight species; Cormorant and Stork worsen slightly. Recent overall and dry errors improve for nine species, with Red Kite worsening; recent wet error improves for seven, with Black Kite, Buzzard and Red Kite worsening by approximately 3–4%. Recent dry macro error improves in 2022, 2023 and 2025, with a small loss in 2024. These differences remain visible in `species_scores.csv`, `era_scores.csv` and `year_scores.csv`.

Paired historical year bootstrap (2,000 resamples shared across species) gives episode-minus-weather dry MAE −0.64 birds, with a 95% interval −1.04 to −0.27; wet −0.37 [−0.55, −0.22]. Recent calendar-week bootstrap gives dry −1.08 [−2.30, +0.04] and wet −0.16 [−1.04, +0.83], so those recent improvements are not established independently of sampling variation. These intervals describe reused exploratory holdouts, not independent model-selection confirmation.

The main unresolved period remains 1993–2007: dry MAE falls 24.45 → 23.86 but the original is 21.52, leaving a 10.9% disadvantage. For 2008–2016 dry error is 34.80 → 34.19 versus original 34.68; for 2017–2021 it is 56.33 → 55.51 versus original 54.32. Mean absolute reconstructed-season relative error falls 15.83% → 15.52%, still above original 13.27%. These season comparisons use only eligible recorded interval totals and years with held-out truth, not unknown complete-season totals.

Median final fitting takes 0.156 seconds for weather and 1.365 seconds for episodes; the median paired ratio is 8.76. The episode maximum is 1.905 seconds. Timings exclude input reading, base smoothing selection and derivative checks, and use two independent fitting processes with dense linear algebra restricted to one thread each. This is still a short absolute fit, but the added complexity costs substantially more than the base. The fixed candidate passes the recent dry/wet, historical wet and absolute five-second gates, but fails the prespecified 5% historical dry improvement and five-times relative runtime gates.

## Decision and next proposed comparison

Keep the weather model as the primary candidate. Preserve this episode screen as a modest positive diagnostic, but do not adopt or expand this particular implementation. It improves historical predictions consistently and preserves recent group gains; that supports remaining temporal variation beyond the fitted weather, shared season and year offset. It does not close the historical dry or season-total gap, and it does not prove that the missing variation is intrinsically unexplainable by weather. Rejecting this implementation does not reject the idea of episode effects generally.

Do not retune its strength, introduce species switches, or rerun a larger per-year episode search on these same outcomes. The next proposed cheap diagnostic is shared seasonal flexibility: compare the current small common seasonal basis with a richer common basis while keeping time, weather, offsets, interval aggregation and fitting criterion fixed. The original has a richer shared season, an unisolated difference identified in the diagnosis. This adds shared coefficients rather than many coefficients per year, and tests another possible source of early-history error; it is not yet implemented and cannot be called the explanation without a controlled comparison. Preserve recent and wet accuracy gates, and require improvement relative to the original on the historical target before recommending replacement. Predictive uncertainty and historical short-gap conditioning remain open separately.

That proposed shared-season comparison is now completed in [HISTORY_SEASON.md](HISTORY_SEASON.md). It does not resolve the historical dry or season-total gap and is rejected. Keep both extensions as diagnostics, retain the small weather specification, and assess the fitting criterion and mixed-interval weighting before proposing further smooth terms.

## Reproduce

```sh
uv run python scripts/research/prepare_history_episode.py > logs/history-episode/prepare.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_history_episode.py --shard 0 2 > logs/history-episode/run-0.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_history_episode.py --shard 1 2 > logs/history-episode/run-1.log 2>&1
uv run python scripts/research/review_history_episode.py > logs/history-episode/review.log 2>&1
```
