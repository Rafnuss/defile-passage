import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFile, writeFile, mkdir } from "node:fs/promises";

// The methods guide's edit mode (src/editMode.js), on the dev server only: the prose edits, and
// the review notes with the replies typed under them
const FILES = {
  "/__guide-edits": new URL("../logs/guide-edits.json", import.meta.url),
  "/__guide-notes": new URL("../logs/guide-notes.json", import.meta.url),
};

function guideEdits() {
  return {
    name: "guide-edits",
    apply: "serve",
    configureServer(server) {
      for (const [route, file] of Object.entries(FILES)) {
        server.middlewares.use(route, async (req, res) => {
          res.setHeader("Content-Type", "application/json");
          if (req.method === "POST") {
            let body = "";
            for await (const chunk of req) body += chunk;
            JSON.parse(body); // refuse anything but JSON
            await mkdir(new URL(".", file), { recursive: true });
            await writeFile(file, body);
            res.end("{}");
          } else {
            res.end(await readFile(file, "utf8").catch(() => "[]"));
          }
        });
      }
    },
  };
}

export default defineConfig({
  plugins: [vue(), guideEdits()],
  base: "./",
  build: {
    outDir: "../output/site",
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
