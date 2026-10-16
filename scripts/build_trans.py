# -*- coding: utf-8 -*-
"""missing.json + trans_idx.T  ->  trans_map.json (exact source->zh) + skip report."""
import json, io, sys
sys.path.insert(0, r'C:/Users/yanfa/WorkBuddy/2026-10-16-14-08-23/mobaxterm/analysis')
import trans_idx

missing = json.load(open('missing.json', encoding='utf-8'))
mp = {}
skip = []
for i, s in enumerate(missing):
    t = trans_idx.T.get(i)
    if t is None:
        skip.append((i, s))
    else:
        mp[s] = t

json.dump(mp, open('trans_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
with io.open('trans_skip.txt', 'w', encoding='utf-8') as f:
    f.write('未翻译（功能标识/内部名，保持原样）共 %d 条\n\n' % len(skip))
    for i, s in skip:
        f.write('%4d\t%r\n' % (i, s))
print('trans_map.json: %d entries   skipped: %d' % (len(mp), len(skip)))
