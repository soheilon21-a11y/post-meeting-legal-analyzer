# Deploying the Mithra website

The site is a fully static Astro build (`website/dist`) deployed to GitHub
Pages by the workflow at `.github/workflows/deploy-website.yml`.

## 1. One-time GitHub Pages setup

1. Push this repository to GitHub.
2. Open **Settings → Pages**.
3. Under **Build and deployment → Source**, choose **GitHub Actions**
   (do **not** choose "Deploy from a branch").
4. Save. No branch or folder selection is needed — the workflow uploads the
   artifact and deploys it.

## 2. What triggers a deploy

- A push to `main` that changes anything under `website/**`.
- A manual run from **Actions → Deploy website → Run workflow**
  (`workflow_dispatch`).

Backend-only changes never trigger this workflow, because it is path-filtered
to `website/**`.

## 3. Expected URL

With the default configuration the site is served at:

```
https://soheilon21-a11y.github.io/post-meeting-legal-analyzer/
```

`siteUrl` and `base` are pinned in `website/src/config.ts` and read by
`astro.config.mjs`; every internal link/asset goes through the `href()` helper,
so there is no base-path drift.

## 4. Verify a deploy

1. Open the Actions run and confirm both `build` and `deploy` jobs are green.
2. Open the Pages URL and check:
   - the EN landing page loads with CSS applied;
   - the `EN | DE` toggle switches to the German stub;
   - `Impressum`, `Datenschutzerklärung`, and a bad URL (404) all render.
3. In DevTools → Network, reload and confirm there are **zero external
   requests** and **zero client JavaScript** files.

## 5. Custom domain (optional, future)

If a custom domain is attached (e.g. `mithra.example`), the only code change
needed is in `website/src/config.ts`:

```ts
export const base = "/"; // was "/post-meeting-legal-analyzer/"
```

Because every internal link is built with `href()`, changing this single value
re-points the whole site. Then add the domain in **Settings → Pages → Custom
domain** and configure DNS per GitHub's instructions.

## 6. Notes and known limitations

- **CSP:** the strict Content-Security-Policy is injected as a `<meta>` tag in
  production builds only. `frame-ancestors` is deliberately omitted — it is
  ignored inside `<meta>` per the CSP spec and would need a real HTTP header
  (not available on GitHub Pages). If a CDN/reverse proxy is added later, set
  the full CSP as a response header there.
- **Open Graph image:** v1 ships text-only OG meta. SVG OG images are poorly
  supported by crawlers; add a PNG `og:image` in a future iteration.
- **No client JavaScript:** mobile navigation uses native
  `<details>/<summary>`, and the language switch uses plain `<a>` links, so the
  site ships 0 bytes of JS and the CSP can be `script-src 'none'`.
