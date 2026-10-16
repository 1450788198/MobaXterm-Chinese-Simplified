# -*- coding: utf-8 -*-
"""Align two MobaXterm DFM resource trees and mine a human-curated EN->ZH map.

Usage:
    python xalign.py <english.exe> <chinese.exe> [out.json]

Both trees are walked by structural path (form name / object-name chain /
property name), so the same UI element lines up in both versions even when the
builds are not identical.  Only pairs whose Chinese side actually contains CJK
are kept.
"""
import json
import struct
import sys

import dfm

VA_STRING, VA_LSTRING, VA_WSTRING, VA_UTF8STRING = 6, 12, 18, 20


class Res:
    def __init__(self, path):
        self.path = path
        self.B = open(path, 'rb').read()
        B = self.B
        e = struct.unpack_from('<I', B, 0x3C)[0]
        coff = e + 4
        nsec = struct.unpack_from('<H', B, coff + 2)[0]
        opt_size = struct.unpack_from('<H', B, coff + 16)[0]
        opt = coff + 20
        self.rsrc_rva, self.rsrc_size = struct.unpack_from('<II', B, opt + 96 + 16)
        secs = []
        for i in range(nsec):
            o = coff + 20 + opt_size + i * 40
            vsize, va, rsize, raw = struct.unpack_from('<IIII', B, o + 8)
            secs.append((va, max(vsize, rsize), raw))
        self.secs = secs

    def raw_of(self, rva):
        for va, sz, raw in self.secs:
            if va <= rva < va + sz:
                return raw + (rva - va)
        return None

    def enum(self):
        B = self.B
        root = self.raw_of(self.rsrc_rva)

        def dirname(v):
            if v & 0x80000000:
                o = root + (v & 0x7FFFFFFF)
                ln = struct.unpack_from('<H', B, o)[0]
                return B[o + 2:o + 2 + ln * 2].decode('utf-16-le')
            return v

        def walk(off, path):
            _c, _t, _a, _b, nname, nid = struct.unpack_from('<IIHHHH', B, off)
            for i in range(nname + nid):
                eo = off + 16 + i * 8
                nameid, offs = struct.unpack_from('<II', B, eo)
                nm = dirname(nameid)
                if offs & 0x80000000:
                    yield from walk(root + (offs & 0x7FFFFFFF), path + [nm])
                else:
                    de = root + (offs & 0x7FFFFFFF)
                    dva, dsz, _cp, _rv = struct.unpack_from('<IIII', B, de)
                    yield (path + [nm], dva, dsz)

        for path, dva, dsz in walk(root, []):
            yield (path, dva, dsz)

def collect(res):
    """form_name -> {path_key: string_value}"""
    out = {}
    for path, dva, dsz in res.enum():
        if len(path) != 3 or str(path[0]) != '10':
            continue
        fo = res.raw_of(dva)
        if fo is None or res.B[fo:fo + 4] != b'TPF0':
            continue
        nm = path[1]
        try:
            form = dfm.parse(res.B[fo:fo + dsz])
        except Exception:
            continue
        vals = {}
        walk_obj(form, (form['name'],), vals)
        out[nm] = vals
    return out


def walk_obj(obj, prefix, vals):
    for pname, (pt, pv) in obj['props'].items():
        if pt in (VA_STRING, VA_LSTRING, VA_WSTRING, VA_UTF8STRING):
            if isinstance(pv, str):
                vals[prefix + (pname,)] = pv
    for idx, ch in enumerate(obj['children']):
        walk_obj(ch, prefix + (ch['name'], idx), vals)


def has_cjk(s):
    return any('\u4e00' <= c <= '\u9fff' for c in s)


def main():
    en = collect(Res(sys.argv[1]))
    zh = collect(Res(sys.argv[2]))
    out_path = sys.argv[3] if len(sys.argv) > 3 else 'ref_map.json'

    pairs = {}
    stats = {'forms_en': len(en), 'forms_zh': len(zh),
             'shared_forms': 0, 'aligned': 0, 'changed': 0, 'untranslated': 0}
    for f in en:
        if f not in zh:
            continue
        stats['shared_forms'] += 1
        a, b = en[f], zh[f]
        for k, v in a.items():
            if k not in b:
                continue
            stats['aligned'] += 1
            w = b[k]
            if w == v:
                stats['untranslated'] += 1
                continue
            if has_cjk(w):
                pairs.setdefault(v, w)
                stats['changed'] += 1

    json.dump(pairs, open(out_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print('mined pairs:', len(pairs), '->', out_path)


if __name__ == '__main__':
    main()
