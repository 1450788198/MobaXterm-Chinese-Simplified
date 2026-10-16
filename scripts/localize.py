# -*- coding: utf-8 -*-
"""
MobaXterm Chinese localiser.

Reads the Professional-unlocked exe produced by patch_pro.py, rewrites the
Delphi DFM (TPF0) RCDATA resources with Chinese captions/labels/hints, rebuilds
the whole PE resource directory into a brand-new section and repoints
DataDirectory[2] at it.  The original .rsrc section is left in place but
becomes unreferenced.
"""
import os
import json
import struct
from collections import OrderedDict

import dfm
import dfm_probe
import rtres
import trans_zh

# --- RT_STRING (type 6) table inherited from the reference localisation -----
REF_EXE = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\ref\MobaXterm_chs_24.3.exe'
ORIG_EXE = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\files\MobaXterm.exe'
try:
    RT = rtres.build_map(ORIG_EXE, REF_EXE)
except Exception:
    RT = {}

SRC = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\build\MobaXterm.exe'
OUTDIR = r'C:\Users\yanfa\WorkBuddy\2026-10-16-14-08-23\mobaxterm\build'
OUT = os.path.join(OUTDIR, 'MobaXterm_zh.exe')

IMAGEBASE = 0x400000
FILE_ALIGN = 0x200
SEC_ALIGN = 0x1000

# ---------------------------------------------------------------------------
D = {
    'OK': '确定', 'Cancel': '取消', 'Close': '关闭', 'Yes': '是', 'No': '否',
    'Abort': '中止', 'Retry': '重试', 'Ignore': '忽略', 'Help': '帮助',
    'Apply': '应用', 'Save': '保存', 'Save as...': '另存为…',
    'Open': '打开', 'Browse...': '浏览…', 'Browse': '浏览',
    'Execute': '执行', 'Refresh': '刷新', 'Duplicate': '复制副本',
    'Delete': '删除', 'Rename': '重命名', 'Copy': '复制', 'Paste': '粘贴',
    'Cut': '剪切', 'Undo': '撤销', 'Redo': '重做', 'Find': '查找',
    'Replace': '替换', 'Select all': '全选', 'Clear': '清空',
    'Edit': '编辑', 'Add': '添加', 'Remove': '移除', 'New': '新建',
    'Import': '导入', 'Export': '导出', 'Load': '加载', 'Reload': '重新载入',
    'Reset': '重置', 'Defaults': '默认值', 'Restore defaults': '恢复默认',
    'Preview': '预览', 'Test': '测试', 'Start': '启动', 'Stop': '停止',
    'Pause': '暂停', 'Resume': '继续', 'Restart': '重启', 'Run': '运行',
    'Quit': '退出', 'Exit': '退出', 'Back': '上一步', 'Next': '下一步',
    'Finish': '完成', 'Done': '完成', 'Continue': '继续',
    'Search': '搜索', 'Sort': '排序', 'Print': '打印',
    'Properties': '属性', 'Settings': '设置', 'Options': '选项',
    'Preferences': '偏好设置', 'Configuration': '配置',
    'Advanced': '高级', 'General': '常规', 'Security': '安全',
    'Display': '显示', 'Appearance': '外观', 'Terminal': '终端',
    'Sessions': '会话', 'Session': '会话', 'View': '查看',
    'Tools': '工具', 'Macros': '宏', 'Games': '游戏', 'X server': 'X 服务器',
    'About': '关于', 'About MobaXterm': '关于 MobaXterm',
    'Documentation': '文档', 'Check for updates': '检查更新',
    'View MobaXterm log file': '查看 MobaXterm 日志文件',
    'New tab': '新建标签页', 'Fullscreen': '全屏',
    'Detach tab': '分离标签页', 'Local terminal': '本地终端',
    'New session': '新建会话', 'User sessions': '用户会话',
    'Start local terminal': '启动本地终端',
    'Select your favorite theme': '选择您喜欢的主题',
    'Light': '浅色', 'Dark': '深色',
    'Quick connect...': '快速连接…',
    'Server output': '服务器输出', 'Stop server after': '此时间后停止服务器',
    'seconds': '秒', 'Seconds': '秒', 'Port ': '端口 ', 'Port: ': '端口：',
    'Remote host *': '远程主机 *', 'Username ': '用户名 ',
    'Password ': '密码 ', 'Login: ': '登录名：',
    'Listening port ': '监听端口 ',
    'Create or manage credentials': '创建或管理凭据',
    'Abort file transfer': '中止文件传输',
    'Session settings': '会话设置',
    'MobaXterm Configuration': 'MobaXterm 配置',
    'Basic SSH settings': 'SSH 基本设置',
    'Advanced SSH settings': 'SSH 高级设置',
    'Network settings': '网络设置',
    'Bookmark settings': '书签设置',
    'Terminal settings': '终端设置',
    'X11 settings': 'X11 设置',
    'Serial settings': '串口设置',
    'VNC settings': 'VNC 设置',
    'FTP settings': 'FTP 设置',
    'RDP settings': 'RDP 设置',
    'Choose a session template': '选择会话模板',
    'Session name': '会话名称',
    'Terminal shell': '终端 Shell',
    'Copyright': '版权所有',
    'Special thanks to...': '特别感谢…',
    'Professional Edition': '专业版',
    'Home Edition': '家庭版',
    'Educational Edition': '教育版',
    'license': '授权',
    'This version is registered to': '本版本授权给',
    'Click here for more information': '点击此处查看更多信息',
    'Homepage': '主页', 'E-Mail': '电子邮件', 'Changelog': '更新日志',
    'Updates': '更新',
    'Warning': '警告', 'Error': '错误', 'Information': '信息',
    'Confirm': '确认', 'Question': '提问',
}

