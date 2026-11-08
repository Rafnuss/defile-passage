import { createApp } from "vue";
import { createI18n } from "vue-i18n";
import App from "./App.vue";
import messages from "./i18n/explore.js";
import "bootstrap-icons/font/bootstrap-icons.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "./theme.css";
import "./method.css";
import "./site.css";
import "./site-header.css";

createApp(App)
  .use(createI18n({ legacy: false, locale: "en", messages }))
  .mount("#app");

// `?edit` on the dev server: edit the guide's prose in place (editMode.js)
if (import.meta.env.DEV && new URLSearchParams(location.search).has("edit"))
  import("./editMode.js").then((m) => m.startEditMode());
