import { ref, onMounted, onBeforeUnmount } from "vue";
import Plotly from "plotly.js-basic-dist-min";
import { PLOT_TEMPLATE } from "../theme.js";

/**
 * Lifecycle shared by the Plotly components: `visible` turns true once the element first comes
 * near the viewport, so the ~30 charts of the page are only drawn when scrolled to, and the plot
 * is purged on unmount (e.g. when a species card is collapsed) to free its memory.
 *
 * @param {import("vue").Ref<HTMLElement|null>} elRef - the plot container
 * @returns {import("vue").Ref<boolean>} visible
 */
export function usePlot(elRef) {
  const visible = ref(false);
  let observer;

  onMounted(() => {
    if (!elRef.value) return; // container not rendered (e.g. no data)
    if (!("IntersectionObserver" in window)) {
      visible.value = true;
      return;
    }
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          visible.value = true;
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(elRef.value);
  });

  onBeforeUnmount(() => {
    observer?.disconnect();
    if (elRef.value) Plotly.purge(elRef.value);
  });

  return visible;
}

/**
 * Plotly.react with the site's chart theme (src/theme.js): fonts, axes and hover labels shared by
 * every chart. A layout can still override any of it.
 */
export function plotReact(el, traces, layout = {}, config = {}) {
  return Plotly.react(el, traces, { template: PLOT_TEMPLATE, ...layout }, config);
}
