<template>
  <div ref="root" class="picker" @keydown="onKey">
    <div class="picker-field" :class="{ open }">
      <i class="bi bi-search picker-icon"></i>
      <input
        :id="id"
        ref="input"
        v-model="query"
        type="text"
        class="picker-input"
        role="combobox"
        autocomplete="off"
        :aria-expanded="open"
        :aria-controls="`${id}-list`"
        :aria-label="$t('explore.picker.label')"
        :placeholder="selectedName"
        @focus="openList"
        @click="openList"
      />
      <span v-if="!open && !query" class="picker-current" @click="focus">{{ selectedName }}</span>
      <i class="bi bi-chevron-down picker-caret" @click="toggle"></i>
    </div>

    <div v-if="open" class="picker-panel shadow">
      <div class="picker-tools">
        <div class="d-flex flex-wrap gap-1">
          <button
            v-for="f in filters"
            :key="f.key"
            type="button"
            class="btn btn-sm chip"
            :class="f.key === filter && !query ? 'btn-primary' : 'btn-outline-secondary'"
            @mousedown.prevent="setFilter(f.key)"
          >
            {{ f.label }} <span class="chip-n">{{ f.n }}</span>
          </button>
        </div>
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1">
          <span class="small text-muted me-auto">
            <template v-if="query">{{
              $t("explore.picker.searchAll", { n: list.length })
            }}</template>
            <template v-else>{{ filterHelp }}</template>
          </span>
          <div class="form-check form-switch small mb-0" :title="$t('explore.picker.groupsHelp')">
            <input
              :id="`${id}-groups`"
              v-model="showGroups"
              class="form-check-input"
              type="checkbox"
              role="switch"
              @mousedown.prevent
            />
            <label class="form-check-label" :for="`${id}-groups`" @mousedown.prevent>
              {{ $t("explore.picker.groups") }}
            </label>
          </div>
          <div class="btn-group btn-group-sm" role="group">
            <button
              v-for="s in SORTS"
              :key="s"
              type="button"
              class="btn btn-outline-secondary py-0"
              :class="{ active: sort === s }"
              @mousedown.prevent="sort = s"
            >
              {{ $t(`explore.picker.sort.${s}`) }}
            </button>
          </div>
        </div>
      </div>
      <ul :id="`${id}-list`" ref="listEl" class="picker-list" role="listbox">
        <li
          v-for="(tx, i) in list"
          :key="tx.taxon_id"
          role="option"
          :aria-selected="tx.taxon_id === modelValue"
          :class="{ active: i === cursor, selected: tx.taxon_id === modelValue }"
          @mousedown.prevent="choose(tx)"
          @mousemove="cursor = i"
        >
          <span class="story" :class="`story-${tx.story}`" :title="storyLabel(tx.story)"></span>
          <span class="flex-grow-1 text-truncate">
            {{ taxonName(tx, locale) }}
            <span class="sci">{{ tx.scientific_name }}</span>
          </span>
          <span v-if="isGroup(tx)" class="group-tag" :title="$t('explore.picker.groupsHelp')">{{
            $t("explore.picker.groupOf", { n: tx.members.length - 1 })
          }}</span>
          <span class="birds" :title="$t('explore.picker.birdsTitle')">{{ birds(tx) }}</span>
        </li>
        <li v-if="!list.length" class="empty text-muted small">
          {{ $t("explore.picker.none") }}
        </li>
      </ul>
      <div class="picker-legend small text-muted">
        <span v-for="s in STORIES" :key="s" class="me-3 text-nowrap"
          ><span class="story" :class="`story-${s}`"></span>{{ storyLabel(s) }}</span
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import { taxonName, isGroup } from "../../services/explore";

const { t, locale } = useI18n();

const props = defineProps({
  // taxa.json entries with a page (the full tier)
  id: { type: String, default: "exploreTaxon" },
  taxa: { type: Array, required: true },
  modelValue: { type: String, default: null },
});
const emit = defineEmits(["update:modelValue"]);

// The picker's filters: the highlights (defile-explore `catalogue.highlight`), the groups
// (`catalogue.group`), and everything
const FILTERS = ["highlight", "raptors", "waterbirds", "passerines", "other", "all"];
const SORTS = ["taxonomic", "common"];
const STORIES = ["full", "caveat", "counts"];

const root = ref(null);
const input = ref(null);
const listEl = ref(null);
const open = ref(false);
const query = ref("");
const filter = ref("highlight");
const sort = ref("taxonomic");
const cursor = ref(0);
// Groups ("harrier sp.", "Red/Black Kite") are hidden unless asked for; remembered per viewer
const GROUPS_KEY = "explore.showGroups";
const showGroups = ref(false);
try {
  showGroups.value = localStorage.getItem(GROUPS_KEY) === "1";
} catch {
  /* storage unavailable: groups stay hidden */
}
watch(showGroups, (on) => {
  try {
    localStorage.setItem(GROUPS_KEY, on ? "1" : "0");
  } catch {
    /* not remembered */
  }
});
const pool = computed(() => props.taxa.filter((tx) => showGroups.value || !isGroup(tx)));

const inFilter = (tx, f) =>
  f === "all" ? true : f === "highlight" ? tx.highlight : tx.group === f;
const filters = computed(() =>
  FILTERS.map((key) => ({
    key,
    label: t(`explore.picker.filter.${key}`),
    n: pool.value.filter((tx) => inFilter(tx, key)).length,
  })).filter((f) => f.n > 0),
);
const filterHelp = computed(() => t(`explore.picker.help.${filter.value}`));

