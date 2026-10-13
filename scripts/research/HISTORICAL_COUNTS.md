# Actual historical interval assessment

The next experiment uses released 1993–2021 counts and complete non-weather-stop effort, plus accepted recent mixed-interval observations to inform shared time/weather effects. It fits the same working mean specification: one shared seasonal spline, six UTC clock harmonics, current-rain slope/hinge, wind u/v, civil-night status and a separate offset per observed year. Extending year contrasts to the additional observed years changes the coefficient count, not the predictor specification. Every year contrast receives the existing unit ridge; recent four-year fitting remains unchanged. This is not a new year-trend term or an episode addition.

## Recording scope gate

`historical_core_scope.tsv` lists candidate core species. Recording starts come directly from the released taxonomy's `systematic_count_start_year`, whose documented interpretation permits absent entries to be zero within complete observed surveys from that year. The additional owner-requested panel rule requires a positive main-direction record in every year from the adopted start through 2025; annual presence is a selection criterion, not independent evidence of systematic recording. All ten core species have adopted starts of 1993 and satisfy this rule for every year 1993–2025. Fit historical observations only from 1993–2021; retain accepted recent observations for shared effects. Missing days and weather-stop intervals remain unknown.

The generated `taxonomy_annual_coverage.csv` audits all taxa with adopted starts, including missing years. `core_species_scope.csv` records the selected panel and evidence. The broader table assigns 1993 to 33 taxa, 1994 to Stock Dove, and 2008 to 103 remaining passerine concepts; blank start dates supply no systematic scope. Rook's documented 1996 exception remains outside this core panel.

## Exact support and exclusions

Keep each released species-survey count intact and integrate its mean over the survey's actual covered hours. Several surveys on a date remain separate observations; no count is distributed over hourly weather rows. Complete weather stops remain unknown and are excluded. Incomplete surveys are excluded. Actual effort gaps remain absent; inferred historical empty intervals retain the release's documented continuity assumption.

An entry with presence-only count, explicit outside-survey status, a point outside its linked interval, or an observation-support range beyond that interval makes its species-date unsupported for this experiment. Exclude that entire species-date because a broad count might span another session; preserve the original records in the support audit. Exclusions must not become zero counts. This conservative choice is a fitting eligibility rule, not an edit to the released dataset.

## Frozen holdouts

Within the existing site comparison window, use count-independent one-, three- and seven-day blocks: `(nonleap_doy - 3 + 4 * (year - 1993)) % 21` phases 0, 5–7 and 12–18 respectively. Hide every eligible historical survey on a selected date; keep recent observations in training. Every fitted historical year retains some counts. An additional native short-gap fold hides three adjacent whole historical observation intervals only in connected runs with at least six observations of at most 1.5 hours each. Coarse full-day totals cannot supply partial-day truth and are never subdivided. This short-gap fold therefore represents the later surviving fine-scale records, not every historical year.

Rebuild seasonal basis, weather scaling and smoothing using outer retained observations. Compare with the original architecture fitted to identical retained counts and exact coverage; its diurnal profile comes from eligible recent hourly observations only, avoiding hidden historical hourly allocations. Historical season scores reconstruct sums over known eligible observed windows, not true totals on never-counted dates. Score daily missing-count MAE and species-year absolute/signed relative total error separately by era, year, coverage and rain; bootstrap historical years jointly across species. No new retained adjustment or uncalibrated historical prediction intervals are introduced.

If actual historical fitting fails scientific or numerical checks, retain the failure and reassess the specification before adding corrections. Do not apply the simpler model to unsupported years or claim pre-1993 reconstruction from this experiment.

## Reproduce

```sh
uv run --with 'pyarrow<20' python scripts/research/prepare_historical_counts.py
uv run python scripts/research/prepare_mixed_intervals.py
uv run python scripts/research/prepare_historical_holdouts.py
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 Rscript scripts/research/prepare_historical_transfer.R logs/historical-counts/input logs/historical-counts/design
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/run_historical_counts.py
```

Generated observations, components, support exclusions, taxonomy start/annual-record audits, species/year inventory and source hashes are in `logs/historical-counts/`. The holdout-preparation script requires eligible historical scope and cannot fit unknown absences as zeros. No production changes.

## Input audit

The assembled panel has 116,130 species-surveys and 297,760 hourly exposure components; 115,680 species-surveys are eligible. The 65 entries with unsupported timing affect 49 species-dates; excluding their entire dates removes 8,233 recorded birds from fitting and validation, so conclusions apply to the supported subset. Historical survey intervals do not overlap. Short-gap truth is available for 2014–2021; whole-day holdouts cover all 29 historical years.

