#!/usr/bin/env python3
"""One-off: reconstruct past weekly snapshots from nested trailing windows.

Uscreen's analytics_top_content only reports windows ending today, so a window ending N days ago
is (last N+k days) minus (last N days), per video. Videos missing from a top-100 list are treated
as 0, so long-tail numbers can be slightly high; rankings at the top are unaffected.
"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "raw/_backfill"

wins, cur = {}, None
for line in open(B / "windows_2026-11-09.txt"):
    line = line.strip()
    if not line or line.startswith("# "):
        continue
    m = re.match(r"## days=(\d+)", line)
    if m:
        cur = wins.setdefault(int(m.group(1)), {}); continue
    i, v, w = map(int, line.split())
    cur[i] = (v, w)

titles = {}
for f in ("top_7d.json", "top_30d.json"):
    for it in json.load(open(ROOT / "raw/2026-11-09" / f))["items"]:
        titles[it["content_id"]] = it["title"]
for line in open(B / "extra_titles.tsv"):
    i, t = line.rstrip("\n").split("\t"); titles[int(i)] = t
missing = {i for w in wins.values() for i in w} - set(titles)
assert not missing, f"no title for {missing}"


def diff(big, small, days):
    rows = []
    for i, (v, w) in wins[big].items():
        sv, sw = wins[small].get(i, (0, 0))
        dv, dw = max(v - sv, 0), max(w - sw, 0)
        if dw > 0:
            rows.append({"content_id": i, "title": titles[i], "views": dv, "watch_time": dw})
    rows.sort(key=lambda r: -r["watch_time"])
    return {"content_type": "video", "days": days, "limit": 100, "items": rows[:100],
            "_derived": f"top_content(days={big}) minus top_content(days={small}), pulled 2026-11-09"}


plan = {"2026-11-02": (14, 37, 7), "2026-10-26": (21, 44, 14), "2026-10-19": (28, 51, 21)}
for d, (w7, w30, sub) in plan.items():
    out = ROOT / "raw" / d
    out.mkdir(exist_ok=True)
    json.dump(diff(w7, sub, 7), open(out / "top_7d.json", "w"), ensure_ascii=False)
    json.dump(diff(w30, sub, 30), open(out / "top_30d.json", "w"), ensure_ascii=False)
    json.dump(None, open(out / "store_metrics.json", "w"))
    print(d, "ok")