UI_PROPS = {'Caption', 'Text', 'Hint', 'Title', 'BoundLabel.Caption',
            'GroupName', 'DisplayLabel', 'EditLabel.Caption', 'HoverCaption',
            'AddedTitle.Caption'}

# merge the extended dictionary
D.update(trans_zh.EXACT)

# exact-match table for the long tail (keys carry significant padding spaces)
_trans_map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'trans_map.json')
if os.path.exists(_trans_map_path):
    with open(_trans_map_path, encoding='utf-8') as _f:
        D.update(json.load(_f))

# ---- highest priority: human-curated map mined from a reference
# Chinese localisation of MobaXterm (aligned form-by-form, property-by-property)
R = {}
_ref_map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'ref_map.json')
if os.path.exists(_ref_map_path):
    with open(_ref_map_path, encoding='utf-8') as _f:
        R = json.load(_f)

# strings that must never have a brand substituted into them (filenames,
# filters, URLs, format specs, ...)
_BRAND_GUARD = ('|', '://', '.exe', '*.', '\\', '%', '.plugin', '.ini',
                '.txt', '.sh', '.bash', '.ksh', '.mxt')

LATIN_UI_FONTS = {'Arial', 'MS Sans Serif', 'Tahoma', 'Verdana',
              'Segoe UI', 'Trebuchet MS', 'Calibri', 'Times New Roman'}
CJK_FONT = 'Microsoft YaHei'

NEVER = {'Font.Name', 'BoundLabel.Font.Name', 'HoverFont.Name',
         'AddedTitle.Font.Name', 'SkinData.SkinSection', 'Name',
         'HelpKeyword', 'Root', 'DefaultExt', 'Filter', 'FileName',
         'URL', 'PasswordChar', 'Suffix', 'DisplayFormat', 'SoftwareName'}


def brand_safe(s):
    """brand() but never inside filenames, filters, URLs or format specs."""
    if any(g in s for g in _BRAND_GUARD):
        return s
    return trans_zh.brand(s)


def translate(s):
    """Reference map -> long-tail map -> exact table -> brand+phrase fallback."""
    if s in R:                      # human-curated reference wins
        return brand_safe(R[s])
    if s in D:                      # raw first: keep padding spaces intact
        return D[s]
    v = s.strip()
    if v in R:
        return brand_safe(R[v])
    if v in D:
        return D[v]
    if '\n' in s or '\r' in s:
        parts = s.replace('\r\n', '\n').split('\n')
        if any(p.strip() in D or p.strip() in R for p in parts):
            out = []
            for p in parts:
                q = p.strip()
                if q in R:
                    out.append(R[q])
                elif q in D:
                    out.append(D[q])
                else:
                    out.append(p)
            return '\n'.join(out)
    t = trans_zh.phrase(trans_zh.brand(s))
    if t != s:
        return t
    return None


def localize_object(obj, stats):
    """Translate visible captions and switch Latin UI fonts to a CJK font."""
    props = obj['props']

    # --- font swap so GBK text actually renders --------------------------
    fn = props.get('Font.Name')
    if fn and fn[0] == dfm.VA_STRING and isinstance(fn[1], str) and \
            fn[1].strip() in LATIN_UI_FONTS:
        props['Font.Name'] = (dfm.VA_STRING, CJK_FONT)
        # Font.Charset is an IDENT property (TFontCharset), never a string
        props['Font.Charset'] = (dfm.VA_IDENT, 'GB2312_CHARSET')
        stats[2] += 1

    for pname, (pt, pv) in list(props.items()):
        if pt != dfm.VA_STRING or not isinstance(pv, str) or pv in ('-', '', '*'):
            continue
        if pname in NEVER:
            continue
        base = pname.split('.')[-1]
        if pname not in UI_PROPS and base not in ('Caption', 'Text', 'Hint', 'Title'):
            continue
        t = translate(pv)
        if t is not None:
            obj['props'][pname] = (pt, t)
            stats[0] += 1
    for ch in obj['children']:
        localize_object(ch, stats)


