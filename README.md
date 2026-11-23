# rogeniecordero.com

One dashboard for every brand: https://rogeniecordero.com/9nthdimension/

- `9nthdimension/index.html` — the page. It reads two data files next to it.
- `9nthdimension/articles.json` — built by `_hub/collect_articles.py` from each site's publishing calendar (read-only).
- `9nthdimension/social.json` — follower history and social-post problems from Metricool.

Both files are refreshed daily by the "All Brands Dashboard refresh" scheduled task. All older per-brand dashboards were retired on 2026-11-22.
