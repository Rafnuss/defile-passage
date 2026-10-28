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
        Six decades of observations, changing counting effort, and the statistical methods that
        connect them. Follow each step, try the illustrations, and inspect the evidence.
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
                We first select comparable species, years and dates using daily bird counts and
                counting intervals from
                <a href="https://github.com/Rafnuss/defile-dataset">defile-dataset</a>, which
                documents their preparation and recording conventions.
              </p>
              <p v-else>{{ chapter.intro }}</p>
            </header>
            <component
              :is="chapter.component"
              :key="data.taxon_id"
              :name="name"
              :data="data"
              :effort="effort"
              v-bind="chapter.id === 'counts' ? { surveyDays, lastCompleteYear } : {}"
            >
              <template #species>
                <p>
                  Taxa are selected for the full analysis if they have at least
                  <strong>{{ manifest.tiers.full_min_days }} recorded days</strong>, spread over at
                  least <strong>{{ manifest.tiers.full_min_years }} years</strong>.
                </p>
                <p>
                  Subspecies are rolled up to species level. Higher-level taxa (“sp.” groups and
                  slash taxa) are modelled separately when no single component contributes more than
                  <strong>90%</strong> of the birds recorded; groups must contain 2–100 descendant
                  taxa. See the
                  <a href="https://raphaelnussbaumer.com/defile-dataset/"
                    >defile-dataset taxonomic hierarchy</a
                  >
                  for the detailed tree.
                </p>
                <p>
                  Choose any of the taxa below to use its data throughout this report. The same
                  selection is available in the left menu.
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
        </template>
      </article>
    </div>
  </main>
  <footer class="site-footer">
    <span>Défilé Explore · Methods & quality assurance</span
    ><a href="https://github.com/Rafnuss/defile-explore">Source code ↗</a
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
      "We first link counting intervals to coverage, then describe count variability and fit expected full-day passage using the year, date and weather.",
    technical:
      "The profile determines coverage c. The daily model is fitted to counts with log(c) as an offset. The trend block records the fitted summaries and dispersion parameters.",
    modules: ["profile", "timeofday", "trend", "weather"],
  },
  {
    id: "reconstruction",
    label: "Predict",
    title: "Reconstructing full days",
    component: MethodReconstruction,
    intro:
      "Using the fitted daily model, we first distinguish uncounted, fully counted and partly counted days, then estimate missing birds and inspect the full-day totals.",
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
      "We first accumulate daily passage to find each season’s 10%, 50% and 90% passage dates, then quantify changes in those annual passage dates.",
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
      "We assess reconstruction accuracy and interval calibration, then use the results to decide which estimates can be displayed.",
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
const surveyDays = ref(null);
const lastCompleteYear = computed(() =>
  manifest.value
    ? Number(manifest.value.last_date.slice(0, 4)) - manifest.value.partial_years.length
    : null,
);
const active = ref("counts");
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
    surveyDays.value = surveys.days;
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
