<template>
  <div class="year-control">
    <label :for="id">Year</label>
    <div class="input-group input-group-sm navigation-control">
      <button
        type="button"
        class="btn btn-outline-secondary"
        :aria-label="`Previous ${context} year`"
        :disabled="index === 0"
        @click="year = ordered[index - 1]"
      >
        ‹
      </button>
      <select :id="id" v-model.number="year" class="form-select form-select-sm">
        <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
      </select>
      <button
        type="button"
        class="btn btn-outline-secondary"
        :aria-label="`Next ${context} year`"
        :disabled="index === ordered.length - 1"
        @click="year = ordered[index + 1]"
      >
        ›
      </button>
    </div>
  </div>
</template>
<script setup>
import { computed } from "vue";
const props = defineProps({
  years: { type: Array, required: true },
  id: { type: String, required: true },
  context: { type: String, required: true },
});
const year = defineModel({ type: Number, required: true });
const ordered = computed(() => props.years.slice().sort((a, b) => a - b));
const index = computed(() => ordered.value.indexOf(year.value));
</script>
