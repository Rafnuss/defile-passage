# Défilé Explore — decisions log

A running log of settled calls for the Explore statistics: what was tried, what worked, what was
rejected and why. Not a design spec; read the code for that. See `DEVELOPMENT.md` for what is
still open.

## Repository

**Methods move to the Explore documentation site (2026-10-26, requested by the user).** The illustrated methods formerly in defileViz's six modals now belong to `website/` in this repository, as a continuous homepage with a species selector and stable chapter/section anchors. The site uses defileViz's palette and typography, with equations and implementation references for a technical audience. QA remains a full diagnostic viewer under `qa/`, with species comparison alongside it. defileViz's information links preserve the taxon and open the relevant documentation section. This supersedes the 2026-10-09 decision to keep method modals in defileViz. `scripts/build_site.py` assembles the frontend, existing export and Python QA pages into `logs/site/`; publication keeps the `viewer.zip` release asset name and existing export checks. Site-only changes need no model fitting for local preview; publication continues to require a full export matching HEAD and a site built from committed code. Legacy root-level taxon and comparison pages redirect to `qa/`.

**Methods narrative and seasonal windows (2026-10-26, requested by the user).** Keep only a basic description of the standardised input dataset; recording and cleaning conventions belong to defile-dataset. Open with a branching diagram that distinguishes observed totals, reconstructed seasons, smooth long-term passage and the separate classified-bird summaries. Species selection belongs in the first chapter alongside eligibility, comparable years and windows. Illustrate windows with one selectable complete season: standard and analysis periods, actual daily survey hours and raw species counts on one date axis. Windows are chosen across comparable years and stay fixed when the example year changes. Explain the derived results before their reliability checks.

**Methods organised by inference step (2026-10-26, requested by the user).** The guide has seven chapters: data and effort (species, years, days, temporal resolution); daily count model (coverage, count variability, model terms, weather/episodes, smoothing); reconstructing full days; seasonal totals and abundance trend; phenology and its trend; age and sex; and reliability. Fitting the daily expectation and predicting missing passage are distinct explanatory steps of the same production model. Reading-the-results material remains separately in a collapsible appendix for later editorial review; the reproducibility chapter is removed. Reliability keeps a short explanation in the main narrative, linking to species QA and retaining its worked example and display rules in a disclosure. Existing subsection links remain supported.

**Method report editorial simplification (2026-10-26, requested through browser annotations).** Remove the overview diagram, introductory workflow cards and repeated chapter labels; retain a single title per chapter. Explain taxon selection before a centred species selector and restore a synchronised selector in the sidebar. The window illustration aggregates complete comparable seasons by calendar date rather than selecting one season. Use one notation throughout: N_d observed daily count over the union of counting intervals, c_d profile-based coverage, mu_d expected observed count and R_d expected full-day passage. Solar-time details are optional. Merge weather and episode explanations into the model subsection, add weather-response panels from the existing export and describe numerical fitting explicitly. Remove the general code/export disclosures and reference paragraph. No statistical model or export definition changes.

**Pedagogical model and reconstruction examples (2026-10-26, requested by the user).** Explain fitting in four high-level steps with solver details optional. Separate the seasonal-shape example from abundance, with a year slider using normalised exported baseline curves. Show weather in three columns with a wind-direction diagram and explicit hourly transformations. Label weather/episode comparisons by in-sample negative-binomial deviance reduction relative to the baseline, not variance attributed to independent components. Explain full-day reconstruction through unobserved, complete and partial cases, their exported coverage shares, an intensity-conditioning example and selectable daily count bars with 80% interval boxes. These examples derive from the existing export; model fitting and export definitions remain unchanged.

**Explain fitting and within-day prediction explicitly (2026-10-26, requested through browser annotations).** Remove the totals chapter and reading appendix; retain validation only as a short species QA link. Explain that the profile is fitted over calendar date and daylight-relative time, shared across years. Add fixed first/last-year references to the seasonal-shape slider. Describe episode smoothing as its production first-difference spline prior, not the research AR(1) process. Component labels now use cumulative negative-binomial deviance explained relative to a coverage-aware constant-rate null fitted on the same days, with fixed dispersion. Explain data filtering, likelihood, coefficient updates, smoothing and uncertainty in fitting subsections. Describe within-day prediction from the simple missing-share estimate through Gamma–Poisson conditioning and flock draws, retaining intensity units as birds per full-day coverage equivalent. Daily interval lines use exact q10/q90 endpoints on the same date as the mean; selected-day bars compare observations, the exported fitted expectation and reconstructed means. No production-model changes.

**Explain empirical-Bayes fitting through evidence, priors and nested loops (2026-10-26, approved by the user).** The fitting narrative starts with the negative-binomial likelihood and Gaussian priors, expresses coefficient estimation as minimising count misfit plus prior penalties, and explains alternating joint coefficient updates with smoothing and dispersion estimation. Identify this as empirical Bayes with a conditional Gaussian coefficient approximation; retain numerical implementation in optional solver details. Describe episodes with open ecological hypotheses and explain how surrounding observations constrain short gaps in well-covered seasons. Remove the AR(1)/Gaussian-process comparison box. This is an explanatory edit only.

**Narrative accounts belong in Explore (2026-10-09).** The bilingual species and species-year accounts moved from defile-dataset to `content/accounts/`, with their authored TSV inputs, CSV exports, reading copies, editorial coverage and generation instructions. Their scripts live in `scripts/accounts/` and read the unchanged release tables in `data/count/dataset/`, including the original annual and paper text extracts. Published annual totals and the original-name crosswalk are retained as supporting snapshots under `content/accounts/reference/`. Authored content is versioned outside ignored `data/`; exporting it does not change the statistical JSON contract or generate new prose.

**Explore has its own repo, split from defile-migration-forecast (2026-10-09).** It started there
as `src/explore/` (that repo's issue #55) and grew into its own project: per-species statistics,
a QA viewer and method pages, with none of the forecast's dependencies (torch, Lightning, Hydra).
The history of its files came along (`git filter-repo`), so the commits below the split are the
forecast repo's, with paths renamed from `src/explore/` to `src/defile_explore/`.

**Nothing is shared with the forecast, by design.** Two pieces of forecast code are copied here,
each with its origin in its docstring: the release reader (`release`, from `src/data/counts.py`)
and the time-of-day GAM (`timeofday`, from `src/phenology.py`), both at forecast commit 13c5107.
In the forecast repo, Explore's results were meant to cross over only as named files (a profile,
a population trend); that still holds, now across repos. Carrying a change from one copy to the
other is a decision made by hand and logged here, never an import or a shared package.

| Date       | Direction           | What                                | Why       |
| ---------- | ------------------- | ----------------------------------- | --------- |
| 2026-10-09 | forecast -> explore | `release.py`, `timeofday.py` copied | the split |

**Built locally, published as release assets (2026-10-09).** A full build takes 30-40 min on a
GitHub runner (~5.5 on 12 cores), and the cache cannot help in CI: it is keyed on the source code,
so most pushes are cold builds. So CI only runs the tests, and `scripts/publish_explore.py` uploads
the local build (`explore.zip`, `viewer.zip`) to the rolling `dev` pre-release; Pages and
defileViz's deploy download from there. Rejected: the 32 MB export committed in defileViz (275
files rewritten in its history at each build, no check that the copy matches), a `gh-pages`
branch (the same growth), Actions artifacts (expire after 90 days, need a token to download).
Traceability comes from the checks before upload: no export from uncommitted code here or in
defile-dataset, none from a commit not pushed. The dataset is still copied in from a local build
(`--dataset`, a snapshot in `data/count/dataset/`); once defile-dataset has releases, the same
option will take one.

## Explore

**Minimum daily coverage sensitivity (2026-10-28, requested by the user).** Test production's `trend.MIN_COVERAGE` at 0%, 1%, 2.5%, 5%, 10%, 20%, 30% and 50% across ten core species and five development masks: 800 threshold fits with smoothing and dispersion re-estimated, 19,552 realistic-mask and 4,908 short-morning target species-days. Twenty percent gives the lowest seasonal error in both assessments (3.529% realistic, 2.213% short mornings), versus 3.530% and 2.309% at the existing 10%; short-morning daily MAE falls 2.17%. Paired year-bootstrap intervals include zero improvement, and only five of ten species improve short-morning seasonal error. Adopt 20% at the user’s request: use the best cutoff from this calibration without requiring a uniquely established optimum or another lengthy run. Thirty and fifty percent worsen realistic seasonal errors; no floor worsens daily error. Set `trend.MIN_COVERAGE = 0.2`, bump `trend-gam@3`, and update the methods illustrations; existing exports require rebuilding. No further calibration batch is scheduled. Reproducible design, limitations and results: [coverage threshold experiment](scripts/hierarchical/COVERAGE_THRESHOLD.md); generated predictions and paired scores: `logs/hierarchical/coverage-threshold*/`.

**The Explore export is a separate, raw aggregation of the release** (`src/defile_explore/`,
defile-migration-forecast #55), not the model's counts: no count is moved, dropped or imputed, and daily totals reconcile
with `count.csv` and the dataset's own daily totals (`tests/test_explore.py`). Effort is the union
of `complete` survey intervals per local day. `species_doy_statistics.json` stays the model's
contract, unchanged.

**Effort-adjusted values use a time-of-day profile, not birds per hour.** A taxon's profile
p(h | doy) is fitted with the model's own ratio GAM (`defile_explore.timeofday.fit_ratio_surface`, one
implementation) on the day's light from civil dawn to dusk (solar hours, and local clock hours
before, until 2026-10-09, see below), from days timed to the hour; a counted day's coverage `c` is
the share of the profile in the hours counted, the adjusted day is count / c, and the annual index
is Σ birds / Σ c over counted days in the window (a ratio estimator, so low-coverage days do not
dominate). Taxa with fewer than 500 timed birds use a group profile (raptors, pigeons,
passerines, other), then a uniform one. On the 2026-10 release, 66 taxa have their own profile.
`scripts/analyse_explore_effort.py` compares the options for Black Kite, Honey Buzzard, Red Kite,
Common Buzzard, Wood Pigeon and Chaffinch:

- Birds per hour and the uniform (daylight) index are the same curve. Neither is offered.
- The profile matters where the species has a peaked day: before 1993 Common Buzzard is at 0.25
  of its 2010-2025 level per hour and 0.82 with its profile (midday passage, morning counts).
- Profiles from the hourly sheets (2014-2020) and from Trektellen entry times (2021-2026) agree
  (total variation 0.05-0.12; Wood Pigeon 0.22, shaped by a few huge mornings), so Trektellen
  times are usable as passage times. Nothing is timed to the hour before 2014, so stability across
  decades cannot be tested.

**No adjusted value below c = 0.5** (`COVERAGE_MIN`), for a day or for a year's mean: the raw
count and `c` are shown instead. Pre-1993 counts cover a median 0.05-0.11 of a raptor's day, and
the step at 1993 survives the adjustment (Kestrel x14, Honey Buzzard x5; Common Buzzard x2.4 ->
x1.45), so effort is not what separates those years. They stay visible, unadjusted, and out of
reference bands. Taxa not counted systematically in some years (passerines before ~2007) are a
protocol matter no effort metric fixes; the dataset README has that history.

**One correction per species, explained in the order of the build** (2026-10-09). A species' days
are corrected once: by the trend GAM's gap-filled days when it has a trend whose totals are not
hidden, otherwise by count / c; the two never stack. Fitting a simpler model for every species
instead, shown only below an uncertainty threshold, was considered and not done: most of the ~200
taxa without a trend have too few birds for it, and would fall back on the counts anyway. The
README's "How a species file is made" lays the steps out, and defileViz's "How it's made" pages
follow them: the counts, time of day and coverage, the trend model, how reliable, what the page
shows, then age and sex.

**Every counted day also gets the model's value, at any coverage (`trend.days`, 2026-10-09, asked
by the user).** `COVERAGE_MIN` stays for the empirical layer (`count / c`, Σ birds / Σ c, the
season panel, the window envelope), where a ratio with no model behind it needs a floor. On top,
for taxa with a trend, each counted day in the model window gets its gap-filled full-day total
(`trend.filled_days`): the birds counted plus the posterior predictive of the hours not counted,
from the draws that make `trend.annual` (rate given y in c ~ gamma(θ + y, θ/μ + c), so a well-counted
day leans on its count and a poorly counted one on its neighbours, the season and the year;
missed birds in flocks, `kappa`). Exported as the mean and an 80% interval, classed under `totals`
(`trend.days.total`). The mean, not the median: the missed part is skewed, and on the 2026-10
release the medians summed to 0.87 of Σ count / c for Common Wood Pigeon days at c 0.5-0.9 (Siskin
0.86, Red Kite 0.93), the means to 1.00. Over the 74 trend taxa, Σ filled / Σ (count / c) is 0.999
(c 0.9-1), 1.002 (0.5-0.9), 0.995 (0.2-0.5), 0.995 (0.1-0.2), so the model agrees with the ratio
where both exist, and the interval says how far to trust a day: q90/q10 is 1.1, 1.7, 3.9 and 7.2
in those bands (days with at least 20 birds). 41 442 days at c 0.2-0.5 and 7 836 at 0.1-0.2 now
have a value; below `MIN_COVERAGE` (0.1, 156 days) a day is filled as not counted, its birds
added. Not used (yet): the pattern of the hours within a day, which needs passage correlated
from hour to hour (DEVELOPMENT.md). Species files grow from 18 to 24 MB. defileViz draws them in the
year panel under the totals (`PlotYearDays.vue`: birds counted as bars, the filled day as a dot
with its 80% interval, hidden or in amber with `trend.days.total`). Two consequences of the skew,
kept as they are: the season's total stays the median of its draws (`trend.annual.total`), so the
days of a season can add up to a little more than it (the sum of the counted days' means over the
season's median: median 0.99, quartiles 0.93-1.03, on the 74 trend taxa, years with uncounted days
below 1); and on 11% of days, nearly all with no bird counted, the mean lies above q90 (a rare
flock in the hours missed), so the interval is drawn clipped at the mean.

