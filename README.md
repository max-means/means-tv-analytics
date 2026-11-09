# Means TV · Content Performance dashboard

A static dashboard (no build step) showing which Uscreen videos performed best over the past 7 and 30 days, split into **creator videos** and **films & non-creator series**.

Live: https://max-means.github.io/means-tv-analytics/ — updated weekly (see `RUNBOOK.md`).

## Files
- `index.html` — the dashboard. Plain HTML/JS, no dependencies.
- `data/data.js` — all snapshots, generated. Don't edit by hand.
- `data/snapshots/YYYY-MM-DD.json` — one processed snapshot per weekly run.
- `raw/YYYY-MM-DD/` — the untouched Uscreen pulls each snapshot was built from.
- `config/classification.json` — how titles are sorted into creator / Means Original / series / film. Edit this to fix a misclassified title.
- `scripts/build.py` — turns a `raw/` folder into a snapshot (`python3 scripts/build.py raw/2026-11-09`).

## Where the numbers come from
Uscreen analytics (`top content` by watch time, top 100 videos per window) plus the store snapshot (active subscribers, MRR). The analytics are batch-synced, so the most recent day may be incomplete.

## "New titles that need a push"
Films and non-creator series (not creator videos, not MMN Daily) added in the last 90 days, from `raw/<date>/new_titles.json`.
Each title is scored on views per week since it was added. "Needs a push" means below the median for new titles, or no views in the last week after being live 2+ weeks.
Titles that only live in an unpublished collection (e.g. the Halloween collections) are marked "Not in catalog" and hidden by default.

## Backfilled weeks (2026-10-19, 10-26, 11-02)
These were rebuilt on 2026-11-09 with `scripts/backfill.py`. Uscreen only reports windows ending today, so each past window is (last N+7 days) − (last N days) per video, using the raw lists in `raw/_backfill/`. Long-tail numbers can run slightly high. Subscriber/MRR and the new-titles section weren't recorded for those weeks. Week-over-week arrows and the trend chart compare each week's top 50 videos, so rebuilt and live weeks are measured the same way.
