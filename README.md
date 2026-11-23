# rogeniecordero.com

One dashboard for every brand: https://rogeniecordero.com/9nthdimension/

- `9nthdimension/index.html` — the page. It reads two data files next to it.
- `9nthdimension/articles.json` — built by `_hub/collect_articles.py` from each site's publishing calendar (read-only).
- `9nthdimension/social.json` — follower history and social-post problems from Metricool.

No scheduled refresh. The Refresh button on the page re-reads every public article calendar (live from GitHub) and the GoatCounter visit counts in the browser. Followers, social-post problems and Tibi Mundum's articles (private repo) update when Claude is asked to refresh the dashboard. All older per-brand dashboards were retired on 2026-11-22.
