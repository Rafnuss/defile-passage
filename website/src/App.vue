<template>
  <a class="skip-link" href="#main">Skip to content</a>
  <!-- Only repository-owned static HTML is inserted; no export or user text enters this template. -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="site-shell" v-html="siteHeader"></div>

  <main id="main" class="site-main">
    <div class="hero">
      <p class="eyebrow">From birds counted to migration understood</p>
      <h1>Methods guide</h1>
      <p class="lead">
        <strong>Context.</strong> Since 1966, migrating birds have been counted every autumn at the
        Défilé de l’Écluse, with a focus on large soaring birds. These counts are valuable data on
        long-term change in populations and in the timing of migration, but counts cover only part
        of each day, and fewer days in the early years, which limits comparisons between years.
        <strong>Method.</strong> We propose a method to make them comparable. First, for each
        species, we model the full-day passage from the daily counts, accounting for the part of the
        day counted, a long-term trend, a level for each year, a seasonal curve that can shift over
        the years, the day’s weather and short multi-day episodes. Second, the fitted model
        estimates the birds of every uncounted hour and day, with their uncertainty, from which come
        season totals, passage dates and their trends. <strong>Results.</strong> Tested on counts
        hidden from the fit, the reconstructed season totals are typically within 8% of the birds
        counted. The reconstructed dataset can be used to study long-term change in the numbers and
        timing of migrants.
      </p>
    </div>

    <div class="reading-layout">
      <aside class="contents" aria-label="On this page">
        <p class="eyebrow">On this page</p>
        <ol>
          <li v-for="(chapter, i) in chapters" :key="chapter.id">
            <a
              :href="`#${chapter.id}`"
              :aria-current="active === chapter.id ? 'location' : undefined"
              ><span>{{ String(i + 1).padStart(2, "0") }}</span
              >{{ chapter.title }}</a
            >
          </li>
        </ol>
        <div class="example-control sidebar-species">
          <label for="species-sidebar">Species</label>
          <SpeciesPicker
            id="species-sidebar"
            v-model="selected"
            :taxa="taxa"
            @update:model-value="selectSpecies"
          />
        </div>
      </aside>

      <article class="method">
        <div v-if="error" class="callout callout-warning" role="alert">
          {{ error }}
          <button class="btn btn-sm btn-outline-secondary" @click="load">Try again</button>
        </div>
        <p v-else-if="!data" role="status">Loading the illustrated examples…</p>
        <p v-if="loading && data" class="visually-hidden" role="status">
          Updating species figures…
        </p>
        <template v-if="data">
          <section v-for="chapter in chapters" :id="chapter.id" :key="chapter.id" class="chapter">
            <header class="chapter-head">
              <h2>{{ chapter.title }}</h2>
              <p v-if="chapter.id === 'counts'">
                The model is built for a subset of species, each with its own range of years and the
                same range of dates within the year, so that its estimates rest on enough counts.
                The raw dataset is available on
                <a href="https://github.com/Rafnuss/defile-dataset">defile-dataset</a>, which
                documents its preparation.
              </p>
              <p v-else>{{ chapter.intro }}</p>
            </header>
            <component
              :is="chapter.component"
              :key="data.taxon_id"
              :name="name"
              :data="data"
              :effort="effort"
              v-bind="chapter.id === 'counts' ? { lastCompleteYear } : {}"
            >
              <template #species>
                <p>
                  Taxa are selected if they have at least
                  <strong>{{ manifest.tiers.full_min_days }} recorded days</strong>, spread over at
                  least <strong>{{ manifest.tiers.full_min_years }} years</strong>. This results in
                  <strong>{{ taxonCounts.species }} species</strong> and
                  {{ taxonCounts.groups }} groups.
                </p>
                <p>
                  Subspecies are rolled up to species level. Higher-level taxa (“sp.” groups and
                  slash taxa) are also modelled, but only if no single taxon contributes more than
                  <strong>90%</strong> of the birds recorded. See the
                  <a href="https://raphaelnussbaumer.com/defile-dataset/"
                    >defile-dataset taxonomic hierarchy</a
                  >
                  for the detailed tree.
                </p>
                <p>
                  This report illustrates the model’s results for one species, which can be selected
                  here or in the left menu:
                </p>
                <div class="example-control main-species">
                  <label for="species">Example species</label>
                  <SpeciesPicker
                    id="species"
                    v-model="selected"
                    :taxa="taxa"
                    @update:model-value="selectSpecies"
                  />
                </div>
              </template>
            </component>
          </section>
          <MethodSymbols />
        </template>
      </article>
    </div>
  </main>
  <footer class="site-footer">
    <span>Défilé Explore · Methods & quality assurance</span
    ><a href="https://github.com/Rafnuss/defile-passage">Source code ↗</a
    ><a href="#main">Back to top ↑</a>
  </footer>
</template>

<script setup>
import headerTemplate from "./site-header.html?raw";

// The same static template is rendered by explore_viewer.wrap for the QA pages.
const siteHeader = headerTemplate
  .replaceAll("__ROOT__", "./")
  .replace('data-page="methods"', 'data-page="methods" aria-current="page"');
import { computed, ref, nextTick, onMounted, onBeforeUnmount } from "vue";
import SpeciesPicker from "./components/explore/SpeciesPicker.vue";
import MethodCounts from "./components/explore/methods/MethodCounts.vue";
import MethodModel from "./components/explore/methods/MethodModel.vue";
import MethodReconstruction from "./components/explore/methods/MethodReconstruction.vue";
import MethodPhenology from "./components/explore/methods/MethodPhenology.vue";
import MethodReliability from "./components/explore/methods/MethodReliability.vue";
import MethodSymbols from "./components/explore/methods/MethodSymbols.vue";

