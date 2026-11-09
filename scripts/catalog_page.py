#!/usr/bin/env python3
"""Summarize a saved videos_list page: cursor + id range + published date range."""
import json, sys
t = open(sys.argv[1]).read(); d = json.loads(t[t.index('{"data"'):t.rindex('}') + 1])
ds = [v['published_at'] for v in d['data'] if v['published_at']]
print('next', d['next_cursor'], 'n', len(d['data']), 'ids', d['data'][0]['id'], '->', d['data'][-1]['id'],
      'pub', min(ds) if ds else None, '->', max(ds) if ds else None)
