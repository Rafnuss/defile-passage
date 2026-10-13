# Daily-passage selection audit and research wrap-up

## Audit protocol fixed before calculation

Use only the saved power-1 inner out-of-fold predictions for all forty core contexts and SD 0/0.25/0.5/1. All 480 inner fits passed numerical checks, including the context with a failed outer no-state fit. No refits, new outer predictions or changes to model selection are permitted in this audit. The outer accuracy tables from the completed experiments remain the final predictive evidence.

For each context, replay the existing daily-MAE score. Summarize signed total bias, mean absolute yearly relative total error (giving each recorded year equal weight), and sum of absolute calendar-week total errors divided by the overall observed count. Calendar weeks use the same Monday-based integer blocks as inner fitting. All totals concern actual retained recorded intervals, not complete true seasons. The yearly score combines predictions from three different inner models and is a diagnostic of accumulated errors, not a whole-season holdout or a coherent seasonal prediction.

Compare SD chosen by daily MAE with the grid minima for yearly and weekly totals, with increasing-SD tie breaking. Report how often daily selection improves daily MAE but worsens yearly totals relative to SD zero, how often the minima disagree, and how much the alternative minima sacrifice daily accuracy. These alternative minima are selected and scored on the same inner validation predictions: apparent improvements are optimistic diagnostics, not independently validated selection rules. Do not use outer hidden counts to choose among them or combine outer predictions from settings not fitted there.

Both historical-task and recent-task contexts train on 1993–2025. Their main scores therefore cover all retained training years and are overlapping diagnostics, not independent era samples. Also report the fixed choices on historical-target years 1993–2021 and recent-target years 2022–2025 separately, without reselecting settings in those subsets.

Pool fold-context diagnostic scores within each task/species, then average species equally. Separate all forty training contexts from the 39 completed outer pairs. Save species/year/context breakdowns under `logs/passage-selection-audit/`. Wrap up the new daily-passage idea using both this audit and the existing fixed comparisons; no further fitting batch follows automatically.

## Completed audit

All 160 saved setting/context tables are audited and reproduce the original amplitude scores. The daily-MAE rule matches every saved selected endpoint. No optimization, outer rescoring under alternative settings or new fills are performed.

The daily-MAE minimum selects positive SD in 38 of 40 contexts: nine of ten historical-task contexts and 29 of thirty recent-task contexts. In every one of those 38, yearly recorded-total error is worse than the no-state setting. The yearly-total minimum selects SD zero in all forty contexts. All 120 positive-SD settings have worse yearly error than their paired zero-state reference; the smallest loss is 3.18 percentage points of yearly relative error. This is not a floating-point tie or a single-species effect. The recent task contains three overlapping outer contexts per species; forty contexts are not forty independent samples.

| All retained-training years | Selection/setting    | Daily MAE | Yearly recorded-total absolute relative error | Signed recorded-total bias |
| --------------------------- | -------------------- | --------: | --------------------------------------------: | -------------------------: |
| Historical-task contexts    | No daily state       |     31.66 |                                         6.61% |                     −0.37% |
| Historical-task contexts    | Daily-MAE minimum    |     29.77 |                                        20.33% |                    −18.78% |
| Historical-task contexts    | Weekly-total minimum |     29.85 |                                        18.71% |                    −15.42% |
| Recent-task contexts        | No daily state       |     30.88 |                                         3.90% |                     −0.15% |
| Recent-task contexts        | Daily-MAE minimum    |     28.99 |                                        19.17% |                    −18.10% |
| Recent-task contexts        | Weekly-total minimum |     29.41 |                                        12.27% |                     −9.95% |

These are training-fold diagnostic errors over actual recorded intervals, with daily observations held out by calendar week. They are not the outer reconstructed-season errors reported in the model comparisons. Both tasks' selection scores use 1993–2025 training observations. The low no-state accumulated bias is measured on out-of-fold predictions, not asserted from the in-sample count-balance equation.

Keeping the same choices but scoring only the corresponding target eras preserves the conflict. In historical years 1993–2021, daily-MAE selection gives daily error 27.12 versus no-state 29.19, but yearly recorded-total error 20.75% versus 7.12%. In recent years 2022–2025, daily error is 41.74 versus 43.69, but yearly recorded-total error 20.93% versus 6.51%. This target-era split uses retained training validation counts only. It neither chooses a new rule in each era nor establishes accuracy for completely unknown historical intervals.