const chapters = [
  {
    id: "counts",
    label: "Observe",
    title: "Data: counts and effort",
    component: MethodCounts,
    intro:
      "Choose comparable species, years and dates, then distinguish the daily counts used by the model from the timed observations used to describe counting effort.",
    technical:
      "Start years and windows are taxon settings. Daily counts, settings and window are exported in species/<taxon_id>.json; survey intervals and annual effort are in effort.json.",
    modules: ["release", "export", "settings", "window"],
  },
  {
    id: "model",
    label: "Fit",
    title: "Daily count model",
    component: MethodModel,
    intro:
      "We model the number of birds counted on a day as a function of the year, the date and the weather. The model explicitly accounts for the part of the day counted, the flocking of birds and short runs of busy or quiet days.",
    technical:
      "The profile determines coverage c. The daily model is fitted to counts with log(c) as an offset. The trend block records the fitted summaries and dispersion parameters.",
    modules: ["profile", "timeofday", "trend", "weather"],
  },
  {
    id: "reconstruction",
    label: "Predict",
    title: "Reconstructing daily totals",
    component: MethodReconstruction,
    intro:
      "Each day's total is the birds counted plus an estimate of the birds missed, with its uncertainty: from the fitted model, updated by the counted hours where there are some.",
    technical:
      "trend.fill_draws produces 1 000 joint draws. trend.days exports full-day means and 80% intervals; season.source identifies the reconstructed series or the count/coverage fallback.",
    modules: ["trend", "season", "reliability"],
  },
  {
    id: "phenology",
    label: "Time",
    title: "Phenology and its trend",
    component: MethodPhenology,
    intro:
      "Passage dates are read from each reconstructed season, and their change over the years is a regression repeated across the 1 000 reconstructions.",
    technical:
      "season.phenology fits annual passage dates separately in each of the 1 000 joint reconstructions, preserving dependence across years. Its 95% trend bands combine reconstruction uncertainty and residual resampling across years.",
    modules: ["season", "trend"],
  },
  {
    id: "reliability",
    label: "Check",
    title: "Validation and QA",
    component: MethodReliability,
    intro:
      "Two questions: can the model recover counts it did not see, and when is a result shown, shown with a caveat or hidden?",
    technical:
      "benchmark records gap-transplant trials. reliability classes totals, abundance trend and timing separately, and reliability.elements supplies the display rules.",
    modules: ["benchmark", "reliability"],
  },
];
const taxa = ref([]),
  selected = ref(new URL(location.href).searchParams.get("species") || "");
const data = ref(null),
  effort = ref(null),
  manifest = ref(null),
  error = ref(null),
  loading = ref(false);
const lastCompleteYear = computed(() =>
  manifest.value
    ? Number(manifest.value.last_date.slice(0, 4)) - manifest.value.partial_years.length
    : null,
);
const active = ref("counts");
const taxonCounts = computed(() => {
  const species = taxa.value.filter((tx) => tx.taxon_rank === "species").length;
  return { species, groups: taxa.value.length - species };
});
const name = computed(
  () =>
    taxa.value.find((tx) => tx.taxon_id === data.value?.taxon_id)?.english_name ||
    taxa.value.find((tx) => tx.taxon_id === selected.value)?.english_name,
);
let request = 0,
  observer;
async function json(path) {
  const response = await fetch(new URL(`data/explore/${path}`, document.baseURI));
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status}).`);
  return response.json();
}
async function selectSpecies() {
  const current = ++request;
  loading.value = true;
  error.value = null;
  try {
    const result = await json(`species/${selected.value}.json`);
    if (current !== request) return;
    data.value = result;
    const url = new URL(location.href);
    url.searchParams.set("species", selected.value);
    history.replaceState(null, "", url);
    await nextTick();
    observeChapters();
  } catch (e) {
    if (current === request)
      error.value = `${e.message} Run the documentation data preparation step or try reloading.`;
  } finally {
    if (current === request) loading.value = false;
  }
}
function observeChapters() {
  observer?.disconnect();
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) if (entry.isIntersecting) active.value = entry.target.id;
    },
    { rootMargin: "-15% 0px -65% 0px" },
  );
  document.querySelectorAll(".chapter").forEach((el) => observer.observe(el));
}
function scrollToHash() {
  const requested = decodeURIComponent(location.hash.slice(1));
  const section = requested.startsWith("totals")
    ? "model"
    : requested.startsWith("shown")
      ? "reconstruction"
      : requested;
  const target =
    document.getElementById(requested) ||
    document.getElementById(section) ||
    document.getElementById(section.split("-m-")[0]);
  if (!target) return;
  let parent = target.closest("details");
  if (target.id === "shown") parent = target.querySelector("details");
  if (parent) parent.open = true;
  target.scrollIntoView();
}

async function load() {
  error.value = null;
  try {
    const [catalogue, surveys, build] = await Promise.all([
      json("taxa.json"),
      json("effort.json"),
      json("manifest.json"),
    ]);
    taxa.value = catalogue
      .filter((tx) => tx.tier === "full")
      .sort((a, b) => a.english_name.localeCompare(b.english_name));
    effort.value = surveys.annual;
    manifest.value = build;
    selected.value =
      taxa.value.find((tx) => tx.taxon_id === selected.value || tx.ebird_code === selected.value)
        ?.taxon_id || taxa.value.find((tx) => tx.english_name === "Red Kite").taxon_id;
    await selectSpecies();
    await nextTick();
    scrollToHash();
  } catch (e) {
    error.value = e.message;
  }
}
onMounted(() => {
  load();
  window.addEventListener("hashchange", scrollToHash);
});
onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener("hashchange", scrollToHash);
});
</script>
