# Publishing `preview.html` with GitHub Pages (2026)

`preview.html` is a self-contained project website (no build step, no backend).
GitHub Pages serves it as a live page next to the README.

## Option A — Deploy from branch (simplest, recommended here)

1. Push `main` with both copies: root `preview.html` + `index.html` and
   `docs/preview.html` + `docs/index.html`, plus `.nojekyll` in both folders.
   (`docs/preview.html` is a mechanical copy of the root file with the
   `src="docs/…"` media prefix stripped — the diff must show only those lines.)
2. Open the repo on GitHub → **Settings** → **Pages**.
3. Under **Build and deployment → Source**, choose **Deploy from a branch**.
4. Branch: `main`, folder: `/docs` (recommended). `/ (root)` also works
   because of the mirrors.
5. Wait 1–2 min for the “pages build and deployment” Action. The site is live at:

   `https://M0-AR.github.io/raft-consensus-universe-phd-2026/preview.html`

   (mirror: `…/docs/preview.html` — one of the two always resolves; with the
   mirrors in place, `/preview.html` resolves under either source setting).

Branch deployment serves static files only — which is exactly what
`preview.html` is (inline CSS/JS, no server code), so nothing else is needed.

## Option B — GitHub Actions (use when you add a build step later)

Use only if `preview.html` ever needs generated charts committed by CI.
Keep the workflow to: checkout → (optional) `python scripts/run_all.py --quick` →
upload `preview.html` + `results/` + `docs/` as the Pages artifact → deploy.
Branch deployment stays the default until then.

## Custom domain (optional)

1. Add a `CNAME` file at the root containing your domain.
2. Point DNS at GitHub Pages (`<user>.github.io`).
3. Enforce HTTPS in Settings → Pages.

## Checklist before sharing

- [ ] `preview.html` opens locally via `python3 -m http.server` with no console errors.
- [ ] `docs/screenshot-hero.png` and `docs/screenshot-benchmarks.png` are committed (README embeds them).
- [ ] `docs/demo.gif` / `docs/demo.mp4` exist after recording (`bash docs/demo.sh play` + `agg`).
- [ ] README links use relative paths (`preview.html`, `docs/...`, `results/...`) so they work on both github.com and Pages.
