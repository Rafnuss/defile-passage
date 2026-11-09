# AGENTS.md

Guidance for AI coding agents working in this repo.

## What this project does

Computes the statistics behind defile-website's Explore page from the defile-dataset release: a JSON
file per taxon (daily counts, effort, time-of-day profile, GAM trend and gap-filled totals, ...)
plus `taxa.json`, `effort.json` and `manifest.json`. `README.md` has the layout
and the commands.

Principles:

- **The counts are always shown.** Every panel draws the birds counted, or marks which days were
  counted; what comes from a model (the trend GAM, the time-of-day GAM) is labelled as such.
- **One complete series per taxon.** For a taxon with a trend, the numbers come from its fit: the
  trend GAM's gap-filled days (`fill_draws`) make the season totals, the season block's shares,
  passage dates and chances, each with its uncertainty from the draws (`season.source: gam`).
  Without a trend, or where the trend's totals are hidden (`reliability.fills_season`), the season
  is from the counts (`count / c`, interpolated across gaps). Nothing refits a model to draw a
  panel.
- **Effort is explicit.** A count is read with its coverage `c` (the share of the day's expected
  passage counted). No ratio `count / c` below `COVERAGE_MIN`, nothing adjusted before a taxon's
  start year.

## Independence from the forecast

defile-migration-forecast and this repo share no code and import nothing from each other.
`release.py` and `timeofday.py` are copies of forecast code (origin in their docstrings). Never
add a dependency on the forecast repo or a shared package; carrying a change across is a decision
for the user, logged in the table in `DECISIONS.md` -> Repository.

## The output is a contract with defile-website

defile-website (`src/services/explore.js`, `src/components/explore/`) reads `taxa.json` (names,
`tier`, and the picker's `taxon_order`, `group`, `season_birds`, `story`, `highlight` from
`catalogue.py`),
`effort.json` (`annual`) and `species/<taxon_id>.json`: `trend` (`annual`, `passage_q`, `season`,
`episodes` (`base`, `weather`, `episode`), `window`, `theta`, `kappa`, `first_year`, `last_year`, `days`: every window day
gap-filled, drawn by the year panel), `season` (`source`, `share`, `count`, `c`, `passage` with
`q50_lo`/`q50_hi`, `chances`), `weather` (`effects` with `class`, `confirmed`, `counted`; `wind`
with its `rose`), `daytime` (`hours` over the main passage beside `expected`, the
profile's prediction for the same days and minutes),
`key_numbers`, `reliability`, `benchmark` (`gap`, `gap_trials`), `records`, `accounts`, `age`,
`sex`, `window`, `settings.start_year`, `links`, `profile` (`day`: the curve the coverage figure of the method page draws), `annual` and `days`. Only
`diagnostics` is not read. Renaming or reshaping a field breaks the page: change both repos
together. `scripts/explore_viewer.py` draws every block and is where a block is checked first.
Each block names its `method` (`name@version`): bump the version when what the block means
changes. Hours of the day are solar time (`export.solar_shift`); defile-website converts them to the
clock with the same formula (`solarShift`). The files are strict JSON (`export.dumps`: no NaN).

The passage tables (`data/passage/`, `passage.py`) are a second contract, with the Zenodo record
and the data paper. They are read from the species files, never from a model of their own: a column
renamed or changed in meaning bumps `passage.METHOD`.

`reliability` classes each trend claim (`totals`, `trend`, `season`) as `show`, `caveat` or `hide`
with reason codes, and `elements` gives each drawn field resting on a claim its class
(`reliability.ELEMENTS`). The rule and its thresholds live in `reliability.py`; defile-website only
looks fields up in `elements` and words the reasons. Change a threshold here, never add a filter of its own there.

## Written accounts

`content/accounts/` is authored text, not generated: edit `species-sections.tsv` and
`year-accounts.tsv` (both languages together), never write or translate prose automatically, and
follow its README. The build reads only those two files (`accounts.py` checks them: unique keys,
known sections and taxa, both languages); the report and paper extracts in the release are the
editors' sources, not the build's.

## Per-taxon settings

Every setting has a rule (`settings.py`). Fix a wrong value by improving the rule when it can be
done for all taxa; otherwise add an exception to `src/defile_passage/overrides.yaml`, with a
`reason`. Never special-case a taxon in code.

## Conventions

- Fixed values are module-level `UPPER_SNAKE_CASE` constants, defined once in the module that owns
  the concept and imported elsewhere. Grep before writing a literal.
- `DECISIONS.md` is the log of settled calls and of what was tried and rejected: read it before
  re-proposing something, and add to it when a question is settled. `DEVELOPMENT.md` holds only
  what is open.
- Before treating a change as done: `uv run pytest` and `pre-commit run --all-files` (black and
  isort at line length 99, docformatter, mdformat, codespell).
- `data/` and `logs/` are generated: never commit them. The counts are a defile-dataset release:
  `scripts/build_explore.py --dataset vYYYY.N` downloads its `dataset.zip` into
  `data/count/dataset/` (`release.fetch_dataset`); a local dataset folder (committed code) can
  go to the rolling `dev` preview only.
- The build runs locally, never in CI (30-40 min on a runner): `scripts/publish_explore.py`
  uploads the export, the passage tables and the viewer to a release, from which Pages and
  defile-website deploy and the passage tables go to Zenodo. It refuses a build from uncommitted code
  and a versioned release from a dataset that is not a release; never loosen those checks.
- Builds are verbose (pygam warnings, per-taxon progress): redirect to `logs/` and grep.
- `data/cache/` holds the shared stage and each taxon's trend fit, keyed by the release and by
  the source code of the modules that made them, so a code change invalidates them by itself.
  `--no-cache` ignores them; deleting the folder is always safe.

## Environment gotcha

This repo sits in a OneDrive-synced folder. A cloud-only placeholder can make a read hang at 0%
CPU or fail with "Resource deadlock avoided"; if a build or `uv run` stalls, suspect that first
and ask the user to make the folder available offline.