**Explore lives in this repo, contained in `src/defile_explore/`.** It shares the forecast's release
reader and time-of-day GAM, and a population trend fitted for Explore may later help the
forecast (Red Kite's under-prediction of recent years is a missing trend). But the forecast never
imports it (`tests/test_explore.py` enforces the direction); a result crosses over only as a named
file the forecast reads, as `species_doy_statistics.json` does, decided here first. The GAM
profile is variant A of the Explore baseline, provisional until compared with a hierarchical
Gaussian process on a chronological holdout.

**Each taxon has a start year, 1993 or 2007**: its counts are compared from then on, and nothing
is adjusted before it (earlier years stay in the export, raw). Daily systematic counting began in
1993 and always targeted raptors, herons and egrets, storks, pigeons and corvids, and other large
birds counted individually (cranes, geese, ducks), which start in 1993 even if rare then (Peregrine
recovered). Passerines were hardly recorded before 2007, when their taxa double and their birds
rise 15-fold (defile-dataset `docs/sampling-history.md`): any other taxon starts in 1993 only if
recorded in at least 0.75 times as large a share of the 1993-2006 years as of the later ones. A
year counts as recorded only with at least 2% of the taxon's median year since 2007, so that a
trickle noted while the taxon was not counted is not a series ("swallow sp." 2000-2006: ~600 birds
a year against ~150 000 since). The floor stays low because it also penalises a real increase
(Common Crane, ~30 a year before 2007 and 380 since). Full tier: 45 from 1993, 41 from 2007.

**Group taxa are read as everything below them** (`add_rollups`, replacing the hand-listed
`COMBINED` series). defile-dataset gives each taxon a `parent_taxon_id` (`taxonomy/parent_taxa.csv`:
the smallest enclosing "sp." or slash taxon, a subspecies's species; roots have none). A group's
series is its own count plus every taxon below it, at any depth, under its own id (`members` lists
them): "harrier sp." is all harriers, "Columba sp." the Columba pigeons, "swallow sp." all swallows
and martins. It replaces `combined-columba` and `combined-hirundinidae`, which were the same sums.
Why: a group's own count follows how far observers identified ("Columba sp." only from 2014,
"swallow sp." in 1993-1999), so its own series is not the birds. The members' series stay as they
are. Rock Dove and Feral Pigeon have no parent (local birds, never in a pigeon total).
A group is not shown (tier `excluded`, no page, its own series untouched) when it is alone (fewer
than `ROLLUP_MIN_BELOW` = 2 taxa below it: "Asio sp." is Short-eared Owl) or when one taxon is more
than `ROLLUP_MAX_SHARE` = 90% of all the birds counted under it (the group would be that taxon) or when it is too large to say anything (more than
`ROLLUP_MAX_BELOW` = 100 taxa below it: "bird sp." with 270 and "passerine sp." with 104; the next
is "shorebird sp." with 50). A species is always read with its subspecies (Western Yellow Wagtail with the Blue-headed
Wagtail, Redpoll with Lesser Redpoll), whatever their share. Rules, not a list, and not on a family. Occurrence tiers still decide the rest. Groups with their own timed
birds get their own profile, but only taxa without `members` fit a group profile (no double
counting).

**Tiers count days with migrating birds**, not birds: `full` from 50 days over 5 years, `rare`
at 10 days or fewer (84 / 45 / 142). Provisional, to tune once the page exists. French names come
from the eBird taxonomy (fr_FR) by `ebird_code`.

**Trends and annual totals come from a GAM, not a Gaussian process** (`src/defile_explore/trend.py`,
`scripts/benchmark_trend.py`). A day's count is negative binomial around coverage x exp(intercept
\+ trend(year) + season(doy) + shift(year, doy) + year level + episode), where `episode` is each
year's own short-range curve (runs of good or bad migration days, the weather's share); hours not
counted are filled with an hourly over-dispersion `kappa` fitted from the timed days (flocks). The
annual total is the birds counted plus the posterior predictive of the coverage missed. Both
priors were fitted on one engine and benchmarked on Black Kite, Honey Buzzard, Red Kite, Common
Buzzard, Osprey, all pigeons and Chaffinch:

