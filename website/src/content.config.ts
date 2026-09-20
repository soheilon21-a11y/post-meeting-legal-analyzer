// Astro 5 requires content collections under `src/content/` to be defined
// explicitly. We keep the strings files at the plan's path
// (`src/content/strings/`) and declare the collection here so the build no
// longer relies on the deprecated auto-generation.
import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";

const strings = defineCollection({
  loader: glob({ pattern: "**/*.json", base: "./src/content/strings" }),
});

export const collections = { strings };
