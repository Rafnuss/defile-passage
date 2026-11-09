import { cp, mkdir, rm } from "node:fs/promises";

// Serve the same export as the QA viewer; statistical fitting is a separate step.
const source = new URL("../../data/output/explore/", import.meta.url);
const target = new URL("../public/data/explore/", import.meta.url);
await mkdir(new URL("../public/data/", import.meta.url), { recursive: true });
await rm(target, { recursive: true, force: true });
await cp(source, target, { recursive: true });
console.log("Copied data/output/explore to the documentation site");
