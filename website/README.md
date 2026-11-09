# Explore documentation

A continuous illustrated methods guide for the production Explore pipeline, using the same palette, system fonts and chart conventions as defile-website. The guide is English; figures read the existing JSON export. Species selectors in the first chapter and sidebar stay synchronised. The window figure aggregates comparable complete seasons by calendar date. Coverage distinguishes observed daily count, expected observed count and expected full-day passage; optional disclosures hold solar-time and numerical details. Weather panels derive response curves from exported coefficients and contrasts, without refitting. A year slider compares normalised seasonal shapes, while daily reconstruction combines count bars, 80% vertical interval lines and selectable day breakdowns. A separate worked example exposes the partial-day conditioning calculation. All component labels report cumulative in-sample deviance explained against the same fitted constant full-day-rate reference. The reconstruction detail contrasts observed coverage, the daily prediction and the exported reconstructed mean with its interval. The QA decision table and species comparison remain Python-generated pages. Recording and data-cleaning details remain in defile-dataset.

## Build and preview

From the repository root, with `data/explore/` already built:

```bash
npm ci --prefix website
uv run python scripts/build_site.py
uv run python -m http.server 4174 --bind 127.0.0.1 --directory logs/site
```

Open `http://127.0.0.1:4174/`. The homepage, all QA pages, comparison, copied export and legacy redirects are in `logs/site/`. The normal publication script uploads this directory as `viewer.zip`; its existing full-export provenance checks still apply. Build the site again after committing before publishing. Deploy the Explore documentation before deploying the defile-website changes so its new links have a destination.

For interactive frontend editing:

```bash
npm run dev --prefix website
```

This copies `data/explore/` to ignored `website/public/data/explore/` before serving. QA pages are available through the assembled preview above. To refresh just the diagnostic pages, run `uv run python scripts/explore_viewer.py`.

To edit the guide's prose in the rendered page, open it on the dev server with `?edit` added to the
URL (`http://127.0.0.1:5173/?edit`). Text blocks become editable (formulas, links and live readouts
stay fixed), and each edited block is saved within a second to ignored `logs/guide-edits.json` with
its original and edited text, maths as TeX between ⟨ ⟩. Edits come back on reload. The `.vue`
templates are not written: carry the edits into them, then empty the file. Review notes in
ignored `logs/guide-notes.json` (`id`, `section`: an element id, `find`: words of the passage the note
follows, `topic`, `note`, `reply`) show under their passage in edit mode, each with a reply box saved
to the same file.

## Sources

- `src/App.vue`: chapter introductions, contents, species selection and provenance.
- `src/components/explore/methods/`: illustrated explanations moved from defile-website, including the existing local edits to the counting section.
- `src/components/explore/`: interactive model widgets and KaTeX equations.
- `src/theme.css`, `src/theme.js`: palette and typography matching defile-website; retain rust for counts and slate blue for estimates.
- `src/site.css`, `src/method.css`: reading layout and figure styles.
- `src/site-header.html`, `src/site-header.css`: the single header template and its responsive styles, imported by Vue and read by Python. `__ROOT__` becomes `./` in the guide and `../` in QA; each renderer marks the active navigation item. Edit these files once for all report pages.
- `public/qa.css`: report-specific styles, inlined with the theme and shared header styles by the Python viewer.
- `../scripts/build_site.py`: assemble the frontend, QA, comparison and legacy redirects.

Methods describe production code in `src/defile_passage/`, not experimental models under `scripts/research/`. Update the relevant explanation when a method changes. The model-fitting subsection explains the implementation; the README documents the export blocks. The dataset manifest identifies the actual observations and code behind the examples; historical benchmark summaries are not hardcoded.

## Links and checks

`?species=<taxon_id>#coverage-m-profile` selects a taxon and opens a section. Chapter IDs are `counts`, `model`, `reconstruction`, `phenology` and `reliability`. `coverage` is now a subsection of the daily count model; subsection IDs are prefixed by the chapter to avoid collisions. Keep these anchors stable: defile-website's `src/services/methods.js` constructs links to them. Species without a fitted model keep their coverage and empirical phenology examples, with explanatory notes where model outputs are unavailable. Existing coverage, filling and passage-date subsection anchors remain valid in their new locations. Retired totals and interpretation anchors redirect to the model or reconstruction chapter. The separate totals chapter and reading appendix are removed. Validation includes a gap-transplant figure in the methods guide and links to the species’ expandable row in the QA table. The main content is data and effort, the daily count model, within-day reconstruction, phenology and QA.

```bash
npm run lint --prefix website
npm run format:check --prefix website
uv run pytest
pre-commit run --all-files
```

## How the HTML report is produced

Use `scripts/build_site.py` as the single entry point. It runs these steps in order:

1. `export_method_data.py` extracts date-specific profiles and counting slots from the cache matching the export’s dataset timestamp into `website/public/data/methods/`. Without a matching cache, these optional illustrations are unavailable; the build prints that explicitly.
2. `npm run build` copies the existing export, then Vite replaces `logs/site/` with the compiled methods guide and static assets. Running this step alone removes the old QA pages too.
3. `explore_viewer.py` writes `qa/index.html`, historical taxon redirects and `qa/compare.html`. Both Python generators use `explore_viewer.wrap` for the shared header, page title, theme. Provenance is retained in downloadable manifests rather than a page banner.
4. The assembler adds redirects for historical root-level species/comparison links, preserving query strings and fragments, then writes `site-manifest.json` with the export provenance and site revision.

All pages use the brand “Défilé de l’Écluse”, the subtitle “Explore”, and page names “Methods guide”, “Quality assurance”, “Species comparison”, or the species name. Browser titles follow `<page> · Explore · Défilé de l’Écluse`. The report header returns to the public website at `/defile/#explore`.

Edit explanations in Vue, QA decisions in Python and common navigation in the shared template. Never edit `logs/site/` by hand. A complete site rebuild is needed after changing a shared header or stylesheet; the quick QA command refreshes only the Python pages. Neither command fits models or updates `data/explore/`. The Python plots load Plotly from a version-pinned CDN, so their interactive figures require an internet connection.

The searchable SpeciesPicker.vue is copied verbatim from defile-website, with instance IDs for the sidebar and main selector. Keep component behaviour identical in both repositories and synchronise the English picker messages.
