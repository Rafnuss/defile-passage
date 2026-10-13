# Shared seasonal flexibility control

## Prespecified protocol

Test one change to the retained weather mean: a shared thin-plate seasonal smooth with mgcv `k = 20` (19 coefficients) instead of `k = 8` (seven coefficients). This adds twelve coefficients shared across years, producing 63 coefficients over 1993–2025, rather than the rejected episode candidate's 183. It does not add yearly seasonal contrasts, episode effects, retained-count corrections or a latent-state likelihood.

Keep all forty contexts from the episode screen: ten core species on actual historical seven-day gaps and three current recent whole-day masks each, with historical training included. Preserve intact counts, covered hours, weather/time/night columns, annual offsets and their unit penalties exactly. Rebuild only the seasonal basis and its normalized penalty from retained inputs. Use the same power-1.5 working criterion and training-only three-week-fold smoothing grid (0.1, 1, 10) as the baseline; reselect smoothing for the new basis, never on hidden target counts. Replay all baseline coefficients and held-out predictions within 1e-7. This tests seasonal capacity under the existing common smoothing rule, not an isolated basis effect at identical fixed penalty strength.

Acceptance gates set before fitting: historical dry MAE, early-era (1993–2007) dry MAE and reconstructed-season absolute relative error must each be no worse than the original benchmark; historical wet and recent dry/wet MAE must each deteriorate by no more than 2% from the paired weather baseline. Median final fit must take at most five seconds and at most five times baseline. Point gates only authorize broader one-/three-day and short-gap validation, not production replacement. Report species, year, era and jointly blocked bootstrap comparisons. Do not adjust basis size or selection rules after seeing these masks.

The historical original comparison uses matching retained inputs under its own architecture. The recent original refit uses recent training only and is contextual; the two weather candidates share identical historical and recent training. Reconstruction truth covers eligible recorded intervals only. Reused masks remain exploratory, and unobserved storm-closure truth and predictive uncertainty remain untested. Production is unchanged.

## Completed results

All forty paired contexts completed. Eighty final fits pass the existing gradient and directional-derivative thresholds, and all forty baseline fits reproduce coefficients and hidden predictions within 1e-7. All 104 repository tests pass. Shared-season capacity increases from 51 to 63 total coefficients without adding year-specific components.

| Task                      | Weather baseline | Richer shared season | Original benchmark | Change from weather baseline |
| ------------------------- | ---------------: | -------------------: | -----------------: | ---------------------------: |
| Historical seven-day, all |            30.84 |                31.00 |              30.06 |                        +0.5% |
| Historical seven-day, dry |            33.40 |                33.60 |              31.52 |                        +0.6% |
| Historical seven-day, wet |            20.77 |                20.78 |              24.31 |                       +0.04% |
| Recent, all               |            42.54 |                42.82 |              46.93 |                        +0.7% |
| Recent, dry               |            47.71 |                48.07 |              47.85 |                        +0.8% |
| Recent, wet               |            29.91 |                30.01 |              44.68 |                        +0.3% |

Historical dry MAE improves for four of ten species and worsens for six; the median species ratio is 1.006. Recent dry improves for three and worsens for seven; the median ratio is 1.010. Thus this result is not a loss driven by pigeons or a single core species. Species-level outputs are in `species_scores.csv`, with years and eras in separate tables.

For 1993–2007 dry gaps, MAE rises 24.45 → 24.89 versus original 21.52. It also rises 34.80 → 35.04 in 2008–2016, but falls 56.33 → 55.78 in 2017–2021, still above original 54.32. Historical mean absolute reconstructed-season relative error is 15.83% baseline, 15.85% richer season and 13.27% original. It remains an assessment of eligible recorded totals, with no unknown full-season truth or zeros assigned to closures.

Paired bootstrap differences against the weather baseline are +0.20 birds [−0.16, +0.59] historical dry, +0.01 [−0.39, +0.42] historical wet, +0.36 [−0.37, +1.15] recent dry and +0.10 [−0.63, +0.75] recent wet. Historical years and recent calendar weeks are resampled jointly across species, with 2,000 replicates. The small losses against baseline are not statistically resolved. Against the original, historical dry error remains worse by +2.08 [0.82, 3.51], while wet error improves −3.53 [−6.83, −0.24]. These reused development masks do not include exploratory selection uncertainty.

Median final fitting time is 0.159 seconds baseline and 0.270 seconds candidate, with median paired ratio 1.77 and candidate maximum 0.409 seconds. Candidate time including matrix reading, nine training-only inner fits, final fit, numerical checks and output is median 2.90 seconds (maximum 4.53). Dense linear algebra uses one thread per process, with two independent processes. The candidate passes speed and wet/recent point-limit gates but fails all three historical benchmark gates: aggregate dry, early-era dry and season reconstruction.

Training-only selection chooses smoothing 10 for 37 of 40 richer-season contexts, compared with 22 of 40 baseline contexts; remaining choices are 0.1. The same strength multiplies seasonal and clock penalties in both candidates. Consequently this comparison establishes that increasing seasonal capacity under the existing fitting/selection rule does not resolve the gap; it does not isolate season shape at fixed clock smoothing or prove that all seasonal specifications are inadequate.

## Decision and next step

Reject this seasonal extension and keep the original small weather specification. Do not expand validation of this failed candidate, retune basis size on these masks or combine it with the rejected episode extension. The modest positive episode result remains valid, and the earlier recent and historical wet advantages survive; neither experiment produces an acceptable historical dry/season replacement.

Pause further smooth-term additions. The next proposed step is an assessment of the working count criterion and how it weights hourly versus intact long surveys, before specifying another model. The present additive interval mean is valid, but power-1.5 working loss is not a coherent count likelihood and changes effective weight when intervals are aggregated. The earlier recent coarsening control found negligible predictive deterioration, so resolution weighting is a hypothesis to investigate for historical targets, not an established explanation. Also keep the shared season/clock smoothing interaction explicit. A redesign must state which demonstrated limitation it fixes and keep runtime bounded; do not revive the earlier rejected Gamma-Poisson/hurdle integration machinery automatically. No new criterion or redesigned model is implemented in this screen.

## Reproduce

```sh
Rscript scripts/research/prepare_history_season.R > logs/history-season/prepare.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_history_season.py --shard 0 2 > logs/history-season/run-0.log 2>&1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_history_season.py --shard 1 2 > logs/history-season/run-1.log 2>&1
uv run python scripts/research/review_history_season.py > logs/history-season/review.log 2>&1
```

## Completed criterion audit follow-up

The proposed retained-input audit is now complete: [RATE_CRITERION.md](RATE_CRITERION.md). It measures the duration-dependent working weights and the shared smoothing interaction without fitting or scoring another candidate. Next proposed comparison is one duration-weighted control on the existing small mean; it has not yet run.
