import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFile, writeFile, mkdir } from "node:fs/promises";

// The methods guide's edit mode (src/editMode.js) saves its edits here, on the dev server only
const EDITS = new URL("../logs/guide-edits.json", import.meta.url);

function guideEdits() {
  return {
    name: "guide-edits",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__guide-edits", async (req, res) => {
        res.setHeader("Content-Type", "application/json");
        if (req.method === "POST") {
          let body = "";
          for await (const chunk of req) body += chunk;
          JSON.parse(body); // refuse anything but JSON
          await mkdir(new URL(".", EDITS), { recursive: true });
          await writeFile(EDITS, body);
          res.end("{}");
        } else {
          res.end(await readFile(EDITS, "utf8").catch(() => "[]"));
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), guideEdits()],
  base: "./",
  build: {
    outDir: "../logs/site",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{ name: "plotly", test: /node_modules[\\/]plotly/, priority: 20 }],
        },
      },
    },
  },
});
