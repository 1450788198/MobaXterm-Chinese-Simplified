# -*- coding: utf-8 -*-
"""Delphi binary DFM (TPF0) reader + writer (writer only re-emits what it read)."""
import struct

VA_NULL, VA_LIST, VA_INT8, VA_INT16, VA_INT32 = 0, 1, 2, 3, 4
VA_EXTENDED, VA_STRING, VA_IDENT, VA_FALSE, VA_TRUE = 5, 6, 7, 8, 9
VA_BINARY, VA_SET, VA_LSTRING, VA_NIL, VA_COLLECTION = 10, 11, 12, 13, 14
VA_SINGLE, VA_CURRENCY, VA_DATE, VA_WSTRING, VA_INT64 = 15, 16, 17, 18, 19
VA_UTF8STRING, VA_DOUBLE = 20, 21


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def i8(self):
        v = struct.unpack_from('<b', self.d, self.p)[0]
        self.p += 1
        return v

    def i16(self):
        v = struct.unpack_from('<h', self.d, self.p)[0]
        self.p += 2
        return v

    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from('<q', self.d, self.p)[0]
        self.p += 8
        return v

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def peek(self):
        return self.d[self.p] if self.p < len(self.d) else 0

    def eof(self):
        return self.p >= len(self.d)


class Writer:
    """Serialises a parsed DFM back to the binary TPF0 form.

    STR_ENC is the byte encoding for vaString / vaLString values.  This build
    of MobaXterm is a non-Unicode (ANSI) Delphi target and the host system's
    ANSI code page is 936 (GBK), so GBK is the right choice; latin-1 is kept
    as a fallback for characters GBK cannot represent.
    """

    STR_ENC = 'gbk'

    def __init__(self, str_enc=None):
        if str_enc:
            self.STR_ENC = str_enc
        self.d = bytearray()

    def u8(self, v):
        self.d.append(v & 0xFF)

    def i16(self, v):
        self.d += struct.pack('<h', v)

    def i32(self, v):
        self.d += struct.pack('<i', v)

    def i64(self, v):
        self.d += struct.pack('<q', v)

    def raw(self, b):
        self.d += b

    def enc(self, s):
        if not isinstance(s, str):
            return s
        try:
            return s.encode(self.STR_ENC)
        except UnicodeEncodeError:
            return s.encode('latin1', 'replace')

    def lpstr(self, s):
        b = self.enc(s)
        self.u8(len(b))
        self.d += b

    def bytes(self):
        return bytes(self.d)


def lpstr(r):
    n = r.u8()
    return r.raw(n)


def widestr(r):
    """vaWString payload: int32 CHARACTER count, then count*2 bytes UTF-16LE."""
    n = r.i32()
    return r.raw(n * 2)


def read_value(r):
    t = r.u8()
    if t == VA_NULL:
        return t, None
    if t == VA_LIST:
        out = []
        while r.peek() != 0:
            out.append(read_value(r))
        r.u8()
        return t, out
    if t == VA_INT8:
        return t, r.i8()
    if t == VA_INT16:
        return t, r.i16()
    if t == VA_INT32:
        return t, r.i32()
    if t == VA_EXTENDED:
        return t, r.raw(10)
    if t in (VA_STRING, VA_IDENT):
        return t, lpstr(r).decode('latin1', 'replace')
    if t in (VA_FALSE, VA_TRUE, VA_NIL):
        return t, None
    if t == VA_BINARY:
        return t, r.raw(r.i32())
    if t == VA_SET:
        out = []
        while r.peek() != 0:
            out.append(lpstr(r).decode('latin1', 'replace'))
        r.u8()
        return t, out
    if t == VA_LSTRING:
        return t, r.raw(r.i32()).decode('latin1', 'replace')
    if t == VA_COLLECTION:
        items = []
        while r.peek() != 0:
            r.u8()                       # item marker (0x01 / 0x02)
            props = {}
            while r.peek() != 0:
                nm = lpstr(r).decode('latin1', 'replace')
                props[nm] = read_value(r)
            r.u8()                       # end of item
            items.append(props)
        r.u8()                           # end of collection
        return t, items
    if t == VA_SINGLE:
        return t, r.raw(4)
    if t == VA_CURRENCY:
        return t, r.i64()
    if t == VA_DATE:
        return t, r.raw(8)
    if t == VA_WSTRING:
        return t, widestr(r).decode('utf-16-le', 'replace')
    if t == VA_INT64:
        return t, r.i64()
    if t == VA_UTF8STRING:
        return t, lpstr(r).decode('utf-8', 'replace')
    if t == VA_DOUBLE:
        return t, r.raw(8)
    raise ValueError('unknown value type %d @ %d' % (t, r.p))


