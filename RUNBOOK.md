# Weekly update runbook

How the weekly scheduled task refreshes the dashboard. `DATE` = today (YYYY-MM-DD, America/New_York). Everything below writes into `raw/DATE/`.

## 0. Setup
- Attach `max-means/means-tv-analytics` with push access and clone it.
- Uscreen MCP tools needed: `analytics_store_metrics`, `analytics_top_content`, `analytics_content_performance`, `videos_list`, `collections_list`, `categories_get`.

## 1. Headline pulls (save each response exactly as returned)
| Call | File |
|---|---|
| `analytics_store_metrics()` | `raw/DATE/store_metrics.json` |
| `analytics_top_content(content_type=video, days=30, limit=100)` | `raw/DATE/top_30d.json` |
| `analytics_top_content(content_type=video, days=7, limit=100)` | `raw/DATE/top_7d.json` |

## 2. Keep creator classification current
- `categories_get(category_id=25737)` (the CREATORS category). If it lists a collection that isn't in `config/classification.json` → add its title to `creators` and its id to `creator_collection_ids`.
- After building (step 4), the build prints any `UNMATCHED suffixes`. Add each one to `creators`, `creator_aliases`, or `originals` as appropriate, then rebuild.

## 3. New titles that need a push
1. Page `videos_list(limit=100)` newest-first, saving every page's raw output to `raw/DATE/catalog/videos_pN.txt`. Stop once a whole page is published before (DATE − 90 days).
2. Save `collections_list(limit=100, status=["published"])` page 1 to `raw/DATE/catalog/collections_p1.txt`.
3. `python3 scripts/new_titles.py candidates raw/DATE`. This carries forward last week's titles still inside 90 days, adds new ones, and prints the ids to pull.
   - If it lists "unpublished-but-in-a-collection" videos that aren't already carried forward, check the collection with `collections_get`. Add the videos to `raw/DATE/new_titles_candidates.json` by hand only if they're new and actually reachable. Use `visible: false` plus a `note` when the collection is unpublished.
4. For every candidate id, call `analytics_content_performance(content_id=ID, days=90)` and save the response as-is to `raw/DATE/perf/ID.json`.
5. `python3 scripts/new_titles.py assemble raw/DATE`.

`raw/*/catalog/` is gitignored (large, and holds expiring download links). Everything else gets committed.

## 4. Build, check, publish
1. `python3 scripts/build.py raw/DATE`. Fix any UNMATCHED suffixes (step 2) and rerun.
2. Sanity-check the printed totals. Each window should have 100 videos split across creator / other / mmn.
3. Render `index.html` headlessly (`google-chrome --headless=new --screenshot`) and look at it.
4. Commit `Weekly snapshot DATE` and push to `main`. GitHub Pages redeploys automatically: https://max-means.github.io/means-tv-analytics/

## 5. Report back to Max
A short summary:
- Week-over-week change in watch hours for creators, films & series, and MMN Daily.
- Top 3 creator videos and top 3 films/series this week.
- The "needs a push" list: titles, views per week, flags.
- Anything odd, e.g. new unmatched creators, missing data, or a big drop.
