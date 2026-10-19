# -*- coding: utf-8 -*-
"""Enumerate / dump Delphi DFM (TPF0) RCDATA resources from the patched exe."""
import struct
import sys

P = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\build\MobaXterm.exe'
B = open(P, 'rb').read()


def enum_resources():
    """Walk the PE resource directory; yield (type, name, lang, rva, size, fileoff)."""
    e_lfanew = struct.unpack_from('<I', B, 0x3C)[0]
    coff = e_lfanew + 4
    nsec = struct.unpack_from('<H', B, coff + 2)[0]
    opt_size = struct.unpack_from('<H', B, coff + 16)[0]
    opt = coff + 20
    rsrc_rva, rsrc_size = struct.unpack_from('<II', B, opt + 96 + 2 * 8)
    secs = []
    for i in range(nsec):
        o = coff + 20 + opt_size + i * 40
        vsize, va, rsize, raw = struct.unpack_from('<IIII', B, o + 8)
        secs.append((va, max(vsize, rsize), raw))
    raw_of = lambda rva: next((raw + (rva - va) for va, sz, raw in secs
                               if va <= rva < va + sz), None)
    root = raw_of(rsrc_rva)
    assert root is not None, 'cannot map resource RVA'

    def dirname(v):
        if v & 0x80000000:
            o = root + (v & 0x7FFFFFFF)
            ln = struct.unpack_from('<H', B, o)[0]
            return B[o + 2:o + 2 + ln * 2].decode('utf-16-le')
        return v

    def walk(off, level, path):
        """off = file offset of a directory; path = list of (kind, name)."""
        chars, ts, maj, minr, nname, nid = struct.unpack_from('<IIHHHH', B, off)
        for i in range(nname + nid):
            eo = off + 16 + i * 8
            nameid, offs = struct.unpack_from('<II', B, eo)
            nm = dirname(nameid)
            if offs & 0x80000000:                      # subdirectory
                yield from walk(root + (offs & 0x7FFFFFFF), level + 1, path + [nm])
            else:                                      # data entry
                de = root + (offs & 0x7FFFFFFF)
                dva, dsz, cp, rv = struct.unpack_from('<IIII', B, de)
                yield (path, nm, dva, dsz, raw_of(dva))

    for path, lang, dva, dsz, fo in walk(root, 0, []):
        # path = [type, name]
        t = path[0] if len(path) > 0 else None
        nm = path[1] if len(path) > 1 else None
        yield (nm, t, lang, dva, dsz, fo)


if __name__ == '__main__':
    res = list(enum_resources())
    print('total resource data entries:', len(res))
    tpf0 = [(n, t, l, dva, dsz, fo) for (n, t, l, dva, dsz, fo) in res
            if t == 10 and fo is not None and B[fo:fo + 4] == b'TPF0']
    print('TPF0 (DFM) RCDATA entries:', len(tpf0))
    for n, t, l, dva, dsz, fo in tpf0[:20]:
        print('   name=%-24s size=%-8d rva=%#x' % (n, dsz, dva))
    print()
    print('=== types present ===')
    from collections import Counter
    print(Counter(str(t) for _, t, _, _, _, _ in res).most_common(12))
    print()
    # dump the first DFM
    if tpf0:
        n, t, l, dva, dsz, fo = tpf0[0]
        print('=== raw head of %s (%d bytes) ===' % (n, min(dsz, 400)))
        print(B[fo:fo + 400].hex(' '))
        print()
        print(B[fo:fo + 200])