def write_value(w, t, v):
    w.u8(t)
    if t == VA_NULL:
        return
    if t == VA_LIST:
        for item in v:
            write_value(w, *item)
        w.u8(0)
        return
    if t == VA_INT8:
        w.u8(v)
        return
    if t == VA_INT16:
        w.i16(v)
        return
    if t == VA_INT32:
        w.i32(v)
        return
    if t == VA_EXTENDED:
        w.raw(v)
        return
    if t in (VA_STRING, VA_IDENT):
        w.lpstr(v)
        return
    if t in (VA_FALSE, VA_TRUE, VA_NIL):
        return
    if t == VA_BINARY:
        w.i32(len(v))
        w.raw(v)
        return
    if t == VA_SET:
        for s in v:
            w.lpstr(s)
        w.u8(0)
        return
    if t == VA_LSTRING:
        b = w.enc(v)
        w.i32(len(b))
        w.raw(b)
        return
    if t == VA_COLLECTION:
        for props in v:
            w.u8(0x01)
            for nm, (pt, pv) in props.items():
                w.lpstr(nm)
                write_value(w, pt, pv)
            w.u8(0)
        w.u8(0)
        return
    if t == VA_SINGLE:
        w.raw(v)
        return
    if t == VA_CURRENCY:
        w.i64(v)
        return
    if t == VA_DATE:
        w.raw(v)
        return
    if t == VA_WSTRING:
        b = v.encode('utf-16-le') if isinstance(v, str) else v
        w.i32(len(b) // 2)
        w.raw(b)
        return
    if t == VA_INT64:
        w.i64(v)
        return
    if t == VA_UTF8STRING:
        b = v.encode('utf-8') if isinstance(v, str) else v
        w.u8(len(b))
        w.raw(b)
        return
    if t == VA_DOUBLE:
        w.raw(v)
        return
    raise ValueError('unhandled write %d' % t)


def read_object(r, is_root=False):
    if is_root:
        sig = r.raw(4)
        assert sig == b'TPF0', 'bad signature %r' % sig
        prefix = b''
    elif r.peek() == 0xFF:
        prefix = r.raw(2)                                # ffFlags
    else:
        prefix = b''
    cls = lpstr(r).decode('latin1', 'replace')
    nm = lpstr(r).decode('latin1', 'replace')
    props = {}
    while r.peek() != 0:
        pname = lpstr(r).decode('latin1', 'replace')
        props[pname] = read_value(r)
    r.u8()                                            # end of properties
    children = []
    while r.peek() != 0:
        children.append(read_object(r))
    r.u8()                                            # end of children
    return {'class': cls, 'name': nm, 'prefix': prefix,
            'props': props, 'children': children}


def write_object(w, obj, is_root=False):
    if is_root:
        w.raw(b'TPF0')
    else:
        w.raw(obj.get('prefix', b''))
    w.lpstr(obj['class'])
    w.lpstr(obj['name'])
    for pname, (pt, pv) in obj['props'].items():
        w.lpstr(pname)
        write_value(w, pt, pv)
    w.u8(0)
    for ch in obj['children']:
        write_object(w, ch)
    w.u8(0)


def parse(data):
    r = Reader(data)
    return read_object(r, is_root=True)


def serialize(obj):
    w = Writer()
    write_object(w, obj, is_root=True)
    return w.bytes()
