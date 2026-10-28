<template>
  <!-- eslint-disable vue/no-v-html -- KaTeX output of our own strings -->
  <div v-if="display" class="tex-display" v-html="html"></div>
  <span v-else v-html="html"></span>
</template>

<script setup>
import { computed } from "vue";
import katex from "katex";
import { MODEL_COLORS } from "../../theme.js";
import "katex/dist/katex.min.css";

// The model's terms, one colour each, as in ExploreMethod.vue (C and .t-*): \Tr is T in the
// trend's colour, and so on. Expanded here rather than as KaTeX macros, where "#" is an argument.
const TERMS = {
  Tr: [MODEL_COLORS.trend, "T"],
  Yr: [MODEL_COLORS.year, "Y"],
  Se: [MODEL_COLORS.season, "S"],
  Sh: [MODEL_COLORS.shift, "D"],
  Ep: [MODEL_COLORS.episode, "E"],
  Wx: [MODEL_COLORS.weather, "W"],
};
const expand = (e) =>
  e.replace(
    /\\(Tr|Yr|Se|Sh|Ep|Wx)(?![a-zA-Z])/g,
    (_, k) => `\\textcolor{${TERMS[k][0]}}{${TERMS[k][1]}}`,
  );

const props = defineProps({
  // LaTeX source
  e: { type: String, required: true },
  display: { type: Boolean, default: false },
});

const html = computed(() =>
  katex.renderToString(expand(props.e), { displayMode: props.display, throwOnError: false }),
);
</script>

<style scoped>
.tex-display {
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