- Gap filling (well-counted years 2014-2025 given an old year's gaps): GAM and GP both 5.0%
  error, the GP better in 49% of paired trials; the ratio index 14.6% (40% too high for pigeons),
  the season alone 5.7%.
- Calibration came from the episode term and `kappa`, not from the prior: without them both 80%
  intervals held the truth 54% of the time, with them 80% (95%: 94%).
- Predicting 2023-2025 from the years before (extrapolation, which Explore never does): GP 35%
  error, GAM 49%, almost all of it Chaffinch, where the P-spline extends its last slope; daily log
  scores equal (-3.170 / -3.171). A trend fed to the forecast would need a flat extrapolation.
- The Hilbert-space GP misbehaved at long lengthscales (prior variance 0.17 instead of 1 at the
  series' ends for a 30-year lengthscale, with the domain at 1.5 x the data), and full Bayes
  (NumPyro NUTS: 3-5 min a fit; PyMC's C backend does not compile here) bought nothing once
  intervals were calibrated. The GAM refits in 0.2 s.

Every smooth sums to zero over its grid, so the intercept, trend, season, `shift` (an interaction
only, as mgcv's `ti`) and the year level each own their part: unconstrained, the smooth trend moved
with the optimiser's stopping point (Black Kite 2025/1993: 0.80 to 1.21). Smoothing parameters
come from the Fellner-Schall update (mgcv's `efs`): the same optimum from any start. `theta` then
alternates with them as the maximum of the Laplace marginal likelihood: its likelihood given the
fitted means was 15-35% too large (days looked less variable than they are). About 3 s a taxon
(median 2.9 s of CPU over the 74 exported trends).

The constraints separate the terms on the log scale only, so `trend` and `shift` are not
abundance and timing on their own, and are never reported separately. `shift` sums to zero over
the window's days with each day weighted equally, near-empty tails included: when the tails fill
up, `trend` rises and `shift` lowers the peak, and in birds the two cancel. Change from the first
season to the last (1993-2025; Chaffinch from 2007):

| Taxon          | Totals (trend + season + shift) | `trend` alone | `trend` with `shift` recentred on passage | Largest gap |
| -------------- | ------------------------------- | ------------- | ----------------------------------------- | ----------- |
| Black Kite     | x0.82                           | x2.95         | x0.83                                     | 6%          |
| Honey Buzzard  | x0.30                           | x1.67         | x0.30                                     | 2%          |
| Red Kite       | x9.6                            | x4.9          | x9.8                                      | 9%          |
| Common Buzzard | x0.79                           | x5.66         | x0.78                                     | 1%          |
| Osprey         | x0.83                           | x1.02         | x0.83                                     | 0%          |
| All pigeons    | x0.94                           | x2.98         | x0.92                                     | 2%          |
| Chaffinch      | x16                             | x9.5          | x16                                       | 2%          |

Abundance is therefore read from the smooth total in birds and timing from the median passage
date, which is what the export and defileViz show. Weighting `shift`'s constraint by the season's
passage, inside the fit, was considered and not done:

- It adds no output: the two quantities it would approximate are already exported exactly.
- It is not exact: a pure shift of δ days on a season of spread σ still moves the weighted `trend`
  by about δ²/2σ² (Red Kite, 12 days later since 1993, has the table's largest gap, 9%).
- It changes what the trend and shift penalties smooth, so the totals would need re-benchmarking.
- Its weights come from the fitted season (circular) or the raw counts (noisy tails).

If a split of abundance and timing is ever needed, for example for the forecast, recentre `shift`
on the passage after the fit (the table's fourth column) rather than refitting.

The benchmark (three refits per taxon, each hiding every target year; 40 s for seven taxa) splits
the error by kind of gap: hours hidden on days still partly counted are 15% of a year's birds and
3% of error, whole days hidden 6% and 2%. So the day's own count and its time-of-day profile matter
most, and the smooth terms least. What was tried on that split (`fe09ac4` has the code):

- `kappa` on blocks of 4 clock hours (`KAPPA_BLOCK`), kept: a day's passage shifts as a whole, so
  neighbouring hours are correlated and `kappa` halves from single hours to 3-4 hour blocks, then
  levels off. It fixed most of the under-coverage (Honey Buzzard 55% -> 70% of 80% intervals).
- Counted hours as flocks too (y negative binomial of size kappa x c in the day's rate update),
  dropped: 3% too low on gap-filled totals and no more accurate.
- Daily ERA5 weather at Défilé (wind, rain, cloud, temperature smooths), dropped for Explore: the
  error on whole days fell from 2.1% to 1.7% of a year but the total's did not (5.4% vs 5.3%), at
  2.5 x the time. It improves daily log scores (Black Kite -2.94 vs -3.02): a forecast matter.
- Finer episodes (`GAM_EPISODE_K` 35 and 50 instead of 25), kept at 25. At 25 knots the
  first-difference penalty sits at its lower bound for six of the seven taxa, so an episode's
  length is set by the knot spacing (fitted correlation halves after ~6 days for every taxon), not
  by the data. The data's own departures from the smooth model are shorter: on well-counted core
  days, with each year's mean removed, their autocorrelation halves from lag 1 to lag 2 and is gone
  by lag 3-4 (raptors, 1993-2025). Fitted on 2014-2025, more knots raise the marginal likelihood a
  little (+2 to +11 at 50 knots) and let the penalty act again, but even 50 knots (one every 2.6
  days) only bring the halving to ~4 days. The gap benchmark at 35 knots matched 25 (5.3% error,
  whole days 2.0% vs 2.1%, intervals 90% / 97%), with recent years slightly worse (0.62 vs 0.54).
  Fewer is worse: at 15 knots (episodes correlated for ~10 days) the error rose to 5.9% (Honey
  Buzzard 8.1%, Chaffinch 9.4%), intervals narrowed to 87% / 96%, and the marginal likelihood fell
  by 12-14, for no gain in time.
  On 1993-2025, now that the episode block is solved per year (below), 50 knots costs 2x the time
  of 25 and still does not help: the marginal likelihood rises by 0-25 per taxon, but the gap
  error is 5.4% vs 5.3% and recent years 0.60 vs 0.55. Variation faster than an episode (a day or
  two of weather) is left to the negative binomial's independent days, which the benchmark says is
  enough for totals.

Result: 5.3% gap-filling error, bias +0.5%, intervals slightly wide (91% / 97% for 80% / 95%),
Honey Buzzard still narrow (70% / 91%). Trends are exported for full-tier species and for group
taxa with members (roll-ups), not for unidentified birds with nothing below them, whose numbers
follow identification effort.

**Fitting speed and convergence (2026-10).** A fit took 15-25 s and the full build ~4 min, and
the Fellner-Schall loop did not always converge:

- H is solved by blocks (`Factor`): the `episode` columns of different years never share a row,
  so the episode corner of H is block diagonal (33 blocks of 24) and the 891-column system reduces
  to the Schur complement on the other 99 columns. The results are unchanged (log marginal within
  0.06, totals within Monte Carlo noise; `tests/test_explore.py` checks the algebra against
  the dense matrix).
- The smoothing-parameter loop hit its 100-iteration cap for Black Kite: a fully penalised trend
  (`lambda` near its upper bound, a straight line) has a vanishing wiggle and room, and its update
  oscillated by +-0.1 forever. A penalty leaving less than 0.01 degrees of freedom now counts as
  converged, and repeated steps in the same direction are lengthened (Red Kite's episode penalty
  crept to its lower bound by 0.11 a step). Neither moves the fixed point.
- Worker processes ran one OpenBLAS thread per core each (load 110 on 12 cores): `worker_pool`
  gives each worker one thread.
- `doy` was `dayofyear`, so every window day of a leap year sat one day later in the season,
  `shift` and `episode` than the same date in other years: now the day of a non-leap year
  (`season_day`).

Together about 10x: a fit ~2-3 s, the benchmark 40 s with loading, the full build ~2.5 min, of
which ~80 s is the time-of-day profiles (`build_profiles`, serial).

Settings tried on the benchmark (GAM alone, seven taxa) beside the episode knots: none moved the
gap error off 5.3-5.4%, the benchmark's noise level, nor fixed Honey Buzzard's coverage. Season
12 or 30 knots, `shift` 4x6 or 8x12, trend 20 knots, a lower `lambda` bound (-10), observed instead
of expected information in the Laplace approximation (+20 log marginal over seven taxa, same
totals), and `MIN_COVERAGE` 0.05 or 0.2 (0.05 widens nothing and loses Osprey's coverage, 0.78)
all landed within +-0.002 of the base error. Dropping the year level or `shift` cost 111 and 56
of log marginal. Honey Buzzard's misses are whole hidden days at the late-August peak, estimated
~30% low; its day-level dispersion is not peakier than the season's (theta 1.2 in the tails, 0.9
at the peak), and with 11 target years an 80% coverage of 0.70 is within one standard error.
Across the 74 exported trends, `trend` is at its upper bound (a straight line on the log scale)
for 27 and `shift_year` (timing constant over the years) for 26: the year levels take the
multi-year waves, which the marginal likelihood prefers.

**Effort from `survey_complete`; weather stops are zero passage (2026-10-09, decided by the user).**
Effort took only `complete` surveys of the old `survey_coverage`, so `partial` days had no `c`
and the trend filled them as days nobody counted, dropping their birds (Honey Buzzard 2025-09-01:
265 counted, filled at 396 with an 80% interval of 17-1022), and days rained out (`none`) were
filled as normal days (about 9 000 Wood Pigeons on 2025-10-23). The dataset now says it directly
(defile-dataset `docs/survey-coverage.md`): `survey_complete` (every bird that passed is in the
counts), `weather_stop` (counting impossible, no bird assumed), absences cut out of surveys. The
effort's coverage slots are the union of complete surveys, weather stops included, so a rained-out
day is counted with zero birds (`c` = 1); `hours` leaves weather stops out (`weather_hours`). A day
with only incomplete surveys is `uncertain`. Briefly, before the dataset changed, `partial` was
read as complete.

## Pipeline

**One function per taxon builds every block, from one fit (2026-10-09).** `pipeline.build_taxon`
takes a taxon's slice of a shared stage (release, effort, daily and hourly counts, profiles, age
and sex rows) and returns its species file: the raw tables, the trend GAM, and the blocks derived
from them (`season`, `daytime`, `age`, `sex`, `records`, `key_numbers`, `diagnostics`). Nothing
refits a model to draw a panel; a prototype that did (six species, every candidate panel) fixed
which blocks exist. The viewer (`scripts/explore_viewer.py`) only draws the export, so what it
shows is what defileViz would get.

**Settings by rule, exceptions by hand with a reason.** About 90 taxa get a full page and 74 a
trend, too many to configure one by one. Every setting has a rule (`settings.py`); a wrong value
is fixed by a better rule where possible, else by an entry in `overrides.yaml`, which refuses an
override without a `reason`. The species file records each value's source. Links follow the
same scheme: eBird, Birds of the World, EBBA2 and Trektellen by rule from the taxonomy's codes;
pages without a code to build them from (Vogelwarte, Migration Atlas) only by hand.

**Caches keyed by content, not by flags.** The shared stage is cached per release (file names,
sizes, times) and per source code of the modules that compute it; each trend fit per hash of the
taxon's data, profile, years and `trend.py`'s source. A code change invalidates exactly what it
touches, without remembering to clear anything. A rebuild after a change to a derived block takes
seconds (four taxa: 5 s instead of ~2 min), so a `--only <block>` option was not needed. A cold
build of all 273 taxa (74 trends) takes ~3 min on 12 cores: 109 s of shared stage, mostly the
time-of-day profiles, then 63 s for the taxa.

**Blocks name their method and version** (`season@1`, `trend-gam@1`, ...): defileViz's method
page will have one section per method, and a version bump says that what a block means changed.

**The season as counted: shares of each year's birds per day, gaps filled only for the total.** A
day's rate is birds per full counted day (`y / c`, not below `COVERAGE_MIN`); its share divides by
the year's total, where uncounted days are linearly interpolated between counted ones. The cells
shown are counted days only, each with its birds counted (`count`) for the hover. Each year's
10/50/90% passage dates come from the same filled series, with the share of the window counted, so
the viewer can fade years with long gaps. The
smooth dates (the GAM's season without the year's level and episodes, `trend.passage_quantiles`)
are drawn over them.

**Time of day: one histogram for the season, the date x hour matrix only where the hour changes**
(`daytime@2`, decided by the user: simpler, and a change shown only when there is one). Bars are
birds per counted hour as shares, pooled over every timed day (days with birds and at least
`PROFILE_MIN_TIMED` of them timed, so hours counted less often weigh less, not zero; an hour
counted under 3 h is left out), beside the smooth profile averaged over the main passage. The
change is the late part's mean passage hour minus the early part's (10-35% and 65-90% of the
passage), with a 95% interval from resampling days within each part, so one large flock cannot
make it look certain. The matrix is shown when the interval excludes zero and the shift is at
least 1 h: 19 of the 86 full-tier taxa, nearly all late taxa passing earlier on the clock
(Chaffinch -1.9 h, Red Kite -1.6 h), plus Great Cormorant, Barn Swallow and Black-headed Gull
passing later. Superseded by solar time (`daytime@3`, next entry). Measured in clock time on purpose: the end of summer time in late October and later
sunrises explain much of it, but a visitor reads a clock. A shift that is clear but under an hour
(Common Buzzard -0.7 h, Sparrowhawk -0.8 h) stays one histogram.

**Every hour of the day is solar time, not clock time (2026-10-09, decided by the user;
`DEFINITIONS_VERSION` 2, `daytime@3`).** Hour 12 starts at the sun's transit over Defile
(`export.solar_shift`: the zone's offset, less the longitude and the equation of time); days stay
local calendar dates. On the clock the transit moves from 13:43 (1 Aug) to 12:20 (3 Nov), with a
1 h step when summer time ends, in late October, at the peak of Wood Pigeon and Chaffinch passage.
The profile GAM, with 4 splines over the season, cannot draw that step. Comparing the mean passage
time of each timed day in four time bases (share of its spread explained by the season, lower is
steadier): Red Kite 0.18 by clock, 0.03 solar, 0.21 hours after sunrise, 0.03 share of daylight;
Common Buzzard 0.21 / 0.03 / 0.23 / 0.04; Sparrowhawk 0.12 / 0.03 / 0.14 / 0.02; Wood Pigeon
0.06 / 0.01 / 0.04 / 0.02; Chaffinch 0.13 / 0.09 / 0.10 / 0.08; only Great Cormorant is steadier
after sunrise. Solar time and the share of daylight tie; solar time keeps hours as units.

- Effort (`hourly`) is split into solar hours from the survey intervals; a count timed to an
  interval (an hour-by-hour sheet) is spread over the solar hours it overlaps, a point time falls
  in its hour, so counts and effort are binned alike. `hours` is the counted duration, night
  included. A survey of up to an hour now times its counts even across a clock hour.
- On the 2026-10 release, against a clock-time build of the same code: the gap benchmark's paired
  median change is -0.003 (mean 0.184 -> 0.170; 27 taxa better, 18 worse; Eurasian Curlew 1.17 ->
  0.75, Greylag Goose 0.57 -> 0.23, Alpine Swift 0.59 -> 0.32; Whimbrel 1.01 -> 1.18). Annual
  indices move 1.5% for the median taxon, up to 15-19% for Common Crane, Skylark, Greylag Goose,
  Blue Tit, Chaffinch. Totals hidden 7 -> 5, trends shown 38 -> 41; Yellow-legged Gull's season
  becomes hidden.
- `daytime` still shows 15 taxa by date, a different 15: the summer-time artefacts go (Wood Pigeon
  -1.5 -> -0.4 h, Merlin, Siskin, Hawfinch, Blue Tit, Greenfinch, Honey Buzzard), and morning
  migrants passing later in solar time as sunrise moves later appear (finch sp. +2.6 h, Redwing
  +1.7, Grey Wagtail +1.6, Hen Harrier +1.1). Best hours move about an hour earlier in their
  numbers (Red Kite 11-16 solar, was 12-17 clock).
- A page wanting the clock adds the day's `solar_shift`: about 1.6 h in summer time, 0.5 h in
  winter time.

**Day by day, the trend GAM fills gaps better than the season panel's interpolation (2026-10-09,
test asked by the user; `scripts/analyse_gap_fill.py`).** The gap transplant of the benchmark
(73 trend taxa with target years, 3 rotations, 1 362 target-year trials, median hidden coverage
0.31), scored on each day with coverage hidden instead of the season. Against `season.py` as built
(birds / c at c >= `COVERAGE_MIN`, linear interpolation between, a day kept below it losing its
count) and against the same interpolation keeping partial counts (`interp_kept`):

- days, median |log| error: GAM 0.131, interp 0.145, interp_kept 0.133; weighted by birds 0.333,
  0.594, 0.363. Whole days hidden 0.673 / 0.869 / 0.869, partly hidden 0.112 / 0.123 / 0.114. GAM
  better in 70 / 73 taxa than interp, 38 / 73 than interp_kept (median day error): on partial days
  the gain over interpolation comes mostly from keeping the count; on whole days and big days it
  is the model's.
- the year's median passage date, mean |error|: GAM 2.7 days, interp 4.4, interp_kept 3.3 (GAM
  closer in 66 / 73 and 53 / 73 taxa); by hidden coverage 0-0.2 / 0.2-0.4 / 0.4-0.6 / 0.6-1: GAM
  1.2 / 2.3 / 4.3 / 3.9, interp 1.9 / 3.6 / 7.5 / 10.2. The 10% and 90% dates alike.
- the year's total, median |log| error: GAM 0.085, interp 0.117, interp_kept 0.098; the gap grows
  with hidden coverage (0.6-1: 0.30 / 0.74 / 0.48).
- intervals: a day's 80% interval holds the truth on 79% of days (74% of wholly hidden days), the
  median date's on 91% of years (93% give or take a day).

So a complete series from the GAM's draws is the better base for the day-scale outputs (season
shares, passage dates, chances), the more so the gappier the year. Switched: next entry.

**A counted day of a year with no bird in the model window has share 0, not null (`season@4`,
2026-10-09).** The year's total is 0, so the share was undefined and the plot drew the year as not
counted (Water Pipit-like rows: 1993, 2001, 2002); a day counted is now drawn as counted, no bird.

**One complete series per taxon: the season block from the trend's gap-filled days (`season@3`,
2026-10-09, decided by the user after the test above).** For a taxon with a trend whose totals are
not hidden (`reliability.fills_season`: 67 of the 74 trend taxa on the 2026-10 release), every day
of the model window takes the mean of the `fill_draws` draws (counted or not; `trend.days` now
holds every window day), and the season block is made of that series: the shares (no blank day in
the model window; defileViz pales the days nobody counted, `count` null), every year's 10/50/90%
passage dates taken in each draw (the median over draws, and `q50_lo`/`q50_hi`, the 80% band of
the median date), and the chances, the probability over the draws that a full day holds at least
N birds, every day of the last ten seasons weighing in (beyond the model window, well-counted days
as before). The season fields rest on the `totals` claim (`season.share`, `season.passage`,
`season.chances` in `reliability.ELEMENTS`); where it is hidden (Northern Lapwing, Eurasian Curlew,
Mediterranean Gull, ...) and for taxa without a trend, the season is from the counts (`source: counts`, `count / c` and interpolation as before), so a hidden claim never hides the phenology
(`COUNTS_FALLBACK`). A year with no bird counted keeps no dates and no shares: they would be the
model's alone (Water Pipit 2007-2023). Against the counts version, on the 67 taxa: the median
dates move by 0.24 days (median; mean 2.8, 90th percentile 6.8), the band is 2.3 days wide
(median; 15 at the 90th percentile), and the old date lies in the new band in 79% of years. The
big moves are flocking, erratic taxa where interpolation threw away a big partial day (Yellow-legged
Gull 2011: 71 birds on 20 July at c 0.47, median date 278 -> 207); on those taxa the gap test
favours the GAM most (Yellow-legged Gull median date error 8.7 days against 27.6). The principle
"empirical first" becomes "the counts are always shown; the numbers come from the one fit" (AGENTS.md).
Species files grow from 24 to 28 MB. The trend's cache key now includes `season.py`, whose code
summarises the draws inside `taxon_trend`.

**The profile stays on solar hours, not day-length units (2026-10-09, held-out test asked by the
user; superseded the same day by the twilight axis, next entry).** `scripts/analyse_time_basis.py` fits each of the 68 own profiles on even years and scores
odd years' timed days, then the reverse, with the GAM on solar hours (as built) or on
tau = (t - civil dawn) / (civil dusk - civil dawn), read back on the same solar slots. Scores: the
L1 distance between each day's observed and expected hourly shares; the same on the first and last
counted hours of days counted from dawn or to dusk; the error of the second half of a day's
birds predicted from the first through coverage. Solar 0.636 / 0.062 / 1.417, tau 0.636 / 0.063 /
1.418; tau better in 48% / 52% / 46% of the 134 taxon-folds. The test can tell profiles apart: a
uniform profile scores 0.704 / 0.070 / 1.882, and solar beats it in 95% / 77% / 83%. The two axes
draw different curves (median total variation 0.04, up to 0.2 for Siskin in August; Red Kite
flatter in tau, as thermals keep clock hours), but the day-to-day spread of flocks hides the
difference. A tie, so solar hours stay: they are hours. Siskin's evening rise is there in tau too,
so it is in the counts, not an artefact of the cut at dusk.

**The profile's time axis runs from civil dawn to civil dusk, on daylight samples only, with 16
splines (2026-10-09, asked by the user after herons, egrets and Red Kite looked wrong).** The GAM is
fitted on tau = (t - civil dawn) / (civil dusk - civil dawn), the sun at -6 deg at both ends, from
the samples whose hour overlaps daylight (each at the midpoint of its daylight part), with
`PROFILE_TAU_SPLINES` = 16 (about 1 h apart). The solar-hour fit took its axis from every sample:
three 24-hour days stretched it to 0.5-22.5 h, so its 12 splines were 2 h apart. Held-out test
(`scripts/analyse_time_basis.py`, 68 taxa, even/odd years): l1 0.6347 vs 0.6356, edge 0.0622 vs
0.0621, fill 1.4133 vs 1.4172, better in 93 / 80 / 86 of 134 taxon-folds (worse 41 / 54 / 48). On
solar hours restricted to daylight the gain vanishes (35 better, 38 worse on edge): it is the
twilight anchor with the finer axis that helps. Small on average, but it moves the ends of the day
where they were wrong: Red Kite's last hour before dusk in October, 2,074 birds expected for 629
counted, now 1,254; Grey Heron's September evening 2,090 expected for 2,610 counted, now 2,319.
Tried and kept as they were: day weights `RATIO_WEIGHT_POWER` 0 and 1 against 0.5 (both worse:
l1 better in 67 and 74 of 133 vs 93); weaker smoothing (lam 10 or 1) on Grey Heron, Great Egret
and Red Kite, within 0.5%. Not done: forcing the rate to 0 at -6 deg. The cut there is the
definition of a full day, not a zero rate; herons pass most in the last hour of light and go on
into the night. Herons and egrets are lumpy: on the first and last counted hour a flat profile
scores better than any fit (an expected flock that does not come costs more than a flat guess),
but the fit predicts the rest of a day far better (fill 1.34 vs 1.47 Grey Heron, 0.98 vs 1.54
Great Egret). Grey Heron's August evening peak is still sharper than the fit (1,410 counted, 946
expected, 1-2 h before dusk), and its mornings come in about 20% lower than predicted. On the
2026-10 release, against the solar-hour build: annual indices move 1.3% for the median full-tier
taxon (90th percentile 4.3%, largest 20%, Common Swift, whose dawn and dusk flights now weigh more,
so its coverage is lower: indices +9% in recent years, held-out scores slightly better); mean yearly
coverage unchanged (median, 5-95% -0.03 to +0.02); gap benchmark mean 0.176 -> 0.165 (39 taxa
better, 26 worse); best hours change in 23 taxa. Redwing scores worse on the new axis (l1 0.675 vs
0.667).

**"Through the day" compares like with like (`daytime@4`, 2026-10-09).** The bars were birds per
counted hour pooled over the whole season, beside the profile on one day: an August evening hour,
counted rarely, made a tall bar after that day's dusk (Great Egret, 19-20 h solar: 43 birds in 19
hours counted), and a block's total noted in its last minutes made a bar of an hour barely
counted (Red Kite, 6 Nov 2021: 517 birds at 18:30, after dusk). Now the bars pool the main passage
(`PART_QUANTILES` 10-90%) and, on each day, only hours counted at least half
(`PROFILE_MIN_HOUR_EFFORT`, the profile's own rule); the line (`expected`) is what the profile
predicts for the same days: each day's birds spread over its hours used by the profile in the
minutes counted, pooled the same way. The date x hour grid and the change test use the same hours.
`daytime.profile` (the profile averaged over the main passage) is dropped; `profile.day` stays,
for the coverage figure of the method page.

**Entry errors go back to the source, not into rules (2026-10-09).** `scripts/check_entries.py`
lists counts that look mistimed: a long survey's birds bunched at one end (`block_edge`), timed
outside the survey, timed in the dark, entered twice, surveys overlapping. They are corrected in
defile-dataset or Trektellen; the build does not drop or move them.

**The profile is a continuous curve, and coverage integrates it over the minutes counted
(2026-10-09, asked by the user).** Survey edges fall anywhere within a solar hour, so effort
(`slots`) and the profile live on 5-minute solar slots (`export.STEPS_PER_HOUR`): the GAM is still
fitted on hourly samples (counts are timed to the hour), each placed at its hour's midpoint, read at
each slot's midpoint (flat beyond the first and last hour sampled), cut by the daylight fraction
of each slot and normalised. `c` = Σ p × share of each slot counted. Kappa and the gap benchmark
weight a timed hour by the profile within it; `profile.p`, `daytime.profile` and best hours stay
hourly (each hour's integral), so the contract does not change. Before, the profile was one value
per hour, read at the hour's start, and a half-counted hour got half that hour's weight. On the
2026-10 release, against the hourly build: annual indices move 0.2% for the median full-tier
taxon (90th percentile 0.7%, largest single year 7%, Eurasian Whimbrel); mean yearly coverage +0.001;
gap benchmark mean 0.170 -> 0.176, paired median 0.000 (30 better, 35 worse); kappa -1% (median);
best hours change for 5 taxa. Kept because it is the right integral, not for the numbers: the
hourly profile was already smooth within the day, and dawn and dusk were already cut by the
daylight fraction.

**Age and sex: shares among the birds given one, only in usable years.** A year is usable with at
least 20 birds aged (or sexed), 5% of those counted, and both classes recorded (`demography@2`),
and a taxon needs 3 such years. The age codes `1`, `J`, `I`, `2` are one class, non-adult: the
codes used switch between years (Red Kite: mostly `1` in 2019, `I` in 2022). Every share has a 95%
Wilson interval; a pooled share over the usable years is given too.

**Both classes recorded: the smaller at least 10% of the birds aged or sexed.** Counters often tag
one class and leave the other blank. Red Kite came out 97% non-adult: in 2024, 4 030 non-adults
and 8 adults among 17 372 birds counted, in 2025 3 452 and none. Black Kite (2 334 non-adult, 0
adult in 2025), Grey Heron and gull sp. do the same; Honey Buzzard in 2024 the reverse (644 adults,
52 non-adults). The share among aged birds then measures what was tagged, not what passed. The
rule drops those years (Red Kite, Black Kite, Grey Heron and gull sp. lose the panel; 7 taxa keep
it). It also drops a year where one class is genuinely under 10%: such a taxon gets its years back
as an override, with the reason. Sex uses males against females and female-coloured birds.

**Sex is drawn like age** (`demography@3`, one `share_block` for both): the male share per usable
year, with its interval, sized by the birds sexed, the pooled share as a band, and when males and
female-types pass. The title gives the birds sexed (or aged) against all birds counted in those
years, since only part of them are.

**Records are all-time**, historical counts included (all pigeons: 116 340 on 20 Oct 1975),
decided by the user: a record is a count, not an estimate, so the start year does not apply.
Each top day carries what was written about it in the release (`records@2`, `remarks.py`): the
counters' survey remark of the day and the taxon's count remarks, including the report paragraphs
the dataset attached to that day (Red Kite, 14 Oct 2020: the site record of 2 112). Field labels
(`details:`) and the dataset's placeholders are dropped; the texts stay in French. Coverage is no
longer listed: a record is what was counted. The best day of each year is gone too.

**Every trend is benchmarked in the build, and each of its claims classed (`benchmark@1`,
`reliability@1`).** The gap-transplant test that judged the model on seven taxa now runs on all 74
trend taxa, on the same years, window and profile as the export (`benchmark.py`, cached with the
trend; ~1 min more on a full build). Its median error is 0.10 (0.07-0.20 between quartiles); seven
taxa miss by more than 0.4, all flocking or rare species whose hidden days hold a few big flocks
(Purple Heron 1.8, Eurasian Curlew 1.4, Whimbrel 1.2, Mediterranean Gull 1.1, Alpine Swift, Greylag
Goose, Northern Lapwing ~0.6), always too low. Grey Heron has no well-counted target year and is
untested. Three claims are classed, decided by the user on the proposal:

- `totals`: hidden above 0.4 of gap error; a caveat above 0.15, with 80% intervals holding the truth
  under 60% of 9+ trials, under 60% of a typical year counted, q90/q10 above 2, or untested (with a
  borrowed profile as a second reason: the benchmark measures a borrowed profile's error).
- `trend`: the totals' class, and the smooth's 95% band (median q97.5/q2.5 over the years): a
  caveat above 4, hidden above 20.
- `season`: the median passage date's 80% band: a caveat above 10 days, hidden above 30; a caveat
  when the passage runs past the counted days.

With the posterior's information floor (next entry): totals 48 show / 19 caveat / 7 hide; trend
37 / 30 / 7 (the seven whose totals are hidden); season 27 / 47 / 0. Before it, the blown-up bands
hid 22 trends and 4 seasons.
The recent-seasons test is exported and drawn but not used: a season's level is not predictable
from earlier seasons (median error 0.8), which is a forecast question. The year-by-year marking
(`estimated_years`, under half counted) is for the page to show, not a class.

**The classes are applied to what a page draws in the export, not in defileViz
(`reliability@2`).** `reliability.ELEMENTS` names each field that rests on a claim (the season
totals and the typical-season key number on `totals`; the smooth and the trend key number on
`trend`; the modelled passage dates, their smooth and the main-passage key number on `season`) and
the block's `elements` gives each its class, so defileViz looks a field up rather than knowing
which claim it belongs to. Counts (birds counted, the empirical phenology, chances, daytime, age,
sex, records) rest on no claim and are always shown. The viewer draws everything and flags what
defileViz will do: a summary at the top of each page, a strip over each figure, hidden traces
greyed and tagged `[HIDE]` with a watermark, the mostly estimated years ringed. On the 2025
release: totals 49 / 18 / 7, trend 38 / 29 / 7, season 27 / 47 / 0.

**A count with its own interval of up to an hour is timed at its midpoint
(`release.MAX_COUNT_INTERVAL`); a longer one is kept at day level.** Trektellen's hourly entries
reach the release from 2025 (30 counts on 23 Nov 2025, each 1 h); refusing them stopped the build,
and the hour they fall in is all the pipeline uses. Decided by the user: no need for more.

**The posterior's information is evaluated at a rate of at least 0.1 birds per full day
(`trend.MIN_RATE`, `information_weights`).** Where a taxon is counted but never seen (Common Wood
Pigeon on 18-25 July: 33 years of zeros), the season spline runs towards minus infinity and the
negative binomial's information, proportional to the expected count, with it. The log-likelihood
is flat below the mode but steep above it (zeros were counted), and the Laplace posterior, a
Gaussian with the curvature at the mode, was flat both ways: log-scale sd 12-16 on those days
against 0.4-0.5 in the passage, so a few draws held millions of birds. The smooth's q97.5 was 13
million for Wood Pigeon in 2009 against a median of 29 000 (now 47 000), its median passage
date's 80% band up to 100 days wide (Song Thrush, Redwing; now at most 29). Taking each day's
information as at least that of 0.1 birds per full day bounds such days by a rate the zeros still
allow, and leaves days with more birds, and the posterior mode, unchanged. It applies to the
posterior and the Laplace marginal likelihood, not to the IRLS steps, which it slowed. Across the
74 trend taxa: gap-filled totals within 1% (Water Pipit -8%), benchmark error 0.101 -> 0.097,
80% / 95% interval cover 0.81 / 0.94 -> 0.79 / 0.93, smooth band median 3.6 -> 2.7 (max 5e8 ->
14), same build time. `tests/test_explore.py` has a synthetic case (24x without the floor).
Rejected: summing only days with expected birds (hides the problem in one output), a prior on the
spline's edge (would need tuning per taxon).

**Windows per taxon: fitted on a model window, shown over a wider view window, by rule**
(`window@1`). The default window (18 Jul - 18 Nov) is where 80-100% of years are counted; from
20 Nov to 1 Dec only about a third are. Late taxa still pass then: Red Kite averages around 120
birds a day on 30 Nov in the years counted, and 2025 had 2 600 counted on 19-23 Nov. So each taxon
gets:

- a model window: the default, extended to 0.5% / 99.5% of its mean passage plus 5 days, but only
  over days counted in at least a third of its years, since the trend fills the rest. Never cut
  below the default, so a taxon passing inside it keeps the benchmarked fit. 41 of the 74 trend taxa
  are extended, by at most 6 days (to 20-24 Nov; Black Kite and Sand Martin to 14-15 Jul). Red
  Kite's 2025 total goes from 20 700 to 24 700.
- a view window for the season panels, extended the same way to 0.1% / 99.9% over days counted in
  at least 10% of years (to 2 Dec for most late taxa). Totals, shares and the yearly passage dates
  stay those of the model window: beyond it, the gaps to fill are too long, and filling them held
  the last counted day flat to 2 Dec.
- `passage_beyond_counting` (51 full-tier taxa; 15 with `window@2`, below): the passage still
  reaches the model window's outer limit, so the totals are totals up to that date. A property of
  the count, for the page to state, not a fault to fix.

Both windows are settings, overridable as `[MM-DD, MM-DD]` with a reason.

**The viewer follows the pipeline; defileViz tells the story (2026-10-09, decided by the user).**
The viewer is the developer's model and diagnostic tool, in pipeline order: what defileViz shows,
configuration, counts and effort (birds, mean coverage and ratio index per year), time of day and
coverage (the profile surface, the counted histogram), the season as counted, the trend model (with
its components: the season of the first and last year, each year with and without its episodes
over the counted birds per full day), validation (reliability, benchmark), and the derived blocks.
defileViz is the visitors' page, empirical first with the model drawn on top, one question per
section: when to see it (chances by date, time of day in clock time), how many each year, has the
timing changed (every season as a row of days, its counted median date and the smooth one), who
passes (age, sex), memorable days. Little text on the page; each figure's (i) opens the modal of
the method it rests on, one modal per method rather than one long one: counting and coverage, the
season as counted, the trend model, how reliable, age and sex, in that order on the page's "How it's
made" strip. The modals stay in defileViz and are updated by hand from `DECISIONS.md`: some lag is
accepted.

**The export is strict JSON** (`export.dumps`): a float NaN or infinity is written as null. `json`
writes them as `NaN`, which browsers refuse; the benchmark's ratio estimator has no interval
(`gap_ratio.cover80`), and 127 species files did not load in defileViz.

**A taxon passes beyond counting when a tenth of its passage falls in the last week counted
(`window@2`, 2026-10-09, asked by the user: "way too sensitive").** The first test (99.5% of the
mean passage within 5 days of the model envelope's edge) flagged 51 of the 86 full-tier taxa, most
for a trickle of late birds, and the page said of each that "it still passes when counting ends".
Now the share of the mean passage within the model envelope that falls in its first or last 7 days
must reach 10% (`window.EDGE_DAYS`, `EDGE_SHARE`; `window.edge_shares` is exported). 15 taxa:
early, Common and Alpine Swift, Sand Martin and the gulls, Purple Heron, Common Merganser (passage
under way by 18 July); late, Common Crane (30% in the last week), Redwing, Hen Harrier, Common
Buzzard, Peregrine and Northern Lapwing. Red Kite (8%) is no longer flagged. The page words it as
"much of its passage falls outside the counting season".

**The smooth passage dates are drawn only when the season claim is `show` (`reliability@3`,
2026-10-09, asked by the user).** The lines on the timing panel (10%, half and 90% of the smooth
season passed) read as a finding, and a caveat has no room on them, so a caveat hides them
(`reliability.NO_CAVEAT`; the key number keeps its caveat). Two reasons are added to the season
claim: `tails_band`, the 80% bands of the 10% and 90% dates (now in `trend.passage`, from the same
draws as the median), against the same `PASSAGE_BAND`; and `few_birds`, under 50 birds counted in
a typical season (`SEASON_BIRDS`). The bands alone do not do it: the model's smooth timing keeps
them under 10 days even for Peregrine (4 birds a season) or Eurasian Jay. Season classes on the
2025 release: 36 show, 37 caveat, 1 hide (was 27 / 46 / 1), so lines are drawn for 36 of the 74
trend taxa. Reasons among the 38 others, often several: few birds 30, passing beyond counting 13
(Common Buzzard and Common Crane for that alone), wide bands of the 10% and 90% dates 7, of the
median 4.

**Age and sex take one of three displays (`demography@4`, 2026-10-09, asked by the user).** A
year counts when 5% of its birds were classed and the smaller class is at least 10% of them (both
recorded). With 3 such years of 20 classed birds or more, a share per year (`display: years`);
else one share pooled over all the years that count, if they hold 30 birds or more (`pooled`);
else nothing. Before, a taxon needed 3 years of 20 birds or got nothing: 10 taxa. Now 17: Red
Kite, Montagu's and Hen Harrier (age), Merlin (age), Eurasian Sparrowhawk, Great Cormorant, Grey
Heron and the gulls gain a pooled share. Age and sex are in the release from 2001 only, a few
hundred birds a year until 2019, ten times more since, so most per-year panels start late.

**The picker's highlights are curated, not a rule (2026-10-09, asked by the user).**
`content/highlights.tsv` lists them, seeded with the species of the Défilé's 2019 (raptors) and
2020 (other monitored species) papers that have a page: 32. The rule tried first (a `full` story
and 100 birds a season) left out Common Crane and Grey Heron for their caveated totals and put in
Brambling and Common Reed Bunting. The story dot still says how good each taxon's data are.

The EBBA2 link opens the abundance map (`/ebba2/abundance/`), not the occurrence map.

**Key numbers** are read from the blocks, not computed apart: the main passage is the smooth
season's 10-90% in the last year (else the pooled counted seasons of the last 10), best hours the
fewest solar hours holding 60% of the profile on the median passage day, the typical season the
median of the last 10 gap-filled totals, the trend the smooth's change from the start year, the
chance the share of well-counted days in the main passage with at least 1 or 10 birds.

**Written accounts replace the report extracts** (`accounts@1`). The page showed the paragraphs
of the annual reports as extracted (French, unedited, and for a group those of its own taxon
member). It now shows authored accounts from `content/accounts/`: a general account in up to three
sections and a short account per season, in French and English, edited from the reports and the
2019 paper with the numbers left to the page's figures. The build reads only the two authored TSVs
and checks them; `report_text.csv` and `paper_text.csv` are still copied with the release, for the
editors' coverage and totals checks. `reports.json` (the non-species report texts) is no longer
written: defileViz never read it. Location: `content/accounts/` in this repo, versioned and next to
the code that reads it, rather than in defile-dataset (the accounts are written for this page, not
data) or `data/` (generated, never committed); the authored files at its top, `reading/` and
`review/` for what the editorial scripts regenerate.

**Hourly weather pilot (2026-10-10, requested by the user).** `scripts/research/build_hourly_weather.py` splits complete observed Trektellen surveys at UTC hour boundaries, including empty and partial hours, with unresolved counts kept separately and species-specific completeness. `scripts/research/analyse_hourly_weather.R` fits raw counts with real-hour exposure, civil-daylight time, year/season effects and shared day effects, comparing a baseline against weather without the episode smooth. The pilot uses completed 2022–2025 seasons and four taxa; contiguous week and hour holdouts test wet/dry predictions. A bounded snapshot of the existing Defile ERA5 Parquet files is an explicit data input, with source hashes and interval/unit conventions; no forecast code is imported and production Explore exports are unchanged. This is an experiment, not a selected replacement: historical aggregated counts, exact within-hour integration and arbitrary-scale dispersion remain open. See `scripts/research/README.md` for execution and limitations.

**Hourly pilot issue fixes (2026-10-10, requested by the user).** Short validation masks stop at actual effort breaks and seasonal dates use a non-leap calendar. Gaussian coefficient uncertainty is regularized after fitting with an exposure-scaled information floor analogous to `trend.MIN_RATE`, tested at 0.01/0.1/1 bird per daylight day; fitted counts and coefficients are untouched. Predictive means use the analytic log-normal expectation, while shared simulations provide count intervals. Larger time bases and removal of cloud/radiation are separate diagnostic candidates. The actual production episode GAM, profile estimator and flock dispersion are refitted within each common fold on the same four-year eligible observations; this compares architectures, not the full historical production fit. Missing and closure weather are audited against observed support, and the zero-passage closure assumption is evaluated separately without converting closures to training zeros. No replacement model is selected or exported. Methods and results are recorded in `scripts/research/README.md`; outputs are under `logs/hourly-weather-v2/`.

**Daily rate distribution experiment (2026-10-10, requested by the user).** The hourly weather pilot now compares an independent NB GAM, an integrated mean-one Gamma daily multiplier with Poisson counts, and the same multiplier with exposure-scaled NB flock variation. Training-only mgcv bases and smoothing penalties are shared; population coefficients and daily/count shapes are fitted by penalized marginal likelihood, with conditioning on retained hours for short gaps. Numerical integration, gradients, marginal information and constant-rate aggregation are checked independently. Gamma + flocks reduces Pigeon whole-day predictions from 3.33 million to 1.13 million against 621,615 birds, retaining wet-day gains for Buzzard/Red Kite, but dry-day and short rainy-gap bias remain. Gamma-Poisson is rejected because omitting hourly flock variability produces extreme population rates. Removing day effects undercovers daily uncertainty. No replacement is selected or exported; joint marginal smoothing selection and residual temporal/within-day weather structure remain open. See `scripts/research/README.md`; outputs are in `logs/hourly-weather-v3/`.

**Expanded species panel and smoothing follow-up (2026-10-11, requested by the user).** Keep 12 report-priority taxa and four separately labeled passerine comparisons, with observation scope applied before zeros are inferred. The user confirmed passerines were counted throughout complete surveys in 2022–2025; this does not authorize historical passerine zeros. Priority taxa use documented 2023–2025 report scope with 2022 continuity explicitly assumed pending the unavailable report. On 16 species, the iterative smoothing updates barely change held-out performance and usually stall or hit the step limit. Wet whole-day errors are lower than the matched production refit on average but uncertain; dry whole-day errors are higher. Do not select the iterative smoother or replace production gap filling. The next work is day-rate calibration, dry-day bias, year-robust validation and resolving 2022 recording protocol. See the expanded results and caveats in `scripts/research/README.md`; combined artifacts are generated under `logs/hourly-weather-panel-v4/`.

**Weather-sensitive occurrence gate experiment (2026-10-11, requested by the user).** Add a two-part hourly model with exposure-scaled complementary-log-log probability of any birds and an exposure-scaled zero-truncated NB for positive counts. Across the 16-species panel, held-out whole-day MAE improves over the matched production refit on wet and dry intervals, and the occurrence probability tracks the observed positive-hour fraction across rain bands. The positive-count component still overpredicts counts in the sparse ≥3 mm/hour band, and the model has no shared day state, retained-hour conditioning or calibrated predictive intervals. Treat this as a promising diagnostic, not a replacement. Next, add a shared daily activity/rate state while retaining the weather-sensitive occurrence gate; validate occurrence and positive counts by held-out year and weather support. Keep closure hours unknown and production gap filling unchanged. See `scripts/research/README.md`; outputs are generated under `logs/weather-activity-review/`.

**Restore the agreed five-step sequence (2026-10-11, user correction).** The agreed order was (1) assessment/bootstrap/numerical checks and saved coefficients, (2) species-level positive-count calibration, (3) shared daily state, (4) predictive uncertainty and held-out years, and (5) mixed temporal scales/history. Building the shared-state prototype skipped steps 1–2 and fulfilled only part of step 4. The active checklist is `scripts/research/GAP_FILL_PLAN.md`. Correct the panel bootstrap by resampling calendar weeks jointly across species and computing the macro statistic inside each replicate. Correct daily rain classification: reference files had total daily rain while activity files had exposure-weighted mean hourly rain; every candidate now receives one common classification from matching intervals. These corrected results supersede the earlier daily wet/dry summaries, including the occurrence-gate entry above. Save independent activity coefficients and audit numerical gradients/convergence. Assess positive counts by species and year, reporting short-gap and whole-day tasks separately. A tenfold positive-smooth penalty is rejected as a heavy-rain fix: predicted whole-day-fold heavy-rain counts rise from 2,829 to 3,340 against 1,390 observed, despite a small overall gap-MAE improvement. Do not declare the remaining steps complete because the prototype exists. Retain recording scopes, unknown closure counts and the production comparison.

### Gap-fill uncertainty and mixed-scale bridge (11 October 2026)

Continue the original five-step sequence recorded in `scripts/research/GAP_FILL_PLAN.md`. Reject the simpler positive-only count design as well as the tenfold positive-smoothing candidate: both worsen heavy-rain calibration on the common assessment masks. Retain the original positive component for the shared-state uncertainty experiment. Use normalized Gamma quadrature instead of the high-shape lognormal approximation, exact all-zero-day integration and retained-zero conditioning, and coherent joint hourly/daily predictive count draws. Their coefficient covariance remains conditional on fitted Gamma shape, NB dispersion and smoothing; numerical sensitivity and held-out coverage must be assessed before any operational use.

The mixed-scale bridge defines a canonical-hour hurdle distribution with binomial thinning and aggregates its probability-generating functions over the actual observed interval. Preserve unresolved recent survey totals intact and avoid duplicating their hourly observations. The present exposure-scaled fitter requires a coherent-likelihood refit; within-hour varying intensity and joint observations sharing a clock hour are outstanding. Inventory historical recorded totals without inventing absence zeros: the user's systematic passerine-counting confirmation covers complete 2022–2025 surveys only. Production is unchanged.

**Stabilized integration and species-baseline pooling (2026-10-12, user authorized).** Continue the original five-step plan. Posterior-centered integration resolves sensitivity flags across all 128 blocked/annual contexts for both candidates. Evaluate a strength-24 exposure-weighted positive-log-rate variance penalty around each species baseline, leaving occurrence smoothing unchanged. It removes extreme sparse-species uncertainty and improves passerine heavy-rain totals, but priority-species heavy-rain excess and short dry-gap tradeoffs remain. Preserve exploratory candidate status; production is unchanged. Recompute predictions from saved fits when numerical methods change rather than optimizing unnecessarily.

**Constrained coherent recent-data refit (2026-10-12, user authorized).** Fit canonical-hour thinning and intact summed-count likelihoods jointly with a shared daily Gamma state. Initially estimate gate/count intercept and rain corrections while freezing training-only GAM shapes, daily shape and NB size. State explicitly that this is not a full coherent GAM refit and its intervals omit uncertainty in frozen components. The recent input has 291 intact surveys and no repeated species-clock-hour components. Inventory historical recorded totals but exclude them until historical scope is verified; the recent passerine confirmation does not authorize historical absence zeros. Keep [the five-step acceptance tracker](scripts/research/GAP_FILL_PLAN.md) authoritative.

**Reject frozen-time coherent candidate for arbitrary-hour filling (2026-10-12).** All 64 annual constrained coherent contexts pass numerical integration/gradient checks and daily conservation, but matching-data accuracy changes are small and mixed. Expanded coverage exposes extreme unsupported time extrapolation: Cormorant's 45 zero-count hours outside the civil-daylight range in 2025 receive 7.35 million predicted birds. Keep these observations and the diagnostic failure visible. The next coherent fit must estimate the time effects on expanded coverage, rather than freeze daytime GAM shapes. Neither clipping counts nor declaring numerical success constitutes scientific acceptance.

**Require simplicity and speed; stop extending the complex candidate (2026-10-12, explicit user instruction).** Preserve the hurdle/shared-Gamma/mixed-count fits as diagnostics and stop broad reruns and iterative numerical additions. Start a separate 16-coefficient count-rate GAM with season, expanded daylight-relative time and rain. Fit intact interval counts against sums of hourly expected counts using a Poisson working mean objective, without latent daily integration or count convolutions. This preserves mean aggregation and actual exposure, but does not establish Poisson dispersion, retained-hour conditioning or calibrated predictive uncertainty. Test four difficult contexts for numerical reliability and runtime before the full 16-species comparison; smoothing selection is training-only and remains outstanding. See [the simple-rate plan](scripts/research/SIMPLE_RATE_PLAN.md). No production replacement is authorized by a successful pilot alone.

**Bounded time profile for the simple rate candidate (2026-10-12, continued user-authorized development).** Full-panel assessment rejects a noncyclic-time spline plus night indicator: Barn Swallow's held-out predawn observations extend well beyond training support and the spline log-rate explodes. Replace the time smooth with three 24-hour UTC sine/cosine pairs, retaining civil-twilight status, a two-slope log-rain effect and linear wind components. The result has 19 coefficients and direct expected-count interval aggregation. Sixty of 64 annual contexts pass current checks at a median 0.216 seconds including training-week smoothing selection. Mean prediction improves markedly over the pathological simple baseline, but night counts remain excessive, four fits fail, Pigeon is absent from the paired comparison and uncertainty/short gaps/production comparison are outstanding. Retain an experimental candidate; do not select a production replacement or relax acceptance thresholds. See the completed assessment in `scripts/research/SIMPLE_RATE_PLAN.md`.

**Benchmark full-day weather gaps with a small working mean model (2026-10-12, user requested assessment and implementation).** Reuse the original three seven-day masks and exact training/test intervals; compare against the production episode architecture refitted on matching recent inputs. A 22-coefficient year/season/clock/rain/wind mean model with fixed variance power 1.5 passes all 48 contexts and takes a median 0.176 seconds including inner smoothing selection. Its species-balanced full-day MAE is about 5% lower overall and 36.5% lower on wet days, but 8.1% higher on dry days, with heavy-rain total excess and passerine exceptions remaining. The exploratory bootstrap supports a wet gain but not overall superiority or dry noninferiority. Annual seasonal interactions and training-only selection between them and the smaller model did not solve the tradeoff. Retain the small fixed-power candidate for further validation, not production replacement. Use one exact-Hessian trust-region solver and high-accuracy derivative checks; no optimizer ladders, latent-state integration, new episode term or count convolution. See `scripts/research/SIMPLE_RATE_RESULTS.md`.

**Prioritize core large birds and assess residual seasonal episodes (2026-10-12, user clarification).** Evaluate the ten tested raptors/storks/other large birds as the primary scientific group; retain two pigeons and four passerines as separate secondary groups, with every species reported. Use median species error ratios alongside equal-species absolute MAE so one abundant taxon cannot determine the assessment. The seasonal smooth and year offset already describe expected abundance; an episode tests residual within-year temporal departures beyond those and weather. A bounded 50-coefficient alternative adds seven centered spline coefficients per year, with training-week-selected roughness/amplitude shrinkage. All 48 fits pass, median 0.428 seconds with single-thread dense linear algebra. It improves pigeons/passerines and pooled error but worsens core-species MAE 4.1% relative to the 22-coefficient weather-only candidate. Retain the smaller model for core-species development, not a universal episode addition or post-hoc species-specific switching. Freeze the primary specification and groups for additional held-day/storm validation. No production change; uncertainty, retained-hour conditioning and historical scope remain outstanding. See `scripts/research/SIMPLE_RATE_RESULTS.md`.

**Keep the simple core-species model after frozen-mask sensitivity testing (2026-10-12, user authorized).** Freeze the 22-coefficient weather-only model and scientific groups before testing count-independent one-, three- and shifted seven-day gaps. The 4,191 matched held-out species-days reuse observations previously scored in development, so this is internal placement/length sensitivity, not independent confirmation. All 48 fits pass at median 0.175 seconds. Core MAE improves 14.1% overall and 41.9% wet versus original, with improvements at each gap length and within each year. Dry macro MAE improves 3.7%, but only four of ten species improve and its bootstrap crosses zero. Wet core totals remain 24.5% high; dry zero days, passerines and dry pigeons remain limitations. Keep the model unchanged for core development, without species switches or universal deployment. Next assess simple uncertainty and retained-hour use; production, independent confirmation and historical scope remain open. See `scripts/research/GAP_VALIDATION.md`.

**Add a small empirical prediction layer to the frozen mean model (2026-10-12, user authorized).** Preserve every saved 22-coefficient outer mean fit. Calibrate count intervals using training-only calendar-week out-of-fold residuals and adjust missing-hour means by a retained count ratio shrunk with one training-selected pseudo-count (including a no-adjustment option). This is an empirical update, not a Gamma-Poisson posterior or a new latent-state likelihood. All 48 contexts complete at median 0.330 seconds. Core three-hour-gap MAE improves 15.8% overall, 15.4% dry and 19.4% wet; all ten core species improve overall. Core full-day nominal 95% coverage is 95.2%; interval score is 294.4 versus the matched original 356.5. Short wet intervals are conservative and wet passerine full-day 95% coverage is only 90.4%. Mean predictions for wholly missing days are unchanged and short-gap core total bias is slightly worse. Retain these research additions without claiming coherent multi-day uncertainty, independent confirmation or universal calibration. Historical scope, unseen years and production replacement remain open. See `scripts/research/SIMPLE_RATE_UNCERTAINTY.md`.

**Assess retained observations in practical short gaps (2026-10-12, user requested).** Refit the unchanged 22-coefficient weather model with counted hours of target dates included, hiding only the same early/middle/late three-interval gaps used in the earlier clean experiment. Refit the original architecture on exactly matching partial-day inputs; do not substitute its full-day predictions. All 48 weather fits pass at median 0.187 seconds. Including retained hours in fitting improves core MAE 2.3%; an additional training-selected retained update improves another 14.0%, including every core species overall. Adjusted MAE 9.75 is comparable to original 9.97, with no demonstrated superiority and only four core species improving versus original. Wet point and interval performance, retained-zero cases and overall missing-total bias (+5.5% versus original +1.0%) remain limitations. Retain the simple update as a research option, with no new terms or post-hoc weather switch. Production remains unchanged; resolve point-error versus total-bias targeting before operational use. See `scripts/research/SHORT_GAPS.md`.

**Decompose short-gap bias and assess simpler response functions (2026-10-12, user requested).** Keep every GAM unchanged. Separate 945 birds of existing core excess from the current adjustment's additional 659. Cormorant contributes 1,388 of 1,604 final net excess birds, concentrated in morning predictions; adjustment-added bias comes mainly from Buzzard/Red Kite. Fixed `s` already changes evidence weight through `R/(R+s)`; no automatic `s(coverage)` rule is required. Compare current shrinkage, constant blend, expected-coverage blend and bounded response, with parameters selected on training calibration only under MAE/MSE. Bounded MAE improves core error 3.8% and pooled bias to −1.4%, but underpredicts wet totals 11.4%, worsens Honey Buzzard/Stork totals and does not improve median absolute species bias. MSE selection alone does not fix the old rule. Preserve bounded response as a diagnostic candidate rather than selecting from pooled cancellation; remove inherited interval bounds from alternative point outputs. No production or selected adjustment change. Next assess species/year/time-profile calibration before adding corrections. See `scripts/research/ADJUSTMENT_FUNCTIONS.md`.

**Prioritize the historical coverage target over correction-function tuning (2026-10-12, user clarification).** Audit actual non-weather-stop effort against the fixed site comparison season without inventing zeros. Recorded civil-daylight coverage is 49% in 1993–2007, about 61% in 2008–2016 and 86% in 2022–2025; pre-1993 is only 7%. Existing recent-year short-gap tests almost never retain less than half the observed effort and do not establish historical-season reconstruction. Freeze the small weather mean and adjustment functions; replace the previously proposed next species/time-profile tuning step with a historical coverage-transfer assessment, crossing actual attendance templates with hourly versus intact survey-total input, separate weather-driven masking, and species-season total error. Evaluate the general mean before the optional retained-count update and refit year offsets using sparse retained information. Historical weather/scope and unsupported dawn/evening extrapolation remain explicit. The audit is completed; the new fit experiment is proposed, not run. See [the assessment review](scripts/research/HISTORICAL_GAP_ASSESSMENT.md).

**Complete the historical coverage/resolution experiment without new corrections (2026-10-12, user authorized).** All 640 frozen contexts pass unchanged numerical checks; target-year hourly versus connected survey-total inputs preserve exactly the same counts/exposure while other years inform shared effects. Core survey-input seasonal absolute relative error averages 9.7/7.2/5.2% under three post-1993 attendance templates versus original 12.4/8.7/5.4%; median species comparisons and four-year bootstrap do not establish ordinary-attendance superiority, and daily error is worse without the optional update. Weather-selected gaps improve clearly (8.0% versus 15.9%, nine of ten core species). A pre-1993 template retaining only 5% fails for both models despite numerical convergence. Keep the unconditional mean primary and the existing retained-count update optional: it provides no consistent seasonal advantage. The historical weather cache is already continuous with complete predictors from 1965–2026; next test actual historical mixed intervals under verified core-species recording scope rather than continue species/function tuning. Production remains unchanged. See [the completed results](scripts/research/HISTORICAL_TRANSFER_RESULTS.md).

**Historical core recording scope (2026-10-12, owner requested).** Use the released taxonomy’s adopted systematic start dates and require a positive main-direction record in every eligible year through 2025. All ten candidate core species start in 1993 and meet the annual-record rule. Annual presence selects the panel; the adopted taxonomy convention authorizes complete-survey absence zeros. Keep weather stops, incomplete effort and unsupported species-dates unknown. Compare actual 1993–2021 mixed intervals with the unchanged simple weather specification and original architecture. Production remains unchanged.

**Actual historical core comparison complete (2026-10-12).** All 40 matched 1993–2021 interval contexts pass numerical checks, with 1.76-second median weather fits and unchanged recent regression coefficients. Weather mean MAE improves 14.5% on wet whole-day tasks but worsens 6.6% dry; nine of ten core species worsen dry. Reconstructed-total absolute error worsens across all whole-day masks, with the strongest clear losses in 1993–2007. Native short gaps also favor the original. Reject universal replacement; stop correction tuning and specify weather integration around the original abundance backbone before a new fit. Do not repeat the earlier rejected low-rank episode trial. Years without held-out truth do not enter validation scores. Production remains unchanged. Results and limitations: [HISTORICAL_COUNTS.md](scripts/research/HISTORICAL_COUNTS.md).

**Diagnose historical deterioration before redesign (2026-10-12, user requested).** All 120 frozen recent-input controls show no group-wide recent loss from historical training (41.46 → 41.47 birds MAE); species shifts remain, including Grey Heron wet losses and Red Kite gains. Coarsening recent training has negligible effect. Thirty current mixed-input recent comparisons retain 10.4% overall and 35.0% wet gains. Thirty historical weather-removal controls worsen error, so weather remains useful. Forty refitted original-model time ablations on the ten-core seven-day task show early dry error 21.52 full, 21.54 without shift and 23.28 without episodes, against weather mean 24.45. Retain the simple weather candidate; immediate wholesale redesign was premature. A bounded historical temporal-variation trial must preserve recent gains, rather than blindly repeat the earlier rejected recent-only episode trial. Count/survey source hashes are unchanged; season window, daylight eligibility and intact-survey inclusion explain recent input differences. All 180 mean fits pass unchanged numerical checks; full benchmark reproduction passes for ten species. Production unchanged. See [HISTORY_DIAGNOSIS.md](scripts/research/HISTORY_DIAGNOSIS.md).

**Complete one bounded historical episode screen (2026-10-12, user authorized).** Add four centered cubic-spline coefficients per year with fixed strength-100 roughness/amplitude penalty, keeping weather/time/season/year specification, interval aggregation, working power and training-selected base smoothing unchanged. Ten historical seven-day contexts and thirty current recent contexts train on eligible actual history. All eighty final fits pass numerical checks and forty base replays reproduce coefficients within 1e-7. Historical dry MAE improves 33.40 → 32.76 (all ten species), wet 20.77 → 20.41; recent dry 47.71 → 46.63 and wet 29.91 → 29.75. Early historical dry error remains 23.86 versus original 21.52; reconstructed-season error 15.52% versus original 13.27%. Median final episode fit is 1.365 seconds versus 0.156 baseline, with 183 versus 51 coefficients. The candidate fails prespecified 5% historical dry improvement and five-times relative runtime gates. Preserve it as a modest positive temporal-variation diagnostic, but retain the simpler weather model and do not retune or expand this implementation on reused masks. Next proposed cheap control is shared seasonal flexibility, not more per-year corrections; it is not yet implemented. Production unchanged. See [HISTORY_EPISODE.md](scripts/research/HISTORY_EPISODE.md).

**Reject richer shared season under unchanged fitting rules (2026-10-12, user authorized).** Change only common seasonal capacity from mgcv k=8 to k=20, adding twelve shared coefficients (63 total). Preserve the forty historical seven-day/current recent contexts and exact nonseasonal columns/penalties; reselect smoothing using the unchanged training-week grid. Eighty final fits pass numerical checks, forty base fits reproduce coefficients and held predictions within 1e-7, and 104 tests pass. Historical dry MAE 33.40 → 33.60, wet 20.77 → 20.78; recent dry 47.71 → 48.07, wet 29.91 → 30.01. Early dry error is 24.89 versus original 21.52; reconstructed-season error 15.85% versus original 13.27%. Final fits remain fast (median 0.270 seconds versus 0.159); reject on historical accuracy, not speed. Shared season/clock smoothing changes selection (strength 10 for 37/40 versus 22/40), so this is a capacity test under existing fitting rules, not fixed-penalty isolation. Retain the small weather model; pause smooth-term additions and propose a working-criterion/mixed-interval-weight audit before another model. Earlier recent coarsening showed negligible loss and Gamma-Poisson was already rejected, so neither is an established cure. No new criterion or production change. See [HISTORY_SEASON.md](scripts/research/HISTORY_SEASON.md).

**Complete working-criterion and shared-smoothing audit (2026-10-12, user authorized).** Audit forty saved paired contexts using retained inputs only, with no new fits or hidden-count scoring. Power-1.5 loss, common-log-rate score and expected information scale with the square root of duration at constant rates; an intact eight-hour total therefore has 35% of the weight of eight hourly counts. Early years provide 33.9% of retained hours but 16.6% of intercept working information in historical-gap fits; hypothetical square-root-duration weights raise that information share to 30.5% at unchanged fitted means. The larger seasonal screen increased conditional season EDF about 6 to 15 but changed the unchanged clock penalty 100-fold in fifteen of forty contexts; clock flexibility also fell. These establish resolution dependence and a smoothing interaction, not their causal responsibility for historical errors. Keep the small weather mean; next proposed control weights its existing criterion by square-root recorded exposure, without extra terms, changed powers or simultaneous separate smooth parameters. The control is specified but not fitted. Earlier coarsening results and rejection of Gamma-Poisson/hurdle machinery remain valid. Production unchanged. See [RATE_CRITERION.md](scripts/research/RATE_CRITERION.md).

**Reject duration weighting and damping as replacements (2026-10-12, user authorized damping).** Test powers 0.25 and 0.5 on the unchanged 51-coefficient weather mean, retaining training-only common-smoothing selection and all count/interval masks. The damped arm completes forty contexts with baseline replays and numerical checks: historical dry MAE 33.40 → 33.29, early dry 24.45 → 24.24, season error 15.83% → 15.68% versus original 13.27%; recent dry 47.71 → 48.25 and wet 29.91 → 30.68 (+2.6%). It fails historical benchmark and recent wet gates despite median final fit 0.159 seconds. The stronger arm stalls in the exact solver on Honey Buzzard; after interrupting the first stalled batch, unchanged pending contexts run under a 60-second whole-context limit added before reviewing accuracy. All four Honey Buzzard contexts time out. Thirty-six completed stronger contexts cover nine species, with small historical dry improvement but recent dry/wet losses 2.4%/5.9%; these are partial diagnostics and cannot pass completeness. Do not adopt either arm, exclude species to claim acceptance, search further powers, relax solver thresholds or add optimizer ladders. Keep unweighted fitting; resolve bounded numerical behavior before further fitting experiments. The larger season/clock smoothing interaction remains untested separately. Forty baseline contexts reproduce within 1e-7, seventy-six completed weighted final fits pass checks, independent weighted gradients/Hessians/analytic optima pass, and the generalized reviewer preserves ten default seasonal result tables byte-for-byte. Production unchanged. See [DURATION_WEIGHT.md](scripts/research/DURATION_WEIGHT.md).

**Bound the small rate fitter without changing the model (2026-10-12, user authorized).** Newton-CG fails the existing high-count check (gradient 0.0091) and is rejected. BFGS with the unchanged 1e-5 gradient target initially reproduces all 116 saved fits but one formerly stalled CV fit reaches 100 iterations at gradient 0.001211. Raise the common computational cap to 200, without changing acceptance thresholds, and repeat the complete numerical batch. All 152 fits pass independent gradient/derivative checks, including all 36 CV fits from the four stalled Honey Buzzard contexts. Maximum saved objective relative difference is 4.12e-16 and component-rate relative difference 2.66e-6; median final runtime is 0.160 seconds. Raw SciPy statuses include 86 precision-loss messages and 66 successes; no iteration limits remain and statuses are retained explicitly. Adopt BFGS for new research fits, with no model-level retries or fallback predictions. Archived episode/season/duration runners explicitly keep the exact solver for reproducibility and retain its documented stall risk. Duration weights remain rejected, no hidden-count accuracy was reviewed, and production remains unchanged. Separate season/clock smoothing is proposed next, not implemented. See [BOUNDED_SOLVER.md](scripts/research/BOUNDED_SOLVER.md).

**Reject separate season/clock smoothing as a historical remedy (2026-10-12, user authorized).** Keep the existing 51-coefficient unweighted weather mean and select seasonal/clock strengths independently from 0.1/1/10 using the unchanged retained-training week folds and daily MAE. All 1,080 inner and eighty final fits pass unchanged numerical gates; forty saved baseline replays pass. Independent strengths are selected in 24/40 contexts, but historical dry MAE is effectively unchanged (33.3996 → 33.3990), early dry slightly worsens (24.4454 → 24.4503 versus original 21.5174), and reconstructed-total error remains 15.79% versus original 13.27%. Historical wet/recent dry/recent wet and final-speed gates pass; all three historical-original gates fail. Median final fit is 0.155 seconds versus 0.151; selection plus final optimization is 5.49 seconds. Raw precision-loss flags remain recorded despite independent numerical acceptance. Do not adopt this extension, enlarge the grid or retry richer bases on reused targets. Stop local smoothing/weighting/correction screens and explain a simple abundance-model redesign before further fitting; year-varying temporal structure is a hypothesis supported modestly by earlier episode/ablation results, not an established cure. The original five-goal tracker now describes the simple-model strategy explicitly rather than obsolete hurdle/Gamma machinery. All 104 tests pass; production unchanged. See [SEPARATE_SMOOTHING.md](scripts/research/SEPARATE_SMOOTHING.md).

**Specify daily passage redesign before another fit (2026-10-12, user authorized design step).** Propose a jointly fitted daily log-rate deviation with a within-year AR(1) quadratic penalty, retaining the current season/year/hour/weather terms, actual hourly exposure, intact count means and unweighted power-1.5 criterion. This is an episode concept with local calendar-date structure and proposed sparse computation, not an established cure or fewer parameters: approximately 4,092 daily values plus 51 shared coefficients. The original episode ablation supports local multiday departures more than long-term timing shifts; the earlier 183-coefficient broad episode candidate remains rejected. Design a bounded eight-context numerical pilot before efficacy fitting, fixed seven-day correlation scale and log-SD 0.5, with independent derivatives, sparse/dense synthetic agreement, baseline replay and unchanged speed gates. Only after numerical success would training-only amplitude selection and a complete core historical/recent screen follow. No quadrature, count convolution, post-hoc retained update, new weather predictors or broader smoothing search. Explicit limitations include weather/state confounding, within-day bursts, no reservoir/release dynamics, more local unknowns and conditional-mode rather than integrated predictions. No new implementation, fit, predictive assessment or production change in this step. See [ABUNDANCE_REDESIGN.md](scripts/research/ABUNDANCE_REDESIGN.md).

**Complete sparse daily-passage numerical pilot (2026-10-12, user authorized).** Implement fixed seven-day/SD-0.5 daily deviations jointly with the unchanged weather mean, using one constrained sparse scoring method (100 updates, twenty Armijo halvings, no retries). Independent synthetic checks establish objective derivatives, endpoint/centering/year resets, empty runs, cross-date intervals, dense KKT agreement and influence calculations. Eight fixed core contexts pass numerical acceptance, baseline replay and median runtime gates; maximum constrained gradient 0.0001475 and derivative error 1.992e-8. Historical Buzzard reaches the iteration cap but passes the separately fixed 0.001 gradient limit; keep that status and budget. Median final fit 0.623 seconds, paired runtime ratio 3.65, maximum context 2.132 seconds. The 4,092 daily values are sparse, but total working effective DF is 483–1,212, so this is not statistically small or proven resistant to overfitting. All context-years have retained wet/dry hours, without establishing causal weather identification or storm-closure accuracy. No held-out accuracy, predictive intervals or full efficacy fits computed. Freeze implementation and propose training-only amplitude selection on the full ten-core historical/recent screen next; no production selection. All 104 tests pass. See [ABUNDANCE_REDESIGN.md](scripts/research/ABUNDANCE_REDESIGN.md).

**Do not adopt training-selected daily passage after incomplete full-core screen (2026-10-12, user authorized).** Attempt all forty fixed contexts with training-only SD selection from 0/0.25/0.5/1, unchanged seven-day correlation and numerical budgets. All 480 inner fits saved; four fail gradient acceptance at the 100-update cap (recent Heron/Stork, historical Heron/Marsh Harrier), and historical Sparrowhawk fails its selected final fit. No retries, timeouts, dropped amplitudes or fallback predictions. Thirty-five accepted contexts cover seven historical species and 28 recent masks across ten species. On matching completed targets, historical dry MAE 44.73 → 41.60 versus original 42.33; recent dry 47.68 → 45.23 versus original 47.77. All seven historical and all ten recent species improve dry MAE against weather. These partial absolute scores must not be compared with full ten-species historical scores. Reconstructed-total error remains 15.10% versus matched original 12.94%, worse for every completed historical species; paired year-bootstrap difference +2.16 percentage points [1.03,3.19]. Mean signed season bias worsens from weather −1.58% to −7.19% versus original −3.50%. Median completed final fit 0.514 seconds, paired ratio 2.86; selection-plus-fit 6.29 seconds. Completeness and season accuracy block adoption despite promising exploratory daily-error gains. Keep references and production unchanged. Next proposed step is saved-fit diagnosis of convergence and conditional-point/selection-target total bias; no automatic budget increases, amplitude searches, correction multipliers or broad validation fits. Independent derivatives/scaling checks and 104 tests pass. See [DAILY_PASSAGE_RESULTS.md](scripts/research/DAILY_PASSAGE_RESULTS.md).

**Complete saved daily-passage diagnosis without refitting (2026-10-12, user authorized).** Audit all 36 saved selected final checkpoints and five failed histories. Independent observed curvature agrees with finite differences (maximum relative discrepancy 2.58e-8). At failed historical Sparrowhawk, observed/scoring directional curvature is 1.9948 and linearized gradient contraction 0.99475, consistent with the saved slow full-step convergence; four failed inner endpoints have no saved coefficients, so their curvature remains unknown. On the 35 accepted contexts, joint shared-rate changes contribute −25.24 historical and −20.30 recent percentage points to hidden-count bias; daily deviations recover +11.60 and −2.77 points respectively. Retained counts already underpredict 8.13%/9.06% while the weighted intercept score is essentially zero. Ordinary/zero-day MAE improves, but peak MAE worsens and compensating nonpeak excess declines. A fixed-coefficient conditional Gaussian curvature proxy implies only 3.77%/7.26% hidden-support uplift in its current objective scale; it is not calibrated predictive integration or a correction. All original overall/weather total biases and reconstructed-season summaries reconcile. Keep the simple weather reference and production unchanged; no budget increases, new amplitudes, optimizer changes or corrected fills. Next specify a single count-balanced working-criterion control, with a matching no-state reference and separate total/dry/wet gates, before another broad screen. Earlier mean-only Poisson dry limitations remain relevant; no count-distribution or uncertainty claim follows. See [DAILY_PASSAGE_DIAGNOSIS.md](scripts/research/DAILY_PASSAGE_DIAGNOSIS.md).

**Reject count-balanced daily criterion as a reconstruction replacement (2026-10-12, user authorized).** Add optional power-1 working loss to the existing daily fitter, retaining power-1.5 default behavior and using an analytic directional-curvature scale for new power-1 scoring steps. Independent synthetic derivatives, curvature, sparse/dense solves, optimum, count-balance and legacy-path checks pass. Eight-context numerical pilot passes without hidden accuracy review. All forty ten-core contexts attempted; all 480 inner fits pass and every endpoint/prediction is saved. All forty selected daily final fits pass; one matching no-state recent Cormorant fold-2 fit fails gradient acceptance (0.001380), leaving 39 paired contexts with all ten historical species and 29 recent masks. No retries or larger budgets. Retained raw counts balance within 0.001 birds, but historical missing bias remains −22.98% and reconstructed-total error is 15.85% versus retained weather 15.83%, new no-state 15.32% and original 13.27%; every core species remains worse than original on totals. Historical dry MAE 33.40 → 31.80 versus original 31.52; early dry 24.45 → 20.26 versus original 21.52. Recent dry/wet remain protected against matching retained weather. Median completed final fit 0.195 seconds, paired ratio 1.13, selection plus final 2.96 seconds; median working DF 918. On 34 contexts shared with the previous daily screen, the new criterion worsens daily errors and historical absolute total error despite improved signed recent bias. Fixed penalties under changed curvature do not imply equal effective regularization. Completeness, overall historical dry and total-error gates fail. Keep power-1.5 weather research and original production references; no further power/penalty search or post-hoc multipliers. Next proposed step is a saved training-fold selection-target audit, without new fits or outer-target rule selection. All 104 tests pass; production unchanged. See [COUNT_BALANCED_PASSAGE.md](scripts/research/COUNT_BALANCED_PASSAGE.md).

**Wrap up daily conditional-passage branch after selection audit (2026-10-12, user requested closure).** Audit all 160 saved power-1 inner prediction settings across forty contexts, without refits or alternative outer scoring. Daily-MAE selection chooses positive SD in 38 contexts and worsens yearly recorded-total error against zero-state in all 38. All forty yearly-total minima choose SD zero; all 120 positive-SD settings lose yearly accuracy, with minimum loss 3.18 percentage points. Weekly-total selection offers local compromises but retains substantial yearly bias. Same-fold minima are optimistic diagnostics, not validated replacements, and historical/recent-task training samples overlap. Target-era summaries preserve the daily/annual conflict. Together with the completed numerical/bias diagnosis and both daily screens, this establishes a useful local temporal-prediction signal without acceptable reconstructed totals. Close the daily AR(1) conditional-state branch; no more amplitudes, penalties, weekly-selector trials, multipliers or budget changes. Keep hourly mean aggregation, intact surveys, weather and shared season/year terms in the simple research reference, and keep original production. A future abundance redesign must explicitly target expected missing-period totals; no new fitting experiment is scheduled. The five project goals still include historical partial-day conditioning, joint season uncertainty and independent confirmation. See [PASSAGE_SELECTION_WRAPUP.md](scripts/research/PASSAGE_SELECTION_WRAPUP.md).

**Controlled existing-ERA5 variable test (2026-10-12, requested by the user).** Review SoaringMeteo’s official guide and separately test antecedent 24-hour rain plus dry-hour interaction, and radiation plus low cloud, in the retained 51-coefficient interval-rate mean. Each adds only two coefficients; all forty ten-core contexts complete with unchanged masks, working criterion, smoothing selection and independent numerical gates. All 720 inner and 160 final fits pass, including eighty baseline replays; raw precision-loss flags remain recorded. Historical dry MAE improves 1.14%/1.31%, wet 0.99%/4.12%, recent wet 1.82%/3.53%. Recent dry remains protected, while Honey Buzzard drives much of the historical dry gain; excluding it diagnostically leaves only 0.24%/0.59% improvement. Radiation/cloud wet gains are stronger for Common Buzzard and Red Kite, with losses for some species including Honey Buzzard. Reconstructed-season error is 15.56%/15.75%, still above original 13.27%; every core species still trails original seasonal accuracy. Neither passes the three historical-original gates. Both remain fast at about 0.16 seconds median final fit. Preserve the positive weather evidence and experimental candidates, without universal adoption, automatic block combination or reopening the closed daily-state branch. The next proposed physical inputs are boundary-layer height and sensible heat flux; station rain remains a later comparison. All 104 tests pass and production is unchanged. See [ERA5_FEATURES.md](scripts/research/ERA5_FEATURES.md).

**Direct ERA5 soaring-variable follow-up (2026-10-12, user authorized the next small test).** Retrieve boundary-layer height and sensible heat flux at 46.0° N, 6.0° E through authenticated ECMWF ARCO point access, without exposing credentials or importing forecast code. Complete hourly 1993–2025 coverage and migration-season source/timing agreement with existing rain/radiation controls are verified. Compare log boundary-layer depth and signed upward heat flux as a 53-coefficient alternative, without stacking earlier weather blocks. All forty contexts complete; all 360 inner and eighty final numerical checks pass with forty saved-reference replays. Historical/recent wet MAE improve 3.41%/2.15% versus retained weather, while historical dry worsens 0.25% and recent dry is unchanged. Reconstructed-season error is 15.78% versus retained 15.83%, radiation/cloud 15.75% and original 13.27%; all three historical-original gates fail. Nine core species still trail original total accuracy; Grey Heron improves to 21.48% versus original 22.21% and retained weather 22.39%. All main point estimates trail radiation/cloud, with paired intervals overlapping zero. Median final fit is 0.155 seconds, paired ratio 1.045. Do not adopt or stack the lift pair and do not search more transformations/interactions on these reused masks. Preserve source data and positive wet evidence; radiation/cloud remains the stronger weather extension. Station rainfall is the next proposed input-quality check. All 104 tests pass; production remains unchanged. See [ERA5_LIFT.md](scripts/research/ERA5_LIFT.md).

### Weather model consolidation (12 October 2026)

At the user's request, stop experimentation and freeze one weather research candidate: the 53-coefficient hourly mean-rate model with current rain, wind, season, year, bounded UTC clock, night status, radiation and low cloud (`weather_soaring`). Select it for its main dry/wet point estimates and small size; retain rain history, direct lift and daily-state branches only as evidence. This is not a universal production replacement: historical dry MAE is 32.96 versus original 31.52, early dry 23.89 versus 21.52, and reconstructed-season error 15.75% versus 13.27%. Keep original production season totals and exports. Do not add automated weather/species switching or transfer old uncertainty/retained-adjustment results to this specification.

`MODEL_SPECIFICATION.md` is now the canonical choice, formula, evidence and limitations; the research README indexes the saved code/results and `GAP_FILL_PLAN.md` records the five goals' final status. Preserve previous README, specification and plan in `scripts/research/archive/`; leave scripts and ignored fitted evidence in place to preserve reproduction. Earlier proposed station/weather tests are superseded: no new fit or data acquisition is scheduled. Independent validation, heavy-rain truth, historical partial-day conditioning, joint predictive uncertainty and historical reconstruction remain unmet requirements, not an automatic continuation plan.

**Reject direct original-plus-rain replacement (2026-10-13, user requested hybrid).** Fit two fixed-unit-ridge, training-standardized passage-weighted daily rain coefficients jointly with every original GAM term, including episodes. Both arms complete all forty frozen contexts. Historical scores reproduce at displayed precision (the repeated strict replay check is flagged); fresh recent controls estimate a retained-only profile per fold, correcting the old research runner’s species-only profile cache. Historical dry MAE worsens 31.52 → 32.39, recent dry 47.88 → 51.20, and reconstructed-season error 13.27% → 13.59%; historical wet improves 24.31 → 18.53 and recent wet 44.85 → 28.43. Keep original production and the retained hourly radiation/cloud research candidate; do not add switching or another tuning grid. The hybrid is a daily approximation, not exact hourly integration. Preserve raw original-solver score diagnostics without claiming the hourly solver threshold or new uncertainty calibration. See [ORIGINAL_RAIN.md](scripts/research/ORIGINAL_RAIN.md).

**Hierarchical gap filling: production's GAM with daily weather and a daily AR(1) process (2026-10-13, requested by the user).** A separate research line (`scripts/hierarchical/`) keeps production's daily structure and adds one change at a time, scored on realistic masks drawn from a missingness audit (missing days follow rain and dark days; for soaring raptors, counting ends early when passage dies down). Every step is kept on season- and daily-total error with paired year bootstraps, no gates against production: daily rain, radiation/low cloud and wind (profile-weighted over the day, unit ridge), then a daily AR(1) process in place of the episode knots (τ by Laplace marginal likelihood). Realistic masks: season error 4.25% → 3.61%, daily MAE 23.4 → 17.5; production over-fills hidden wet days by 65%. Lockbox, scored once: daily MAE 29.2 → 26.6 (95% −3.9 to −1.2), season 8.49% → 8.23% (−0.71 to +0.10 points). Rejected or not needed: an early-end correction (with production's profile, learned from every day timed to the hour since 2014, early ends are unbiased; the research benchmark's 2022–2025-only profile under-filled them by a third); hourly weather in the time-of-day profile (no gain); an early-era rain effect (it gains only where the masks are blind to preferential sampling of counted wet days in 1993–2013). The earlier rejection of the production + rain hybrid came from calendar masks, which hide mostly dry days. The apparent interval over-coverage is discreteness; the upper tail is calibrated. Production is unchanged: adopting `D` (about 2 minutes a fit against 1.5 s, six τ) is the user's decision. See `scripts/hierarchical/RESULTS.md`.

**Hierarchical line reads the release directly; weather stops are zero passage there too (2026-10-13, decided by the user).** `survey_complete` decides a zero: `scripts/hierarchical/build_inputs.py` builds each core species' observations from `data/count/dataset/` (release built 2026-10-13), a weather stop being complete coverage with zero birds, flagged and left out of the time-of-day profile, as production does since 2026-10-09. The research's frozen inputs had left the stops out, so `D` filled rained-out days as gaps. Against them: birds identical (one Marsh Harrier more), about 42 stop days per species added, and the old release's eight overnight 2025 surveys (ending the next morning) gone. Rerun of `P` and `D` (`run_jobs.py`): realistic masks season error 3.58% (was 3.61%), daily MAE 17.2 (17.5); the rain effect strengthens (median −0.29 per sd, was −0.22) and hidden wet days, which were counted, are filled 15% low (was 6%). Lockbox: season 8.27% against production 8.48%, daily MAE 27.0 against 29.2.

**Weather terms for production and the Explore page: plan and first test (2026-10-13, decided by the user).** Aim: production's daily GAM with daily weather terms, no AR(1) process (`RSW`-like; `D`'s process gains nothing on season totals at ~40x the time), and a weather section on Explore. Interpretability first. Settled: the weather is self-contained (ERA5 from the Open-Meteo archive, `scripts/hierarchical/fetch_weather.py`, never the forecast repo); every term is in every taxon's model and the page shows only clear effects (no selection of terms, no per-taxon choice); wind enters as u and v at 100 m plus speed, shown as a preferred direction and speed; fronts are in (24-hour pressure change, temperature anomaly). Terms of `W`: rain, sunshine share, boundary-layer height, wind u/v, wind speed, pressure change, temperature anomaly (largest correlation: rain-sunshine -0.64). On the realistic masks `W` ties with `RSW` (season 3.54% vs 3.61%, daily MAE 17.4 vs 17.6; differences -0.13 to +0.02 points and -0.47 to +0.20) and with `D` (3.58%, 17.2) at 2.8 s a fit; against `P` -0.69 points and -5.8 birds. Effects on all counted days: rain lowers passage in all ten core species (x0.26-0.68 for 1 mm/h), sunshine raises it in eight (x1.4-3.4; Grey Heron the reverse), wind of any direction lowers it, the raptors favour a N-NE wind (bise), cold days raise Honey Buzzard (x1.46), pressure change shows nothing. Open: the display rule's era test (the early era's effects are weaker, which flags many as `caveat`), and how wind direction and speed are shown together. See `scripts/hierarchical/WEATHER_PLAN.md`.

**Weather broad panel: every species with a trend, a second menu, odd years find and even confirm (2026-10-13, requested by the user).** 72 species on production's daily frames (`scripts/hierarchical/weather_panel.py`, `weather_patterns.py`), grouped by family (`flight_groups.tsv`). The second menu (yesterday's rain, 24-hour temperature change, low cloud; `W2`) does not improve accuracy on the realistic masks (season 3.56% vs `W` 3.54%, daily MAE 17.6 vs 17.4, intervals across zero). Patterns that replicate: rain lowers passage in every group but the aerial insectivores; sunshine raises the soaring birds'; the preferred wind direction differs by group (soaring N-NE, passerines SE, aerial insectivores W) and is the most replicated term; a pressure rise raises passerines and aerial insectivores; yesterday's rain raises the soaring birds'. Low cloud and the temperature change mostly re-share other terms' effects. Proposed, not yet decided: production terms = `W` plus yesterday's rain. Details: `scripts/hierarchical/WEATHER_PLAN.md`.

**Production weather terms: `W3`, and the page section's display rule (2026-10-13, decided by the user).** The trend model's daily weather terms will be rain, yesterday's rain, sunshine, boundary-layer height, wind u, v and speed at 100 m, the 24-hour pressure change and the temperature anomaly (`W3` in `scripts/hierarchical/run_steps.py`), with production's episode block and no daily AR(1) process; low cloud and the 24-hour temperature change are left out. On the realistic masks `W3` scores season 3.53% and daily MAE 17.4 (production 4.23%, 23.2). Groups by family as in `scripts/hierarchical/flight_groups.tsv`. Display: an effect is shown when clear on all years and the same way in odd and even years, `caveat` when a half points the other way, hidden otherwise; wind as a rose of direction and speed together. Mock-up: `scripts/hierarchical/weather_mockup.py`. Next: production (trend, export block, defileViz contract).

**Weather in production: the trend GAM's `weather` terms and the species file's `weather` block (2026-10-13, decided by the user).** `trend.design` adds the `W3` terms (`defile_explore.weather.TERMS`) as a linear `weather` block with a unit prior before the episodes, read from the model frame (`trend.with_weather`: each day's profile-weighted mean, standardised on its counted days); the benchmark refits with them. `SMOOTH` leaves the weather out (the smooth curves are at the mean weather), and `episode_curves` exports it apart from the episodes (`trend.episodes.weather`, a log multiplier beside `episode`). The hourly ERA5 comes from the Open-Meteo archive (`weather.fetch`, called by `build_explore.py`, into `data/weather/`; the current year refetched up to yesterday) and enters the shared stage's cache key. Each trend is refitted on odd and on even years alone for the `weather` block (`weather@1`): per term, the effect for a fixed contrast with its 95% interval, `class` and `confirmed` (`reliability.weather_class`, `wind_class`: shown when clear, at least 10%, and the same way in both halves), the counted days in classes of the term and on the contrast's side against the opposite class (`counted`, a partial residual: birds over what the fit expects without that term, everything else kept, episodes included; the raw ratio had Chaffinch's wet days at x3.4 against the model's x0.44, since wet days fall in the October pulses), and the wind as a rose (5 m/s from each of eight sides against calm, its counted days against calm days; a side with fewer than 20 counted days hidden). `trend-gam@2`. defileViz draws it as a "Does the weather matter?" section on each species page: the shown effects with their counted days, the rose, one line for the terms with no clear link; the group summary of the mock-up is not on the page.

**The model's method page rewritten for the weather (2026-10-13, requested by the user).** defileViz's "The trend model" page groups eq. (3)'s terms by time scale (years, season, day to day) and gets a section "From day to day: weather and episodes" whose Figure 2 draws the smooth season, the same with the day's weather and with the episodes too, and each multiplier apart (hence `episode_curves`' `weather`). Filling the gaps says that a day is filled with its own weather. How to read the weather panel (contrasts, the counted days as partial residuals, the rose) is on "What the page shows" (`m-weather-read`), the display rule on "How reliable?" (`m-weather-classes`), as for the other panels. Quoted numbers from the build of 2026-10-13: 91 species tested on known seasons, median error 9% (5-15% between quartiles) against 17% dividing by coverage, median bias -3%, 80% intervals holding the truth 83% (median).

### Methods: date-specific coverage and cumulative illustrations

The documentation builds date-specific profile curves and five-minute counting slots from the shared cache only when its dataset build timestamp matches the Explore export. These inputs are documentation-only files; they do not change the public species schema or refit a model. The selected-day rectangle is centred on its date, and year/day controls support previous and next navigation.

The existing export retains passage-date summaries but not the 1,000 joint reconstruction paths. The phenology illustration therefore generates 1,000 conditional reconstructions with exported daily predictions fixed, displays 50 grey cumulative paths and conditional 80% bands for all three passage thresholds, and explicitly excludes coefficient uncertainty. Reported passage dates continue to come from the full production reconstruction; long-term timing uses the separate typical-season curve.

### Phenology: one annual-date result

The methods page now describes change in reconstructed annual 10%, 50% and 90% passage dates with equal-year linear fits and changes in days per decade. The separate typical-season timing comparison is removed. Current trend bands use 2,000 residual bootstrap samples of the exported annual date summaries; full joint reconstruction draws are not retained in the export, so reconstruction uncertainty is shown separately where available and is explicitly not propagated into those bands. Retaining the original joint passage-date draws remains necessary for that propagation.

### Shared annual-date phenology calculation

Phenology linear fits now live in `defile_explore.phenology` and are exported as `season.phenology` (`annual-date-linear@1`). The pipeline attaches this block after seasonal reconstruction, so it does not change or refit the daily model. Documentation panels, QA curves, defileViz timing curves and the timing-change headline read the same export. The legacy typical-season `trend.passage_q` field is retained for compatibility but is not a consumer fallback. The new fit inherits the season reliability class, with caveated overlaid trend lines hidden just as for the retired timing line. The residual-bootstrap limitation remains explicit; this does not implement joint reconstruction-draw propagation.

### Propagate joint reconstruction uncertainty into phenology (2026-10-28)

`annual-date-linear@2` supersedes the annual-summary residual bootstrap above. Retain all 1,000 joint 10%, 50% and 90% passage-date draws from production `fill_draws`, preserving the draw index across years. Fit an equal-year line separately in each joint reconstruction and add two residual resamples per draw for between-year regression uncertainty. The mean fitted line is the central result; the 2,000 resamples give 95% slope and trend intervals. The original date draws give annual 80% intervals for all three thresholds. This propagates reconstruction uncertainty without treating repeated draws as independent years. Documentation and defileViz consume this same exported result. The guide combines all three thresholds in one panel and removes its age/sex chapter; age/sex statistics and public displays remain available. The selected reconstructed-day comparison shows the original exported 80% total interval.

### One header for the Explore reports (2026-10-28)

The methods guide, QA index, species reports and comparison share `website/src/site-header.html` and `site-header.css`. Branding is “Défilé de l’Écluse” / “Explore”; each page has its own heading and `<page> · Explore · Défilé de l’Écluse` browser title. Keep the Python diagnostic renderer and Vue illustrated guide, with `scripts/build_site.py` assembling them in that order after the frontend build clears its output. defileViz replaces its method flowchart with a single illustrated-guide card, retaining the selected species in the link.

## Documentation and publication (2026-10-28)

The methods guide reuses defileViz's searchable SpeciesPicker component, including group filters and taxonomic sorting; instance IDs support the guide's two synchronised pickers. Keep the copies identical when changing picker behaviour. The QA index keeps display decisions and numerical inputs in expandable taxon rows; duplicate species reports are retired with redirects to the guide. Gap-transplant validation figures live in the guide, with the benchmark's fixed hyperparameters and median-versus-mean distinction stated explicitly. Species comparisons use the same annual-date phenology regressions as the guide and consumer site.

Figure roles are rust for observed counts/counting intervals, slate blue for reconstructed passage, grey for baseline references, black for reconstruction uncertainty, teal for weather and ochre for episodes. Year-level effects use brown to avoid presenting model effects as observations. Phenology thresholds retain sage (10%), plum (50%) and ochre (90%) in both phenology figures.

Publication retains the committed dataset snapshot copied into data/count/dataset. The newer sibling dataset working tree has an uncommitted build and changed release packaging; it is not silently substituted during this documentation release. The optional local reconciliation test compares sibling daily totals only when both builds have the same metadata timestamp; reconciliation against the pinned count.csv always runs.
