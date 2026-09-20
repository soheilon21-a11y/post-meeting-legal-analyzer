/**
 * Single source of brand truth for the Mithra website.
 *
 * Every pinned value (URLs, base path, counts, accent color) lives here.
 * Components read from this file — numbers shown in copy are never hardcoded
 * in markup. `astro.config.mjs` reads `siteUrl`/`base` from here as well.
 */

/** Canonical production origin (GitHub Pages user site). */
export const siteUrl = "https://soheilon21-a11y.github.io";

/**
 * Deployed base path. For a future custom domain this becomes "/" — that is
 * the only change required, because every internal link goes through `href()`.
 */
export const base = "/post-meeting-legal-analyzer/";

/** Brand name, used for the wordmark and the `Mithra` hero title. */
export const name = "Mithra";

/** Full product name used in <title> and OG tags. */
export const fullName = "Mithra — Post-Meeting Legal Analyzer";

export const taglineEn = "Legal AI. 100% local. 100% cited.";
export const taglineDe = "Rechts-KI. Lokal. Belegt.";

export const githubUrl =
  "https://github.com/soheilon21-a11y/post-meeting-legal-analyzer";
export const githubIssuesUrl = `${githubUrl}/issues`;
export const githubDiscussionsUrl = `${githubUrl}/discussions`;
export const githubLicenseUrl = `${githubUrl}/blob/main/LICENSE`;

/**
 * Accent color. Default is deep green `#1E4B3C` (~9.3:1 on the page
 * background, WCAG AAA). The alternative oxblood `#6B1F2A` stays available as
 * a documented one-line switch — swap the value below and rebuild.
 */
export const accentColor = "#1E4B3C";
export const accentAlternative = "#6B1F2A";

/** Test count — the ONLY place the number 284 appears. */
export const testCount = 284;

export const license = "MIT";
export const copyright = "© 2026 soheilon21-a11y";

/**
 * Prefix a root-relative path with the configured `base`.
 *
 * `href("/")`            -> "/post-meeting-legal-analyzer/"
 * `href("/de/")`         -> "/post-meeting-legal-analyzer/de/"
 * `href("/#features")`   -> "/post-meeting-legal-analyzer/#features"
 */
export function href(path = "/"): string {
  const trimmed = path.replace(/^\//, "");
  return `${base}${trimmed}`;
}
