# -*- coding: utf-8 -*-
"""
One-shot MobaXterm GUI driver.  The child process dies when the invoking shell
exits, so launch / interact / capture must happen inside a single run.

  mz.py shot  <out.png>                      launch, capture main form
  mz.py seq   <out_prefix> <x,y[;x,y...]>    launch, then click each point and
                                             capture the full screen after each
                                             (coordinates are RELATIVE to the
                                              main form's top-left corner)
"""
import ctypes
import ctypes.wintypes as w
import subprocess
import sys
import time
import os
from PIL import Image

u32 = ctypes.WinDLL('user32', use_last_error=True)
g32 = ctypes.WinDLL('gdi32', use_last_error=True)

try:
    ctypes.WinDLL('shcore').SetProcessDpiAwareness(2)
except Exception:
    u32.SetProcessDPIAware()

E = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

RUN = os.environ.get('MZ_RUN', r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\run_patched')
OUT = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\shots_patched'
os.makedirs(OUT, exist_ok=True)


def ctitle(h):
    n = u32.GetWindowTextLengthW(h)
    if n <= 0:
        return ''
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value


def ccls(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value


def crect(h):
    r = w.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def windows_of(pid):
    res = []

    def cb(h, lp):
        q = w.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value == pid:
            res.append(h)
        return True

    u32.EnumWindows(E(cb), 0)
    return res


def find_main(pid, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for h in windows_of(pid):
            if ccls(h) == 'TMobaXtermForm' and u32.IsWindowVisible(h):
                l, t, cx, cy = crect(h)
                if cx > 300:
                    return h
        time.sleep(1.0)
    return None


def grab(hwnd, path):
    l, t, cx, cy = crect(hwnd)
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, cx, cy)
    g32.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', w.DWORD), ('biWidth', w.LONG), ('biHeight', w.LONG),
                    ('biPlanes', w.WORD), ('biBitCount', w.WORD),
                    ('biCompression', w.DWORD), ('biSizeImage', w.DWORD),
                    ('biXPelsPerMeter', w.LONG), ('biYPelsPerMeter', w.LONG),
                    ('biClrUsed', w.DWORD), ('biClrImportant', w.DWORD)]
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = cx
    bi.biHeight = -cy
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(cx * cy * 4)
    g32.GetDIBits(mdc, bmp, 0, cy, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    Image.frombuffer('RGBA', (cx, cy), buf, 'raw', 'BGRA', 0, 1).convert('RGB').save(path)
    return cx, cy


def screen(path):
    W = u32.GetSystemMetrics(0)
    H = u32.GetSystemMetrics(1)
    hdc = u32.GetDC(0)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, W, H)
    g32.SelectObject(mdc, bmp)
    g32.BitBlt(mdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', w.DWORD), ('biWidth', w.LONG), ('biHeight', w.LONG),
                    ('biPlanes', w.WORD), ('biBitCount', w.WORD),
                    ('biCompression', w.DWORD), ('biSizeImage', w.DWORD),
                    ('biXPelsPerMeter', w.LONG), ('biYPelsPerMeter', w.LONG),
                    ('biClrUsed', w.DWORD), ('biClrImportant', w.DWORD)]
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = W
    bi.biHeight = -H
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(W * H * 4)
    g32.GetDIBits(mdc, bmp, 0, H, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(0, hdc)
    im = Image.frombuffer('RGBA', (W, H), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
    im.save(path)
    return im


def click(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    u32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.35)


def focus(h):
    """Reliable foreground steal via AttachThreadInput."""
    k32 = ctypes.WinDLL('kernel32')
    my = k32.GetCurrentThreadId()
    fg = u32.GetForegroundWindow()
    fg_t = u32.GetWindowThreadProcessId(fg, None)
    app_t = u32.GetWindowThreadProcessId(h, None)
    u32.ShowWindow(h, 9)
    if fg and fg_t:
        u32.AttachThreadInput(my, fg_t, True)
    u32.AttachThreadInput(my, app_t, True)
    u32.SetForegroundWindow(h)
    u32.BringWindowToTop(h)
    u32.SetActiveWindow(h)
    u32.SetFocus(h)
    if fg and fg_t:
        u32.AttachThreadInput(my, fg_t, False)
    u32.AttachThreadInput(my, app_t, False)
    time.sleep(0.7)
    now = u32.GetForegroundWindow()
    print('[*] foreground after steal: %#x (target %#x) match=%s' % (now, h, now == h))


def launch():
    p = subprocess.Popen([os.path.join(RUN, 'MobaXterm.exe')], cwd=RUN)
    pid = p.pid
    print('[*] pid %d' % pid)
    main = find_main(pid)
    if not main:
        print('[!] main form not found')
        sys.exit(2)
    print('[*] main = %#x  rect=%s' % (main, crect(main)))
    return pid, main


def main():
    cmd = sys.argv[1]
    if cmd == 'shot':
        pid, h = launch()
        time.sleep(2)
        print('[*] captured', grab(h, os.path.join(OUT, sys.argv[2])))
        time.sleep(20)
    elif cmd == 'seq':
        prefix = sys.argv[2]
        pts = [tuple(int(v) for v in p.split(',')) for p in sys.argv[3].split(';')]
        pid, h = launch()
        time.sleep(2)
        grab(h, os.path.join(OUT, prefix + '_0_main.png'))
        focus(h)
        time.sleep(0.5)
        for i, (dx, dy) in enumerate(pts, 1):
            l, t, cx, cy = crect(h)          # re-read: the form may reposition itself
            click(l + dx, t + dy)
            p = os.path.join(OUT, '%s_%d.png' % (prefix, i))
            screen(p)
            print('[*] click #%d abs=(%d,%d) rect=%s -> %s' % (i, l + dx, t + dy, crect(h), p))
        print('[*] windows after clicks:')
        for w_ in windows_of(pid):
            if u32.IsWindowVisible(w_):
                print('      %#x %-22s %r %s' % (w_, ccls(w_), ctitle(w_), crect(w_)))
        time.sleep(20)


if __name__ == '__main__':
    main()