Weekly-total minima disagree with daily-MAE minima in four historical and twenty recent contexts. They retain positive SD in every historical context and twenty-one recent contexts, and improve their selected weekly-total score. Their yearly bias/error remains substantially worse than no-state. Thus aggregating the selection target to a week is not sufficient evidence of a satisfactory seasonal compromise. These same-fold minima are optimistic selection diagnostics; do not promote them as validated alternatives.

## Answers from the daily-passage experiments

**Does residual within-year migration structure matter?** There is useful evidence that it does. The original episode ablation, the modest broad-episode gains and both daily-state screens show local predictive benefits beyond shared season/year/weather effects. In the full ten-species power-1 comparison, early historical dry MAE improves from the weather reference's 24.45 to 20.26 versus original 21.52. That positive result should be retained. It does not establish a unique mechanism or require this particular AR(1) implementation.

**Does the tested daily-state formulation solve historical gap filling?** No. Its best local daily scores coexist with underpredicted hidden totals. The count-balanced version has reconstructed-total error 15.85% versus original 13.27%, worse for every core species, and signed reconstructed-total bias −8.35%. Its historical missing-count bias is −22.98%, a different denominator from the reconstructed-total bias. The full power-1 historical comparison covers all ten core species; the earlier power-1.5 daily comparison was incomplete and must remain separately matched.

**Was this only the loss function or the selector?** No single cause is established. The original power-1.5 working equation allowed retained count deficits; the power-1 control removes them without repairing hidden totals. The new audit confirms that daily-MAE selection conflicts with yearly totals, but every tested positive SD also loses yearly accuracy. Changing to the yearly-total selector would remove the daily component, rather than demonstrate a successful daily model. Joint shared-rate/daily-state estimation and conditional point prediction remain substantive limitations of the tested formulation. The fixed-coefficient Gaussian curvature proxy was not large enough to explain the entire deficit in its current objective scale; a calibrated integrated mean was never implemented or demonstrated to cure it.

**Is the problem that the model is too slow?** The power-1 daily fit is fast: median 0.195 seconds and median selection plus fitting 2.96 seconds. The remaining scientific failure is total reconstruction, with one explicit matching no-state numerical failure. Fast sparse computation does not make the model statistically small: the completed daily fits have median working effective DF about 918, versus roughly fifty without daily states.

**What should we keep?** Keep the hourly expected-rate construction, actual exposure fractions, intact historical survey counts, weather predictors, shared seasonal shape and year offsets. Their hourly means can be summed over arbitrary recorded intervals. Recent and historical wet-gap improvements remain useful, while actual storm-closure truth is unavailable. Mean aggregation is not a validated arbitrary-scale count distribution or seasonal uncertainty model. Keep the original production benchmark and the existing simple weather research reference; neither new daily screen is a universal replacement.

## Close this experimental branch

The daily AR(1) conditional-state idea has received a numerical pilot, two full attempted core screens, a saved-fit curvature/bias diagnosis, a count-balanced control and this training-selection audit. Stop this branch here. Do not add another amplitude/penalty grid, a weekly-total selector trial, post-hoc multipliers or iteration-budget changes. The positive local results and complete saved artifacts remain reproducible, but no new production model is selected.

A future abundance redesign would need to define the expected missing-period total and its relationship to local migration variability explicitly, and make reconstructed totals a primary validation target from the start. That is a new design decision, not another small repair to the tested mode predictor. There is no next fitting experiment scheduled by this wrap-up.

The original five goals remain the project framework: assessment/numerics have substantial reproducible evidence but independent confirmation is outstanding; weather calibration retains wet benefits and species-level bias limitations; historical partial-day retained conditioning remains unresolved; joint multiday/season uncertainty remains unresolved; actual mixed-scale history has been tested but a universal production replacement has not passed. Earlier empirical recent intervals and short-gap adjustments do not transfer automatically to the daily candidates.

## Reproduction and verification

Run `uv run python scripts/research/audit_passage_selection.py` from the exploration repository. It reads only saved inner tables/checks/selected SDs under `logs/count-balanced-passage/` and writes `logs/passage-selection-audit/`. Generated outputs include all 160 setting metrics, forty-context selection conflicts, weekly/yearly errors, species/task summaries and target-era diagnostics. All repository tests and explicit/repository-wide formatting checks must pass; `git diff --check` must remain clean. No source fitter, production fill or dataset is changed by this audit.
