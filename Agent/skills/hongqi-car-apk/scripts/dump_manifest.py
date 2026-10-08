#!/usr/bin/env python3
"""dump_manifest.py — 从 APK 中直接解析二进制 AndroidManifest.xml 的关键属性。

不依赖 apktool / androguard，纯 struct 解析，毫秒级返回。
输出：manifest 元素的全部属性（package / versionCode / versionName / compileSdkVersion 等）
"""
import struct
import sys
import zipfile

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT_TYPE = 0x0102
UTF8_FLAG = 0x000100

TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12


def _len8(buf, p):
    v = buf[p]
    if v & 0x80:
        return ((v & 0x7F) << 8) | buf[p + 1], p + 2
    return v, p + 1


def _len16(buf, p):
    v = struct.unpack_from("<H", buf, p)[0]
    if v & 0x8000:
        return ((v & 0x7FFF) << 16) | struct.unpack_from("<H", buf, p + 2)[0], p + 4
    return v, p + 2


def read_pool(buf):
    typ, hdr, size, sc, styc, flags, sstart, _ = struct.unpack_from("<HHIIIIII", buf, 8)
    assert typ == RES_STRING_POOL_TYPE, hex(typ)
    offs = struct.unpack_from(f"<{sc}I", buf, 8 + hdr)
    base = 8 + sstart
    out = []
    for o in offs:
        p = base + o
        if flags & UTF8_FLAG:
            _, p = _len8(buf, p)
            n, p = _len8(buf, p)
            out.append(buf[p:p + n].decode("utf-8", "replace"))
        else:
            n, p = _len16(buf, p)
            out.append(buf[p:p + 2 * n].decode("utf-16-le", "replace"))
    return out, size


def dump(axml):
    assert struct.unpack_from("<H", axml, 0)[0] == RES_XML_TYPE
    strings, pool_size = read_pool(axml)
    off = 8 + pool_size

    while off + 8 <= len(axml):
        ctype, chdr, csize = struct.unpack_from("<HHI", axml, off)
        if csize <= 0:
            break
        if ctype == RES_XML_START_ELEMENT_TYPE:
            name_idx = struct.unpack_from("<I", axml, off + 20)[0]
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, off + 24)
            el = strings[name_idx]
            # 属性表起始：ResXMLTree_node 固定 16 字节，attributeStart 以此为基准
            attrs = {}
            abase = off + 16 + attr_start
            for i in range(attr_count):
                a = abase + i * attr_size
                ans, aname, raw = struct.unpack_from("<III", axml, a)
                dsize, res0, dtype, ddata = struct.unpack_from("<HBBI", axml, a + 12)
                nm = strings[aname]
                if dtype == TYPE_STRING:
                    val = strings[ddata]
                elif dtype == TYPE_INT_BOOLEAN:
                    val = bool(ddata)
                elif dtype in (TYPE_INT_DEC, TYPE_INT_HEX):
                    val = ddata if dtype == TYPE_INT_DEC else hex(ddata)
                elif dtype == TYPE_REFERENCE:
                    val = f"@ref/0x{ddata:08x}"
                else:
                    val = f"<type 0x{dtype:02x}>"
                attrs[nm] = val
            return el, attrs, len(strings)
        off += csize
    return None, {}, len(strings)


def main():
    for path in sys.argv[1:]:
        print("=" * 72)
        print(path)
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            axml = z.read("AndroidManifest.xml")
            el, attrs, nstr = dump(axml)
            print(f"  根元素: {el}   字符串池: {nstr} 条")
            for k in ("package", "versionCode", "versionName", "compileSdkVersion",
                      "platformBuildVersionCode", "platformBuildVersionName",
                      "sharedUserId", "installLocation"):
                if k in attrs:
                    print(f"    {k:28s} = {attrs[k]}")
            print(f"  条目数: {len(names)}")
            dex = sorted(n for n in names if n.endswith(".dex"))
            print(f"  dex: {dex}")
            for n in names:
                if n.startswith("META-INF/") and n.upper().endswith((".SF", ".RSA", ".DSA", ".EC")):
                    print(f"  v1 签名文件: {n}")


if __name__ == "__main__":
    main()
