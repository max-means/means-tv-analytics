#!/usr/bin/env python3
"""Helper for the "New titles that need a push" section.

Step 1  python3 scripts/new_titles.py candidates raw/<date>
        Reads raw/<date>/catalog/videos_p*.txt and collections_p*.txt (saved videos_list /
        collections_list pages) plus the previous snapshot's new_titles.json, and writes
        raw/<date>/new_titles_candidates.json: every film / non-creator series added in the
        last 90 days (creator videos and MMN Daily excluded). Prints the ids that need an
        analytics_content_performance(days=90) pull.

Step 2  Save each analytics_content_performance(content_id=<id>, days=90) response, as-is,
        to raw/<date>/perf/<id>.json.

Step 3  python3 scripts/new_titles.py assemble raw/<date>
        Combines candidates + perf files into raw/<date>/new_titles.json for build.py.
"""
import json, sys, glob, re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load_pages(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        t = open(f).read()
        out += json.loads(t[t.index('{"data"'):t.rindex('}') + 1])["data"]
    return out


def candidates(raw_dir):
    import importlib.util
    spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    as_of = date.fromisoformat(raw_dir.name)
    cutoff = (as_of - timedelta(days=90)).isoformat()
    cfg = json.load(open(ROOT / "config/classification.json"))
    creator_cols = set(cfg.get("creator_collection_ids", []))
    vids = load_pages(str(raw_dir / "catalog/videos_p*.txt"))
    cols = load_pages(str(raw_dir / "catalog/collections_p*.txt"))
    out = {}

    # carry forward last snapshot's titles that are still inside the 90-day window
    prev = sorted(p for p in glob.glob(str(ROOT / "raw/*/new_titles.json")) if Path(p).parent.name < raw_dir.name)
    if prev:
        for t in json.load(open(prev[-1]))["titles"]:
            if t["added"] >= cutoff:
                keep = {k: t[k] for k in ("id", "title", "type", "added", "duration", "visible", "show", "note", "collection") if k in t}
                out[t["id"]] = keep

    for v in vids:
        if v["status"] != "published" or not v.get("published_at") or v["published_at"][:10] < cutoff:
            continue
        if re.search(r"\bLIVE\b|Live Event recording|\(Trailer\)", v["title"]):
            continue
        bucket, typ, show, clean = b.classify(v["id"], v["title"])
        bucket = b.own_bucket.get(show, bucket)
        if set(v.get("collection_ids") or []) & creator_cols:
            bucket = "creator"
        if bucket != "other" or v["id"] in out:
            continue
        dur = v.get("duration") or 0
        rec = {"id": v["id"], "title": clean, "type": "Short film" if typ == "Film" and dur and dur < 2400 else typ,
               "added": v["published_at"][:10], "duration": dur or None, "visible": True}
        if typ != "Film":
            rec["show"] = show
        out[v["id"]] = rec

    for c in cols:
        if c["status"] != "published" or not c.get("published_at") or c["published_at"][:10] < cutoff:
            continue
        if c["id"] in creator_cols or c["id"] in out:
            continue
        if re.search(r"Collection$|\| Unicorn Riot", c["title"]):  # curated playlists, not new series
            continue
        out[c["id"]] = {"id": c["id"], "title": f'{c["title"]} ({c["video_count"]} episodes)', "type": "Series",
                        "added": c["published_at"][:10], "duration": None, "visible": True, "collection": True}

    # unpublished videos that are new and only reachable through a non-creator collection: flag for review
    review = [{"id": v["id"], "title": v["title"], "collection_ids": v["collection_ids"]}
              for v in vids if v["status"] == "unpublished" and v.get("collection_ids")
              and not set(v["collection_ids"]) & (creator_cols | set(out)) and v["id"] not in out
              and not re.search(r"\bLIVE\b|Live Event recording", v["title"])]
    res = {"as_of": raw_dir.name, "cutoff": cutoff, "titles": sorted(out.values(), key=lambda t: t["added"]),
           "needs_review": review}
    json.dump(res, open(raw_dir / "new_titles_candidates.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(res['titles'])} candidates since {cutoff}. Pull analytics_content_performance(days=90) for ids:")
    print(",".join(str(t["id"]) for t in res["titles"]))
    if review:
        print(f"\n{len(review)} unpublished-but-in-a-collection videos to review (add to candidates by hand if the collection is live):")
        for r in review:
            print("  ", r["id"], r["title"][:60], r["collection_ids"])


def assemble(raw_dir):
    cand = json.load(open(raw_dir / "new_titles_candidates.json"))
    as_of = date.fromisoformat(cand["as_of"])
    win7 = (as_of - timedelta(days=7)).isoformat()  # matches Uscreen's 7-day window (8 calendar days)
    titles, missing = [], []
    for t in cand["titles"]:
        p = raw_dir / f"perf/{t['id']}.json"
        if not p.exists():
            missing.append(t["id"]); continue
        perf = json.load(open(p))
        days = perf.get("by_day", [])
        r = dict(t)
        r["views"] = perf["totals"]["views"]; r["wt"] = perf["totals"]["watch_time"]
        r["views_7d"] = sum(d["views"] for d in days if d["date"] >= win7)
        r["wt_7d"] = sum(d["watch_time"] for d in days if d["date"] >= win7)
        r["last_view"] = max((d["date"] for d in days), default=None)
        titles.append(r)
    if missing:
        sys.exit(f"Missing perf files for: {missing}")
    json.dump({"_readme": "Generated by scripts/new_titles.py assemble", "as_of": cand["as_of"],
               "cutoff": cand["cutoff"], "titles": titles}, open(raw_dir / "new_titles.json", "w"), indent=1, ensure_ascii=False)
    print(f"wrote {len(titles)} titles to {raw_dir / 'new_titles.json'}")


if __name__ == "__main__":
    mode, d = sys.argv[1], Path(sys.argv[2]).resolve()
    {"candidates": candidates, "assemble": assemble}[mode](d)
