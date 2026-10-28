import js from "@eslint/js";
import vue from "eslint-plugin-vue";
import prettier from "eslint-config-prettier";
import security from "eslint-plugin-security";
import globals from "globals";

export default [
  { ignores: ["public/data/**"] },
  js.configs.recommended,
  security.configs.recommended,
  ...vue.configs["flat/recommended"],
  // Formatting is Prettier's job: turn off the stylistic rules that would conflict
  prettier,
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      // Optional props are simply undefined when not passed
      "vue/require-default-prop": "off",
      // Noisy false positives: index lookups, hash-vs-string compare
      "security/detect-object-injection": "off",
      "security/detect-possible-timing-attacks": "off",
      eqeqeq: ["error", "smart"],
      "prefer-const": "error",
      "no-var": "error",
      "vue/no-v-html": "error",
      "no-unused-vars": ["error", { caughtErrors: "none" }],
    },
  },
  // Build script writes to paths it computes itself
  { files: ["scripts/**"], rules: { "security/detect-non-literal-fs-filename": "off" } },
];
