# -*- coding: utf-8 -*-
"""Patch code-level (CODE/DATA section) Delphi AnsiString constants.

Most of MobaXterm's UI lives in DFM resources, but the main toolbar captions,
the window title, sidebar section names and several runtime labels are plain
AnsiString constants inside the code segment.  This pass rewrites those in
place.

Safety model
------------
* Only an explicit ALLOW list of display-only strings is touched.  Everything
  that is an INI section/key name (Misc, Display, Passwords, ...), a
  lower-case value token (no / none / automatic / on-demand), an internal
  component name (HINT) or an external binary name (chmod, game ids) is
  deliberately excluded.
* The replacement is written as GBK; the AnsiString header length is updated to
  the new byte count and the remaining slack is zero-filled.  The total size of
  the constant never changes, so no offsets move.
* Strings that would grow beyond their original byte budget are skipped and
  reported.
"""
import os
import struct
import sys

SRC = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\build\MobaXterm_zh.exe'

# --- display-only strings we are allowed to rewrite in the code segment -----
ALLOW = {
    'Session': '会话', 'Servers': '服务器', 'Tools': '工具',
    'Sessions': '会话', 'View': '视图', 'Split': '分屏',
    'MultiExec': '多重执行', 'Tunneling': '隧道', 'Packages': '软件包',
    'Settings': '设置', 'Help': '帮助', 'X server': 'X 服务器',
    'Exit': '退出', 'Start': '开始', 'Stop': '停止',
    'Start local terminal': '打开本地终端',
    'New session': '新建会话', 'New tab': '新标签',
    'User sessions': '用户会话', 'Quick connect': '快速连接',
    'MobaXterm Professional': '魔霸终端 专业版',
    'Session name': '会话名称', 'Set title': '设置标题',
    'Rename tab': '重命名标签', 'New folder': '新建文件夹',
    'Terminal zoom': '终端放大', 'Terminal unzoom': '终端缩小',
    'Show/hide sidebar': '显示/隐藏侧边栏', 'Sidebar': '侧边栏',
    'Toolbar': '工具栏', 'Transparency': '透明度',
    'Recover previous sessions': '恢复之前的会话',
    'Start a new remote session': '启动新的远程会话',
    'Manage existing shared sessions': '管理已有共享会话',
    'Share these sessions with my team': '与我的团队共享这些会话',
    'Saved macros': '已保存的宏', 'Record new macro': '录制新宏',
    'Paste in terminal': '粘贴到终端',
    'Find in terminal': '在终端中查找', 'Find next': '查找下一个',
    'Fit to terminal': '适应终端',
    'Print terminal output': '打印终端输出',
    'Save terminal output': '保存终端输出',
    'Start scan': '开始扫描', 'List ports': '列出端口',
    'Tasks list': '任务列表', 'Shortkeys': '快捷键', 'Systray': '托盘',
    'Local clients': '本地客户端', 'Remote server': '远程服务器',
    'Server:': '服务器：', 'Folder name': '文件夹名称', 'Group:': '组：',    'This version is registered to': '本版本授权给：',
    'license': '许可',
    'Red': '红', 'Green': '绿', 'Yellow': '黄色', 'Blue': '蓝色',
    'Magenta': '品红', 'Cyan': '青色', 'White': '白色',
    'Underline': '下划线', 'Ligatures': '连字',
    'No proxy': '不使用代理',
    'Library to use for GSSAPI authentication': '用于 GSSAPI 身份验证的库',
    'Zoom in': '放大', 'Zoom out': '缩小',
    'Games': '游戏', 'Options': '选项', 'Warning': '警告',
    'Undo': '撤销', 'Redo': '重做', 'Find': '查找', 'Print': '打印',
    'Import': '导入', 'Upload': '上传', 'Save': '保存', 'Never': '从不',
    'Start MobaTextEditor': '启动 魔霸文本编辑器',
    'MobaXterm Customizer': '魔霸终端 定制器',
}

# never touched (documented, for the report)
DENY_REASON = {
    'ini section / key': ['Misc', 'Display', 'Passwords', 'Macros', 'Terminal',
                          'Advanced', 'Name', 'Type', 'Size', 'Port',
                          'Preview', 'Information', 'Credentials',
                          'Compression', 'Toolbar'],
    'value token': ['no', 'none', 'No', 'None', 'automatic', 'on-demand',
                    'shared folder', 'N/A', 'Yes'],
    'internal name': ['HINT'],
    'external binary': ['chmod', 'Sftp', 'SFTP', 'FTP', 'TFTP', 'HTTP', 'SSH',
                        'RDP', 'VNC', 'NFS', 'WSL', 'Xdmcp', 'Fvwm2', 'Greed',
                        'Nimesweeper', 'Ninvaders', 'Soliterm', 'Sudoku',
                        'Termwalk', 'Typespeed', 'Tcpdump', 'TextEdit',
                        'Iperf server', 'VNC server', 'Telnet', 'DirectDraw'],
}

