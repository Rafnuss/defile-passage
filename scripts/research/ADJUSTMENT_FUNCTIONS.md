# Diagnose short-gap bias and compare small adjustment rules

Keep all 22-coefficient GAM fits and exact short-gap targets unchanged. First separate the existing mean-model error from the increment introduced by the retained-count adjustment, by species, year, species-year, position, zero counts and individual events. Retain every core species; dominance by a species is a diagnostic, not grounds for exclusion. Secondary groups remain separate. This protocol is written before evaluating alternative rules.

Let `R` be the GAM's expected count during retained effort, `Y` the actual retained count, and `M` the expected missing count. The existing factor `(Y+s)/(R+s)` equals `1 + w*(Y/R-1)` with `w=R/(R+s)`. Thus fixed `s` already increases the weight on retained evidence when the expected retained count increases; `s` is the expected retained count giving half weight. It is not a physical bird count or an estimated Gamma prior. Relative expected coverage `c=R/(R+M)` describes the retained share of expected passage over the observed-plus-gap target window; it is not verified coverage of an entire unobserved daylight day. Changing missing duration alone need not alter how informative a fixed retained observation is about a shared activity factor. Coverage weighting is therefore a hypothesis to test, not an automatic requirement. Flocking and within-day changes weaken the simple expected-count information approximation.

Compare four predefined one-parameter rules, each including no adjustment:

- Existing count shrinkage: factor `(Y+s)/(R+s)`; `s` in 1, 10, 100, 1000, infinity.
- Constant blend: factor `1+a*(Y/R-1)`; `a` in 0, 0.25, 0.5, 0.75, 1. This is a direct, interpretable weight on the retained observed/expected ratio, without a pseudo-count. Full weight can predict zero after retained-zero counts and can magnify small-denominator ratios; report those outcomes rather than silently clipping them.
- Expected-coverage blend: factor `1+a*c*(Y/R-1)`; the same `a` grid. It explicitly tests whether relative coverage should reduce the adjustment. At fixed retained evidence, the weight decreases if more expected passage is missing, which is not automatically a justified model of information.
- Bounded response: factor `exp(b*(Y-R)/(Y+R))`; `b` in 0, 0.25, 0.5, 1, 2. The factor lies between `exp(-b)` and `exp(b)` and equals one when observations match expectation. It tests a bounded response to an unusual retained count, rather than deleting large observed counts or clipping GAM predictions. This is an empirical functional form, not a likelihood-derived posterior.

For every function, select its parameter separately using the same operational training-only out-of-fold calibration rows, once with MAE and once with MSE. This separates the effect of the functional form from the prediction target: MAE favors a conditional median, whereas squared error targets a conditional mean. MSE can be highly influenced by large events. Do not assume it fixes bias. All species use the same rule and grids; no outer missing counts choose parameters. Keep original production, unadjusted weather and the previously selected adjustment as references. These alternatives reuse internal evaluation data and will not yield independent confirmation or justify another round of tuned exceptions.

Report species-balanced MAE/RMSE and median species ratios, aggregate bias, species/year errors, zero-case behavior and paired week-bootstrap differences. Use the existing same-target original benchmark. Do not introduce new model terms, refit the GAM, or automatically replace the retained adjustment. Alternative interval calibration is outside this bounded point-prediction comparison; existing intervals must not be reused for changed point rules.

Run `OPENBLAS_NUM_THREADS=1 uv run python scripts/research/compare_adjustment_functions.py`. Generated diagnosis, selections and comparisons are saved under `logs/adjustment-functions/`. Production is unchanged.

## Completed diagnosis

The current adjusted core predictions exceed observed missing counts by 1,604 birds. The unadjusted weather fit already exceeds them by 945; the adjustment adds a net 659. These are distinct errors and must not all be attributed to the adjustment.

| Core species           | Current signed excess | Increment from adjustment |
| ---------------------- | --------------------: | ------------------------: |
| Great Cormorant        |                +1,388 |                       +97 |
| Common Buzzard         |                  +394 |                      +360 |
| Red Kite               |                  +284 |                      +414 |
| European Honey Buzzard |                  −526 |                       +47 |

Cormorant accounts for about 87% of net excess, without being the source of most additional adjustment bias. Its 2025 error is +1,072 and its 2024 error +573, partly offset by other years. Buzzard and Red Kite contribute more than the entire net adjustment increment, offset by reductions for other species. Do not exclude Cormorant or interpret signed shares as independent additive variance contributions.

Across years, current net error is −27 in 2022, +139 in 2023, +262 in 2024 and +1,229 in 2025. The adjustment adds about 843 and 836 birds in 2023/2024 but removes 486 and 534 in 2022/2025. Thus the largest remaining annual error is in a year where the adjustment helps.

Early gaps account for +1,966 net birds, while middle and late gaps have net deficits of 195 and 167. The adjustment changes early totals by only +21, compared with +582 late. Within Cormorant's first quarter of civil daylight, 8,944 birds were observed, 10,430 predicted before adjustment and 10,663 after. There are no evaluated Cormorant gap intervals outside civil daylight in this diagnostic. This identifies morning prediction as a baseline calibration issue; it does not by itself establish a wrong time smooth, because date, weather and abundance composition differ between time bins. A focused within-species/year time-profile assessment is needed before changing that component.

