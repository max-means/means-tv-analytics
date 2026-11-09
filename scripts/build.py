#!/usr/bin/env python3
"""Build the dashboard data from raw Uscreen pulls.

Usage: python3 scripts/build.py raw/2026-11-09
Reads  raw/<date>/top_30d.json, top_7d.json, store_metrics.json
Writes data/snapshots/<date>.json and data/data.js (all snapshots, loaded by index.html)
"""
import json, re, sys, glob, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "config/classification.json"))
creators = {n.lower(): n for n in cfg["creators"]}
creators.update({k.lower(): v for k, v in cfg["creator_aliases"].items()})
originals = {k.lower(): v for k, v in cfg["originals"].items()}
own_bucket = cfg.get("own_bucket_shows", {})
series_pats = [(re.compile(p["regex"]), p["series"]) for p in cfg["series_patterns"]]


def classify(cid, raw_title):
    title = re.sub(r"\s+", " ", raw_title).strip()
    if str(cid) in cfg["original_ids"]:
        return "other", "Means Original", cfg["original_ids"][str(cid)], title
    if str(cid) in cfg["series_ids"]:
        return "other", "Series", cfg["series_ids"][str(cid)], title
    if " | " in title:
        base, suffix = title.rsplit(" | ", 1)
        key = suffix.strip().lower()
        if key in creators:
            return "creator", "Creator", creators[key], base.strip()
        if key in originals:
            base = base.strip()
            if re.match(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$", base):  # dated episodes, e.g. MMN Daily
                base = f"{suffix.strip()} · {base}"
            return "other", "Means Original", originals[key], base
    for rx, name in series_pats:
        if rx.search(title):
            return "other", "Series", name, title
    if " | " in title:  # unknown suffix: flag it so it can be added to the config
        base, suffix = title.rsplit(" | ", 1)
        return "other", "Unmatched", suffix.strip(), base.strip()
    return "other", "Film", title, title


def window(raw):
    items = []
    for it in raw["items"]:
        bucket, typ, show, clean = classify(it["content_id"], it["title"])
        bucket = own_bucket.get(show, bucket)
        v, wt = it["views"], it["watch_time"]
        items.append({
            "id": it["content_id"], "title": clean, "full_title": it["title"].strip(),
            "show": show, "bucket": bucket, "type": typ,
            "views": v, "watch_hours": round(wt / 3600, 1),
            "avg_min": round(wt / v / 60, 1) if v else 0,
        })
    out = {"days": raw["days"], "items": items, "buckets": {}, "shows": {}}
    for b in ("creator", "other", "mmn"):
        sub = [i for i in items if i["bucket"] == b]
        out["buckets"][b] = {
            "count": len(sub),
            "views": sum(i["views"] for i in sub),
            "watch_hours": round(sum(i["watch_hours"] for i in sub), 1),
            "by_type": {},
        }
        for i in sub:
            t = out["buckets"][b]["by_type"].setdefault(i["type"], {"views": 0, "watch_hours": 0, "count": 0})
            t["views"] += i["views"]; t["watch_hours"] = round(t["watch_hours"] + i["watch_hours"], 1); t["count"] += 1
        shows = {}
        for i in sub:
            s = shows.setdefault(i["show"], {"show": i["show"], "type": i["type"], "views": 0, "watch_hours": 0, "videos": 0})
            s["views"] += i["views"]; s["watch_hours"] = round(s["watch_hours"] + i["watch_hours"], 1); s["videos"] += 1
        out["shows"][b] = sorted(shows.values(), key=lambda s: -s["watch_hours"])
    return out


def new_titles(path, as_of):
    """Score titles added in the last 90 days so marketing can see which need a push."""
    from datetime import date
    if not path.exists():
        return None
    raw = json.load(open(path))
    today = date.fromisoformat(as_of)
    rows = []
    for t in raw["titles"]:
        days = max((today - date.fromisoformat(t["added"])).days, 1)
        weeks = max(days / 7, 1)  # titles under a week old are scored on their first week
        r = dict(t)
        r["days_live"] = days
        r["views_per_week"] = round(t["views"] / weeks, 1)
        r["hours_per_week"] = round(t["wt"] / 3600 / weeks, 1)
        r["watch_hours"] = round(t["wt"] / 3600, 1)
        r["watch_hours_7d"] = round(t["wt_7d"] / 3600, 1)
        r["avg_min"] = round(t["wt"] / t["views"] / 60, 1) if t["views"] else 0
        r["completion"] = round(t["wt"] / t["views"] / t["duration"], 2) if t["views"] and t.get("duration") else None
        rows.append(r)
    vpw = sorted(r["views_per_week"] for r in rows)
    median = vpw[len(vpw) // 2] if vpw else 0
    for r in rows:
        flags = []
        if not r.get("visible", True):
            flags.append("Not in catalog")
        if r["views"] == 0:
            flags.append("No views yet")
        elif r["views_7d"] == 0 and r["days_live"] > 14:
            flags.append("Gone quiet")
        if r["views_per_week"] < median / 2:
            flags.append("Well below typical")
        elif r["views_per_week"] < median:
            flags.append("Below typical")
        r["flags"] = flags
        r["needs_push"] = r["views_per_week"] < median or "Gone quiet" in flags
    rows.sort(key=lambda r: (r["views_per_week"], r["hours_per_week"]))
    return {"cutoff": raw["cutoff"], "median_views_per_week": median, "titles": rows}


def main(raw_dir):
    raw_dir = Path(raw_dir)
    date = raw_dir.name
    snap = {
        "date": date,
        "store": json.load(open(raw_dir / "store_metrics.json")),
        "windows": {
            "30d": window(json.load(open(raw_dir / "top_30d.json"))),
            "7d": window(json.load(open(raw_dir / "top_7d.json"))),
        },
    }
    snap["new_titles"] = new_titles(raw_dir / "new_titles.json", date)
    unmatched = {i["full_title"] for w in snap["windows"].values() for i in w["items"] if i["type"] == "Unmatched"}
    os.makedirs(ROOT / "data/snapshots", exist_ok=True)
    json.dump(snap, open(ROOT / f"data/snapshots/{date}.json", "w"), indent=1, ensure_ascii=False)
    snaps = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "data/snapshots/*.json")))]
    with open(ROOT / "data/data.js", "w") as f:
        f.write("// Generated by scripts/build.py - do not edit by hand\n")
        f.write("window.MEANS_SNAPSHOTS = " + json.dumps(snaps, ensure_ascii=False) + ";\n")
    print(f"built {date}: {len(snaps)} snapshot(s)")
    for w, d in snap["windows"].items():
        for b, s in d["buckets"].items():
            print(f"  {w} {b:8} {s['count']:3} videos  {s['views']:6} views  {s['watch_hours']:8} hrs  {s['by_type']}")
    if snap["new_titles"]:
        nt = snap["new_titles"]
        print(f"  new titles: {len(nt['titles'])}, median {nt['median_views_per_week']} views/wk, "
              f"{sum(r['needs_push'] for r in nt['titles'])} flagged")
    if unmatched:
        print("UNMATCHED suffixes (add to config/classification.json):", *unmatched, sep="\n  ")


if __name__ == "__main__":
    main(sys.argv[1])