// Accents and case ignored, in both names and the scientific one
const fold = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const list = computed(() => {
  const q = fold(query.value.trim());
  const rows = q
    ? pool.value.filter((tx) =>
        [tx.english_name, tx.french_name, tx.scientific_name].some((n) => fold(n).includes(q)),
      )
    : pool.value.filter((tx) => inFilter(tx, filter.value));
  return [...rows].sort((a, b) =>
    sort.value === "common"
      ? (b.season_birds ?? 0) - (a.season_birds ?? 0)
      : (a.taxon_order ?? Infinity) - (b.taxon_order ?? Infinity),
  );
});
const selected = computed(() => props.taxa.find((tx) => tx.taxon_id === props.modelValue));
const selectedName = computed(() =>
  selected.value ? taxonName(selected.value, locale.value) : "",
);

const storyLabel = (s) => t(`explore.picker.story.${s}`);
const birds = (tx) => {
  const n = tx.season_birds ?? 0;
  if (n >= 1000) return `${Math.round(n / 1000).toLocaleString(locale.value)}k`;
  return Math.round(n).toLocaleString(locale.value);
};

function openList() {
  if (open.value) return;
  open.value = true;
  if (selected.value && isGroup(selected.value)) showGroups.value = true;
  // Open on the filter holding the species shown
  if (selected.value && !inFilter(selected.value, filter.value)) filter.value = "all";
  nextTick(() => {
    cursor.value = Math.max(
      0,
      list.value.findIndex((tx) => tx.taxon_id === props.modelValue),
    );
    scrollToCursor();
  });
}
function close() {
  open.value = false;
  query.value = "";
}
const focus = () => input.value?.focus();
function toggle() {
  if (open.value) close();
  else focus();
}
function setFilter(key) {
  filter.value = key;
  query.value = "";
  cursor.value = 0;
}
function choose(tx) {
  emit("update:modelValue", tx.taxon_id);
  close();
  input.value?.blur();
}
function scrollToCursor() {
  nextTick(() => listEl.value?.children[cursor.value]?.scrollIntoView({ block: "nearest" }));
}
function onKey(e) {
  if (!open.value) {
    if (e.key === "ArrowDown" || e.key === "Enter") openList();
    return;
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const n = list.value.length;
    if (!n) return;
    cursor.value = (cursor.value + (e.key === "ArrowDown" ? 1 : n - 1)) % n;
    scrollToCursor();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (list.value[cursor.value]) choose(list.value[cursor.value]);
  } else if (e.key === "Escape") {
    close();
    input.value?.blur();
  }
}
watch(query, () => (cursor.value = 0));

const onOutside = (e) => {
  if (open.value && root.value && !root.value.contains(e.target)) close();
};
onMounted(() => document.addEventListener("pointerdown", onOutside));
onBeforeUnmount(() => document.removeEventListener("pointerdown", onOutside));
</script>

<style scoped>
.picker {
  position: relative;
}
.picker-field {
  position: relative;
  display: flex;
  align-items: center;
  border: 1px solid var(--bs-border-color);
  border-radius: 0.5rem;
  background: var(--bs-body-bg);
  padding: 0.25rem 0.5rem;
}
.picker-field.open,
.picker-field:focus-within {
  border-color: var(--bs-primary);
  box-shadow: 0 0 0 0.2rem rgba(var(--bs-primary-rgb), 0.15);
}
.picker-icon {
  color: var(--bs-secondary-color);
  margin-right: 0.4rem;
}
.picker-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--bs-body-color);
}
.picker-input::placeholder {
  color: var(--bs-secondary-color);
  font-weight: 400;
}
/* The species shown, over the empty input while the list is closed */
.picker-current {
  position: absolute;
  left: 2rem;
  right: 2rem;
  font-size: 1.4rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: var(--bs-body-bg);
  cursor: text;
}
.picker-caret {
  cursor: pointer;
  color: var(--bs-secondary-color);
  padding: 0 0.25rem;
}
.picker-panel {
  position: absolute;
  z-index: 1050;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  background: var(--bs-body-bg);
  border: 1px solid var(--bs-border-color);
  border-radius: 0.5rem;
  overflow: hidden;
}
.picker-tools {
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid var(--bs-border-color);
}
.chip {
  border-radius: 1rem;
  padding: 0.1rem 0.6rem;
}
.chip-n {
  opacity: 0.65;
  font-size: 0.8em;
}
.picker-list {
  list-style: none;
  margin: 0;
  padding: 0.25rem 0;
  max-height: min(26rem, 60vh);
  overflow-y: auto;
}
.picker-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.2rem 0.75rem;
  cursor: pointer;
}
.picker-list li.active {
  background: var(--bs-tertiary-bg);
}
.picker-list li.selected {
  font-weight: 600;
}
.picker-list li.empty {
  cursor: default;
}
.sci {
  font-style: italic;
  font-size: 0.85em;
  color: var(--bs-secondary-color);
  font-weight: 400;
  margin-left: 0.25rem;
}
.birds {
  font-size: 0.8em;
  color: var(--bs-secondary-color);
  font-variant-numeric: tabular-nums;
}
.group-tag {
  flex: none;
  font-size: 0.75em;
  color: var(--bs-secondary-color);
  border: 1px solid var(--bs-border-color);
  border-radius: 1rem;
  padding: 0 0.45rem;
}
.story {
  display: inline-block;
  flex: none;
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  margin-right: 0.3rem;
  vertical-align: baseline;
}
.story-full {
  background: var(--dv-sage);
}
.story-caveat {
  background: var(--dv-gold);
}
.story-counts {
  background: transparent;
  border: 1.5px solid var(--dv-faint);
}
.picker-legend {
  padding: 0.35rem 0.75rem;
  border-top: 1px solid var(--bs-border-color);
}
</style>
