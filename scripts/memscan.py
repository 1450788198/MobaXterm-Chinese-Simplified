# -*- coding: utf-8 -*-
"""Scan the running localized MobaXterm for ASCII 'Tunneling' and classify
every hit: which PE section (read from the live module) or heap."""
import ctypes
import ctypes.wintypes as w
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mz
from clean_run import kill_all

RUN = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\run_zh'
k32 = ctypes.WinDLL('kernel32')

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


def read_mem(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return buf.raw[:got.value]
    return None


def regions(h):
    """Yield (base, size) of committed readable regions."""
    class MBI(ctypes.Structure):
        _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                    ('AllocationProtect', w.DWORD), ('RegionSize', ctypes.c_size_t),
                    ('State', w.DWORD), ('Protect', w.DWORD), ('Type', w.DWORD)]
    addr = 0
    mbi = MBI()
    while addr < 0x7FFF0000:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        size = mbi.RegionSize or 0x1000
        if mbi.State == 0x1000 and mbi.Protect not in (0, 1):   # MEM_COMMIT, readable
            yield mbi.BaseAddress, size, mbi.Type, mbi.Protect
        addr = (mbi.BaseAddress or addr) + size
        addr = (addr + 0xFFFF) & ~0xFFFF


def main():
    kill_all()
    mz.RUN = RUN
    mz.OUT = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\analysis'
    pid, main_h = mz.launch()
    time.sleep(2)

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    print('[*] handle', h)

    # module sections from memory
    base = 0x400000
    hdr = read_mem(h, base, 0x1000)
    e = struct.unpack_from('<I', hdr, 0x3C)[0]
    coff = e + 4
    nsec = struct.unpack_from('<H', hdr, coff + 2)[0]
    opt_size = struct.unpack_from('<H', hdr, coff + 16)[0]
    opt = coff + 20
    secs = []
    for i in range(nsec):
        o = coff + 20 + opt_size + i * 40
        nm = hdr[o:o + 8].rstrip(b'\x00').decode('latin1')
        vsize, va, rsize, raw = struct.unpack_from('<IIII', hdr, o + 8)
        secs.append((nm, base + va, vsize))
    img_end = base + struct.unpack_from('<I', hdr, opt + 56)[0]

    def classify(a):
        if base <= a < img_end:
            for nm, sva, vsz in secs:
                if sva <= a < sva + max(vsz, 1):
                    return 'section:' + nm
            return 'module-head'
        return 'heap'

    needle = b'Tunneling'
    hits = []
    for ba, size, mtype, protect in regions(h):
        if size > 64 * 1024 * 1024:
            continue
        data = read_mem(h, ba, size)
        if not data:
            continue
        off = data.find(needle)
        while off != -1:
            hits.append(ba + off)
            off = data.find(needle, off + 1)
    print('[*] %d hits for %r' % (len(hits), needle))
    for a in hits:
        cls = classify(a)
        ctx = read_mem(h, a - 48, 80) or b''
        printable = ''.join(chr(c) if 32 <= c < 127 else '.' for c in ctx)
        print('   %#010x %-18s %s' % (a, cls, printable))
    return pid, h, hits, classify


if __name__ == '__main__':
    main()
    time.sleep(3)