def pe_checksum(data, checksum_off):
    total = 0
    n = len(data)
    for i in range(0, n - 1, 2):
        if checksum_off <= i < checksum_off + 4:
            continue
        total += struct.unpack_from('<H', data, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
    if n & 1:
        total += data[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def main():
    B = bytearray(open(SRC, 'rb').read())

    e_lfanew = struct.unpack_from('<I', B, 0x3C)[0]
    coff = e_lfanew + 4
    nsec = struct.unpack_from('<H', B, coff + 2)[0]
    opt_size = struct.unpack_from('<H', B, coff + 16)[0]
    opt = coff + 20
    size_of_image_off = opt + 56
    checksum_off = opt + 64
    datadir = opt + 96
    rsrc_rva, rsrc_size = struct.unpack_from('<II', B, datadir + 2 * 8)
    sec_tab = opt + opt_size

    secs = []
    for i in range(nsec):
        o = sec_tab + i * 40
        vsize, va, rsize, raw = struct.unpack_from('<IIII', B, o + 8)
        secs.append((va, max(vsize, rsize), raw, o))

    def raw_of(rva):
        for va, sz, raw, ho in secs:
            if va <= rva < va + sz:
                return raw + (rva - va)
        return None

    root_raw = raw_of(rsrc_rva)
    assert root_raw is not None

    # ---------------- collect + localise ---------------------------------
    stats = [0, 0, 0, 0]   # strings / forms / font swaps / RT_STRING strings
    entries = []
    skipped = []

    def read_dir(off, path):
        chars, ts, maj, minr, nname, nid = struct.unpack_from('<IIHHHH', B, off)
        for i in range(nname + nid):
            eo = off + 16 + i * 8
            nameid, offs = struct.unpack_from('<II', B, eo)
            if nameid & 0x80000000:
                so = root_raw + (nameid & 0x7FFFFFFF)
                ln = struct.unpack_from('<H', B, so)[0]
                nm = B[so + 2:so + 2 + ln * 2].decode('utf-16-le')
            else:
                nm = nameid
            if offs & 0x80000000:
                read_dir(root_raw + (offs & 0x7FFFFFFF), path + [nm])
            else:
                de = root_raw + (offs & 0x7FFFFFFF)
                dva, dsz, cp, rv = struct.unpack_from('<IIII', B, de)
                fo = raw_of(dva)
                data = bytes(B[fo:fo + dsz])
                typ, nmz = path[0], path[1]
                if typ == 6 and RT:
                    try:
                        data, n = rtres.localize_block(int(nmz), data, RT)
                        stats[3] += n
                    except Exception as ex:
                        skipped.append(('RT_STRING#%s' % nmz, str(ex)))
                if typ == 10 and isinstance(nmz, str) and data[:4] == b'TPF0':
                    import os as _os
                    if _os.environ.get('MZ_NOLOC'):
                        pass                      # bisect: rebuild only
                    else:
                        try:
                            obj = dfm.parse(data)
                            localize_object(obj, stats)
                            data = dfm.serialize(obj)
                            stats[1] += 1
                        except Exception as ex:
                            skipped.append((nmz, str(ex)))
                entries.append((typ, nmz, rv, data))

    read_dir(root_raw, [])
    for s in skipped:
        print('    [skip] %s: %s' % s)
    print('[*] %d resource entries, %d DFM forms localised, %d strings translated, '
          '%d RT_STRING strings localised'
          % (len(entries), stats[1], stats[0], stats[3]))

    # ---------------- new section RVA ------------------------------------
    last = max(secs, key=lambda s: s[0] + s[1])
    new_rva = (last[0] + last[1] + SEC_ALIGN - 1) & ~(SEC_ALIGN - 1)
    new_va = IMAGEBASE + new_rva
    print('[*] new resource section RVA=%#x VA=%#x' % (new_rva, new_va))

    # ---------------- build resource blob --------------------------------
    tree = OrderedDict()
    for tk, nk, lang, data in entries:
        tree.setdefault(tk, OrderedDict()).setdefault(nk, OrderedDict())[lang] = data

    pool = bytearray()

    # lay out the directory levels first; the string pool follows them
    n_type = len(tree)
    q = 16 + 8 * n_type
    lvl1_pos = {}
    for tk in tree:
        lvl1_pos[tk] = q
        q += 16 + 8 * len(tree[tk])
    lvl2_pos = {}
    for tk in tree:
        for nk in tree[tk]:
            lvl2_pos[(tk, nk)] = q
            q += 16 + 8 * len(tree[tk][nk])
    hdr_size = q
    pool_start = hdr_size
    name_off = {}

    def pool_add2(s):
        off = pool_start + len(pool)
        pool.extend(struct.pack('<H', len(s)))
        pool.extend(s.encode('utf-16-le'))
        return off

    for tk, sub in tree.items():
        if isinstance(tk, str) and tk not in name_off:
            name_off[tk] = pool_add2(tk)
        for nk in sub:
            if isinstance(nk, str) and nk not in name_off:
                name_off[nk] = pool_add2(nk)

    while len(pool) % 4:                     # keep blobs DWORD aligned
        pool.append(0)
    dir_end = pool_start + len(pool)
    blobs = bytearray()
    data_ent = {}
    for tk in tree:
        for nk in tree[tk]:
            for lang, data in tree[tk][nk].items():
                data_ent[(tk, nk, lang)] = (dir_end + len(blobs), len(data))
                blobs.extend(data)
                while len(blobs) % 4:
                    blobs.append(0)
    # data-entry records come after the blobs
    de_base = dir_end + len(blobs)
    de_bytes = 16 * len(data_ent)
    total = de_base + de_bytes
    print('[*] resource blob: hdr=%d pool=%d blobs=%d de=%d total=%d'
          % (hdr_size, len(pool), len(blobs), de_bytes, total))

    out = bytearray(total)

    # data-entry record index (stable ordering)
    de_index = {key: i for i, key in enumerate(data_ent)}

    def wr_dir(off, items):
        # PE spec: named entries first (case-insensitive ascending), then IDs
        items = sorted(items, key=lambda kv: (0, kv[0].upper()) if isinstance(kv[0], str)
                       else (1, kv[0]))
        nn = sum(1 for k, _ in items if isinstance(k, str))
        ni = len(items) - nn
        struct.pack_into('<IIHHHH', out, off, 0, 0, 4, 0, nn, ni)
        p = off + 16
        for namekey, val in items:
            if isinstance(namekey, str):
                struct.pack_into('<I', out, p, 0x80000000 | name_off[namekey])
            else:
                struct.pack_into('<I', out, p, namekey & 0x7FFFFFFF)
            struct.pack_into('<I', out, p + 4, val)
            p += 8

    items0 = [(tk, 0x80000000 | lvl1_pos[tk]) for tk in tree]
    out[pool_start:pool_start + len(pool)] = pool      # <-- string-name pool
    wr_dir(0, items0)
    for tk, sub in tree.items():
        wr_dir(lvl1_pos[tk], [(nk, 0x80000000 | lvl2_pos[(tk, nk)]) for nk in sub])
        for nk, langs in sub.items():
            wr_dir(lvl2_pos[(tk, nk)],
                   [(lang, de_base + de_index[(tk, nk, lang)] * 16) for lang in langs])

    # data-entry records + blob bytes
    for (tk, nk, lang), (do, dsz) in data_ent.items():
        i = de_index[(tk, nk, lang)]
        struct.pack_into('<IIII', out, de_base + i * 16, new_rva + do, dsz, 0, 0)
        out[do:do + dsz] = blobs[do - dir_end:do - dir_end + dsz]

    # ---------------- append section -------------------------------------
    new_raw = (len(B) + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
    pad = new_raw - len(B)
    if pad:
        B.extend(b'\x00' * pad)
    payload = bytes(out)
    rawsz = (len(payload) + FILE_ALIGN - 1) & ~(FILE_ALIGN - 1)
    B.extend(payload)
    if rawsz > len(payload):
        B.extend(b'\x00' * (rawsz - len(payload)))

    o = sec_tab + nsec * 40
    assert o + 40 <= struct.unpack_from('<I', B, opt + 60)[0], 'no header room'
    B[o:o + 8] = b'.rscn\x00\x00\x00'
    struct.pack_into('<IIII', B, o + 8, len(payload), new_rva, rawsz, new_raw)
    B[o + 24:o + 36] = b'\x00' * 12
    struct.pack_into('<I', B, o + 36, 0x40000040)      # R | CNT_INITIALIZED_DATA
    struct.pack_into('<H', B, coff + 2, nsec + 1)
    struct.pack_into('<I', B, size_of_image_off,
                     ((new_rva + len(payload) + SEC_ALIGN - 1) // SEC_ALIGN) * SEC_ALIGN)
    struct.pack_into('<II', B, datadir + 2 * 8, new_rva, len(payload))

    struct.pack_into('<I', B, checksum_off, 0)
    csum = pe_checksum(bytes(B), checksum_off)
    struct.pack_into('<I', B, checksum_off, csum)

    os.makedirs(OUTDIR, exist_ok=True)
    open(OUT, 'wb').write(bytes(B))
    print('[*] wrote %s (%d bytes), checksum %#x' % (OUT, len(B), csum))



if __name__ == '__main__':
    main()
