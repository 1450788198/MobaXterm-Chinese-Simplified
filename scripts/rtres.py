# -*- coding: utf-8 -*-
"""RT_STRING (type 6) localisation.

MobaXterm ships ~1200 UTF-16 strings in 79 RT_STRING blocks (skin library +
own dialogs).  The reference Simplified-Chinese build uses the very same block
ids and indexes, so the whole table can be inherited by (block, index).

  build_map()      mine {(block, index): chinese} from the reference build
  localize_block() rewrite one block with the mapped Chinese strings
"""
import json
import os
import struct

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_HERE, 'rt_map.json')


def _res_entries(path):
    B = open(path, 'rb').read()
    e = struct.unpack_from('<I', B, 0x3C)[0]
    coff = e + 4
    nsec = struct.unpack_from('<H', B, coff + 2)[0]
    opt_size = struct.unpack_from('<H', B, coff + 16)[0]
    rsrc_rva, _ = struct.unpack_from('<II', B, coff + 20 + 96 + 16)
    secs = []
    for i in range(nsec):
        o = coff + 20 + opt_size + i * 40
        vsize, va, rsize, raw = struct.unpack_from('<IIII', B, o + 8)
        secs.append((va, max(vsize, rsize), raw))

    def raw_of(rva):
        for va, sz, raw in secs:
            if va <= rva < va + sz:
                return raw + (rva - va)
        return None

    root = raw_of(rsrc_rva)
    out = {}

    def dirname(v):
        if v & 0x80000000:
            o = root + (v & 0x7FFFFFFF)
            ln = struct.unpack_from('<H', B, o)[0]
            return B[o + 2:o + 2 + ln * 2].decode('utf-16-le')
        return v

    def walk(off, path):
        chars, ts, maj, mn, nn, ni = struct.unpack_from('<IIHHHH', B, off)
        for i in range(nn + ni):
            eo = off + 16 + i * 8
            nameid, offs = struct.unpack_from('<II', B, eo)
            nm = dirname(nameid)
            if offs & 0x80000000:
                walk(root + (offs & 0x7FFFFFFF), path + [nm])
            else:
                de = root + (offs & 0x7FFFFFFF)
                dva, dsz, cp, rv = struct.unpack_from('<IIII', B, de)
                if path and str(path[0]) == '6':
                    fo = raw_of(dva)
                    out[int(path[1])] = B[fo:fo + dsz]

    walk(root, [])
    return out


def split_block(data):
    """RT_STRING block -> {index: str} (index starts at 1)."""
    i = 0
    idx = 0
    res = {}
    while i + 2 <= len(data):
        ln = struct.unpack_from('<H', data, i)[0]
        i += 2
        if ln == 0:
            idx += 1
            continue
        raw = data[i:i + ln * 2]
        i += ln * 2
        idx += 1
        try:
            res[idx] = raw.decode('utf-16-le')
        except Exception:
            pass
    return res


def join_block(strings, size_hint=None):
    """{index: str} -> RT_STRING block bytes."""
    out = bytearray()
    top = max(strings) if strings else 0
    for idx in range(1, top + 1):
        s = strings.get(idx, '')
        b = s.encode('utf-16-le')
        out += struct.pack('<H', len(b) // 2)
        out += b
    if size_hint:
        while len(out) % size_hint:
            out += b'\x00'
    return bytes(out)


def build_map(orig_path, ref_path):
    if os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as f:
            raw = json.load(f)
        return {tuple(int(x) for x in k.split('#')): v for k, v in raw.items()}
    so = {b: split_block(d) for b, d in _res_entries(orig_path).items()}
    sr = {b: split_block(d) for b, d in _res_entries(ref_path).items()}
    m = {}
    for b in sorted(set(so) & set(sr)):
        for idx, en in so[b].items():
            zh = sr[b].get(idx)
            if zh and zh != en:
                m[(b, idx)] = zh
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump({'%d#%d' % k: v for k, v in m.items()}, f,
                  ensure_ascii=False, indent=0)
    return m


def localize_block(block_id, data, mapping):
    """Return new block bytes with the mapped entries translated."""
    cur = split_block(data)
    changed = 0
    for idx in list(cur):
        zh = mapping.get((block_id, idx))
        if zh:
            cur[idx] = zh
            changed += 1
    if not changed:
        return data, 0
    return join_block(cur, 4), changed