SEC_NAMES = ('CODE', 'DATA')


def sections(B):
    e = struct.unpack_from('<I', B, 0x3C)[0]
    coff = e + 4
    nsec = struct.unpack_from('<H', B, coff + 2)[0]
    opt_size = struct.unpack_from('<H', B, coff + 16)[0]
    out = []
    for i in range(nsec):
        o = coff + 20 + opt_size + i * 40
        nm = B[o:o + 8].rstrip(b'\x00').decode('latin1')
        vsize, va, rsize, raw = struct.unpack_from('<IIII', B, o + 8)
        out.append((nm, va, vsize, raw, rsize))
    return out


def main():
    B = bytearray(open(SRC, 'rb').read())
    secs = sections(B)

    # functional identifiers that must stay byte-identical:
    #  - 0x5042dc..0x504350 : TopToolbarBtns default button-ID table
    #  - 0x5b5e4c..0x5b5e78 : 'Toolbar'/'Session' INI key names
    PROTECT = [(0x5042dc, 0x504350), (0x5b5e4c, 0x5b5e78)]

    def protected(off):
        return any(a <= off < b for a, b in PROTECT)

    wanted = {}
    for s, z in ALLOW.items():
        g = z.encode('gbk')
        wanted[s] = g

    patched = []
    too_long = []
    missing = []

    for s, g in wanted.items():
        raw_s = s.encode('latin1')
        # A Delphi constant is  dword(-1) | dword length | chars | NUL .
        # The stored length field is occasionally off by one in this build, so
        # match on the text itself, validate the header, and use the actual
        # distance to the terminating NUL as the writable budget.
        pos = 0
        found = 0
        while True:
            i = bytes(B).find(raw_s, pos)
            if i < 0:
                break
            pos = i + 1
            if i < 8:
                continue
            if protected(i):
                continue
            if bytes(B[i - 8:i - 4]) != b'\xff\xff\xff\xff':
                continue
            stored = struct.unpack_from('<I', B, i - 4)[0]
            end = i + len(raw_s)
            # the stored text occasionally carries trailing spaces before NUL
            while end < len(B) and end - (i + len(raw_s)) < 4 and B[end] == 0x20:
                end += 1
            if end >= len(B) or B[end] != 0 or stored > len(raw_s) + 8:
                continue
            # zero padding that follows the terminator is free to reuse
            zend = end
            while (zend + 1 < len(B) and zend - end < 4 and B[zend + 1] == 0
                   and zend + 1 + 1 < len(B)
                   and bytes(B[zend + 1:zend + 5]) != b'\x00\xff\xff\xff'):
                zend += 1
            sec = next((n for n, va, vs, raw, rs in secs
                        if raw <= i < raw + max(rs, 0)), None)
            if sec not in SEC_NAMES:
                continue
            found += 1
            budget = zend + 1 - i                   # translation + NUL
            if len(g) + 1 > budget:
                too_long.append((s, len(raw_s), len(g)))
                continue
            B[i:i + len(g)] = g
            B[i + len(g):zend + 1] = b'\x00' * (zend + 1 - i - len(g))
            struct.pack_into('<I', B, i - 4, len(g))
            patched.append((s, g.decode('gbk')))
        if found == 0:
            missing.append(s)

    # recompute the PE checksum: patch_code runs after localize.py, which
    # wrote a correct value, so any code edit would otherwise invalidate it
    e = struct.unpack_from('<I', B, 0x3C)[0]
    coff = e + 4
    opt = coff + 20
    magic = struct.unpack_from('<H', B, opt)[0]
    cs_off = opt + (64 if magic == 0x10B else 112)
    total = 0
    n = len(B)
    i = 0
    while i < n - 1:
        if not (cs_off <= i < cs_off + 4):
            total += struct.unpack_from('<H', B, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
        i += 2
    if n & 1:
        total += B[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total + n) & 0xFFFFFFFF
    struct.pack_into('<I', B, cs_off, total)
    print('checksum = 0x%x' % total)

    open(SRC, 'wb').write(bytes(B))
    print('code-level strings patched : %d occurrences' % len(patched))
    print('skipped (too long)         : %d' % len(too_long))
    print('not present in this build  : %s' % (missing or 'none'))
    for s, a, b in sorted(set(too_long)):
        print('   ! %-34s %d -> %d bytes' % (s, a, b))


if __name__ == '__main__':
    main()
