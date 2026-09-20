// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// Single source of brand truth: site URL and base path are read from
// src/config.ts so they can never drift between the config and the site.
// (esbuild bundles the config and its TypeScript imports before evaluation.)
import { siteUrl, base } from "./src/config.ts";

export default defineConfig({
  site: siteUrl,
  base,
  output: "static",
  // Astro's build-time minification stays ON (never disable it).
  vite: {
    plugins: [tailwindcss()],
  },
});