## Completed comparison

All 40 contexts completed: ten core species × one-, three-, seven-day and native short-gap masks. Maximum gradient was 0.0000163 and directional derivative discrepancy 0.0000000316, both below 0.001. Median weather-model fitting time was 1.76 seconds including training-only smoothing selection; the two parallel comparison shards each took about 122 seconds, including original-model refits. All 104 repository tests and formatting checks passed. The recent four-year regression case retained exactly the same coefficients and selected smoothing after extending year-contrast support.

For the combined one-, three- and seven-day masks, daily missing-count MAE averaged equally across the ten species is:

| Observed held-out weather | Original episode model | Weather mean model | Change |
| ------------------------- | ---------------------: | -----------------: | -----: |
| Dry                       |                  29.92 |              31.89 |  +6.6% |
| Wet                       |                  25.39 |              21.70 | −14.5% |

Wet means exposure-weighted rain of at least 0.1 mm/hour over the held-out observation intervals. There are 14,067 dry and 3,428 wet species-date tasks across the disjoint whole-day masks. The median species error ratio is 1.097 on dry tasks and 0.927 on wet tasks: only one of ten species improves on dry days, while eight improve on wet days. This is a core-species tradeoff, with no pigeons or passerines in the panel.

Mean absolute reconstructed-total error across species-years is 2.87% → 3.03% for one-day masks, 7.34% → 8.23% for three-day masks and 13.27% → 15.83% for seven-day masks. These denominators are recorded totals over eligible historical observation windows, not true unobserved full-season migration. Signed bias can improve while absolute reconstruction error worsens; acceptance uses the latter.

The earliest era matters most: for 1993–2007, three-day total error rises from 8.15% to 9.39%, and seven-day error from 13.66% to 16.60%. The paired year-bootstrap difference is +1.24 percentage points [0.07, 2.54] for three-day gaps and +2.94 [1.00, 4.87] for seven-day gaps. Resampling historical years jointly across species preserves their common conditions; these remain exploratory comparisons on reused model-development masks.

Native short-gap performance also favors the original. For 2014–2016, equal-species daily MAE is 11.75 → 13.81; for 2017–2021 it is 11.52 → 12.56. Reconstructed-total error is 5.04% → 6.78% and 5.81% → 6.27%, respectively. Years with no native short-gap truth are excluded from scoring, rather than counted as zero-error successes.

Full species/year/era/rain and retained-coverage tables are generated in `logs/historical-counts/`; `failures.csv` is empty. No unsupported or never-counted interval supplies validation truth. The wet-day improvement therefore supports behavior on observed rainy intervals, not a directly measured error on historical weather closures. Coarse daily observations also cannot identify the hourly course of migration within their intervals.

## Decision and next design

Do not promote the frozen weather-only model as a general replacement. It is fast and numerically reliable, but actual historical data expose broadly distributed dry-gap losses and worse early-year totals. The shared seasonal spline and year offset already represent expected abundance; residual within-year variation is a possible limitation, not absence of an abundance model. The original architecture also conditions short fills on retained observations, unlike this unconditional mean comparison, so short-gap differences cannot be attributed solely to its episode smooth.

The earlier seven-coefficient-per-year episode addition already worsened recent core-species accuracy; repeating it or selecting species-specific adjustments from these scores is not the next step. Pause further model fitting and specify a weather extension of the original successful abundance backbone: put hourly weather into the expected count integrated over exact observed intervals, preserve complete observed zeros, and represent local temporal abundance within the model. Weather suppression must affect full-day totals rather than being normalized away by a within-day profile. Keep the original's efficient retained-observation conditioning if it can be made consistent with this interval expectation. The precise likelihood, complexity and uncertainty implications require an explicit design before implementation; none of that redesign is implemented here.

The next candidate must preserve ordinary dry-gap and early-era reconstruction accuracy while improving wet gaps, using this frozen core panel and identical holdouts. Do not add correction functions, optimizer ladders or a universal retained-ratio update to rescue the present candidate. Production remains unchanged.

## Follow-up diagnosis supersedes immediate redesign recommendation

The controlled investigation in [HISTORY_DIAGNOSIS.md](HISTORY_DIAGNOSIS.md) shows that adding history does not erase recent predictive gains and removing weather worsens historical performance. Current recent mixed-input comparisons retain 10.4% overall and 35.0% wet gains. Original-model component ablations identify within-year episodes as part of the early historical dry-gap advantage, while its long-term passage-timing shift has little effect on that seven-day task. Retain the promising simple weather candidate and use a bounded historical temporal-variation comparison before any wholesale redesign. The historical dry-gap and reconstructed-total limitations reported above still stand.