The largest overestimate is Cormorant on 2025-09-27: 135 missing birds observed, 243 predicted without adjustment and 715 with it, with 483 birds counted in retained hours. Large misses occur in both directions: Cormorant on 2022-10-03 had 994 birds in the gap and only 320 predicted. Across all current core predictions, positive errors total 13,012 and negative errors −11,408. On zero-count gaps the model predicts 4,556 birds; positive gaps are underpredicted by 2,952. The adjustment reduces zero-gap predictions by 2,022, while increasing positive-gap predictions by 2,681. This is a mixture of daily allocation and baseline calibration errors, not simply a universal upward adjustment after retained zeros.

## Completed function comparison

Parameters were selected exclusively on the operational training calibration rows. Every alternative uses the same unchanged GAM means and 4,035 short-gap targets. Independent checks verify neutral limits, monotonicity, the existing rule's evidence-weight identity, coverage dependence and the bounded response's limits. The existing MAE-selected rule is reproduced exactly. Alternative outputs contain point predictions only; old interval bounds are explicitly removed rather than silently reused.

| Rule, training loss               | Core MAE | Core missing-total bias | Dry bias | Wet bias |
| --------------------------------- | -------: | ----------------------: | -------: | -------: |
| Current count shrinkage, MAE      |     9.75 |                   +5.5% |    +6.1% |    −0.6% |
| Current count shrinkage, MSE      |    10.22 |                   +5.0% |    +5.5% |    +0.9% |
| Constant blend, MAE               |     9.91 |                   +6.0% |    +6.9% |    −2.2% |
| Coverage blend, MAE               |     9.72 |                   +4.4% |    +4.5% |    +3.5% |
| Bounded response, MAE             |     9.38 |                   −1.4% |    −0.4% |   −11.4% |
| Bounded response, MSE             |     9.59 |                   −1.1% |    −0.2% |    −9.9% |
| Original partial-day architecture |     9.97 |                   +1.0% |    +0.3% |    +7.2% |

Constant- and coverage-blend MSE results are also retained in the generated tables; neither resolves the total bias. Changing the old rule's selection loss alone does not solve the issue, so the earlier suggestion that MSE selection could help was a hypothesis, not an established explanation.

The MAE-selected bounded response improves core MAE 3.8% relative to the current adjustment, with eight of ten species improving overall and nine dry. Exploratory paired week-bootstrap differences versus current are −0.37 [−0.70, −0.10] overall, −0.38 [−0.79, −0.06] dry and −0.33 [−0.63, −0.004] wet. However, only four species improve wet and its median wet species MAE ratio is 1.007. Versus original, the overall difference is −0.59 [−1.33, +0.06], again not independent confirmation of superiority. These intervals do not account for choosing a functional form from the assessment.

The bounded response's close aggregate total conceals worse underestimation for Honey Buzzard (737 versus 1,324, −44.3%) and White Stork (1,525 versus 2,002, −23.8%). Cormorant improves to 11,953 against 11,795 (+1.3%), from +11.8% under the current adjustment. Median absolute species-total bias is 10.4% for bounded MAE versus current 8.9%, despite the better pooled total. Bounded MSE gives 7.2% median absolute bias but still underpredicts Honey Buzzard about 44% and wet core totals 9.9%. This demonstrates why pooled total bias alone cannot choose the new rule.

For secondary groups, bounded MAE improves passerine MAE from 25.77 to 21.36, but total bias changes from +10.7% to −10.6%. Pigeon MAE changes from 68.75 to 69.26, with bias improving from −8.3% to −5.7%. Keep these results separate from core decisions. Selected bounded parameters are 1 in 19 contexts and 2 in 29, the upper grid boundary; this bounded experiment does not establish the optimal possible response curve.

## Interpretation and next decision

There is no need to invent a separate `s(coverage)` rule. The existing expected-retained-count weight already varies with the evidence amount. A direct coverage blend is an interpretable alternative but brings only a small improvement and changes wet calibration. Relative coverage alone cannot distinguish a poorly observed low-passage period from a large amount of informative counted passage; time location and within-day correlation also matter.

The bounded response is a useful, simple candidate and can be written as `factor = K^((Y-R)/(Y+R))`, where `K = exp(b)` is the largest possible factor. It responds to the relative discrepancy while limiting extreme rate transfers, without a pseudo-count. This still imposes a functional assumption and does not fix the existing morning/abundance calibration. Keep it as an assessed alternative, not an automatic replacement based on near-zero pooled bias. No production or existing selected adjustment is changed.

The next meaningful analysis is species/year/within-day baseline calibration, especially Cormorant mornings and the missed concentrated Honey Buzzard/Stork passages. Do not add species exceptions, another response curve or post-hoc bias multipliers from these masks. Any later replacement needs per-species total calibration, corresponding interval recalibration and additional validation. Repository tests (104), independent function checks and formatting checks pass. Outputs under `logs/adjustment-functions/` preserve the diagnosis, selected parameters, point predictions, species/year/zero totals and exploratory paired comparisons.

## Temporal aggregation matters for coverage weighting

The retained-only rules estimate a factor from the same `Y` and `R`, independent of the missing amount `M`. Multiplying each missing hour by that common factor gives exactly the same mean as multiplying their summed mean. A coverage-dependent factor changes if it is recomputed after splitting the gap, so its use would require defining coverage once over the entire day's missing window and reusing that same factor for every subinterval. The synthetic checks explicitly identify this difference. This is another reason not to make the correction automatically depend on whichever missing interval happens to be requested: information about activity should come from the observed evidence, while the missing mean scales with the target duration. It does not prove that all coverage effects are irrelevant, but it is a constraint imposed by the user's temporal-scale requirement.
