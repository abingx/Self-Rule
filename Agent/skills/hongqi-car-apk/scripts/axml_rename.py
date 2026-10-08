#!/usr/bin/env python3
"""
axml_rename.py — 原地修改 APK 中二进制 AndroidManifest.xml 的 applicationId(package)。

设计目标：把改动面压到最小。
  * 只替换清单里 package 属性所引用的那一个字符串条目；
  * 不改动 dex / resources.arsc / 原生库 / 其他任何清单属性；
  * 重新写出字符串池与 chunk 尺寸，支持任意长度的新包名。

用法:
  python3 axml_rename.py <src.apk> <dst.apk> <new.package.name> [--list]
"""
import struct
import sys
import zipfile

UTF8_FLAG = 0x000100
RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003


def _align4(n: int) -> int:
    return (n + 3) & ~3


def _read_len8(buf: bytes, p: int) -> int:
    """UTF-8 字符串的长度的 1/2 字节编码。"""
    v = buf[p]
    if v & 0x80:
        return ((v & 0x7F) << 8) | buf[p + 1], p + 2
    return v, p + 1


def _read_len16(buf: bytes, p: int) -> int:
    v = struct.unpack_from("<H", buf, p)[0]
    if v & 0x8000:
        v2 = struct.unpack_from("<H", buf, p + 2)[0]
        return ((v & 0x7FFF) << 16) | v2, p + 4
    return v, p + 2


class AxmlStringPool:
    """解析并重建 AXML 的全局字符串池（chunk type 0x0001）。"""

    def __init__(self, buf: bytes):
        self.buf = buf
        (self.type, self.header_size, self.size, self.string_count,
         self.style_count, self.flags, strings_start, styles_start) = struct.unpack_from(
            "<HHIIIIII", buf, 8)
        if self.type != RES_STRING_POOL_TYPE:
            raise ValueError(f"非字符串池 chunk: 0x{self.type:04x}")
        if self.header_size != 0x1C:
            raise ValueError(f"非预期 headerSize: {self.header_size}")
        self.strings_start = strings_start
        self.styles_start = styles_start

        self.offsets = list(struct.unpack_from(
            f"<{self.string_count}I", buf, 8 + self.header_size))
        self.style_offsets = list(struct.unpack_from(
            f"<{self.style_count}I", buf, 8 + self.header_size + 4 * self.string_count)
        ) if self.style_count else []

        base = 8 + self.strings_start
        self.limit = base + (self.size - self.strings_start)
        self.strings = [self._decode(base + o) for o in self.offsets]
        # 样式数据区域原样保留
        self.tail = buf[8 + self.size:]

    def _decode(self, p: int) -> str:
        buf = self.buf
        if self.flags & UTF8_FLAG:
            _, p = _read_len8(buf, p)          # 字符数，不使用
            nbytes, p = _read_len8(buf, p)
            raw = buf[p:p + nbytes]
            return raw.decode("utf-8", "replace")
        nchars, p = _read_len16(buf, p)
        raw = buf[p:p + 2 * nchars]
        return raw.decode("utf-16-le", "replace")

    def _encode(self, s: str) -> bytes:
        out = bytearray()
        if self.flags & UTF8_FLAG:
            raw = s.encode("utf-8")
            nchars = len(s)
            for v in (nchars, len(raw)):
                if v & 0x80:
                    out += bytes([0x80 | (v >> 8), v & 0xFF])
                else:
                    out.append(v)
            out += raw + b"\x00"
        else:
            raw = s.encode("utf-16-le")
            nchars = len(s)
            if nchars & 0x8000:
                out += struct.pack("<H", 0x8000 | (nchars >> 16))
                out += struct.pack("<H", nchars & 0xFFFF)
            else:
                out += struct.pack("<H", nchars)
            out += raw + b"\x00\x00"
        while len(out) % 4:
            out.append(0)
        return bytes(out)

    def build(self) -> bytes:
        """按当前 self.strings 重建字符串池 chunk 的字节。"""
        data = bytearray()
        offsets = []
        for s in self.strings:
            offsets.append(len(data))
            data += self._encode(s)
        while len(data) % 4:
            data.append(0)

        # stringsStart 以 chunk 起始为基准；header_size 已包含 ResChunk_header 的 8 字节
        new_strings_start = self.header_size + 4 * self.string_count + 4 * self.style_count
        body = struct.pack(f"<{self.string_count}I", *offsets)
        if self.style_count:
            body += struct.pack(f"<{self.style_count}I", *self.style_offsets)
        body += bytes(data)

        # chunk 总长 = 固定头(28) + 字符串偏移表 + 样式偏移表 + 字符串数据
        chunk_size = self.header_size + 4 * self.string_count + 4 * self.style_count + len(data)

        head = struct.pack("<HHIIIIII", self.type, self.header_size, chunk_size,
                           self.string_count, self.style_count, self.flags,
                           new_strings_start, self.styles_start)
        return head + body


def patch_manifest(axml: bytes, old_pkg: str, new_pkg: str, verbose: bool = False):
    if struct.unpack_from("<H", axml, 0)[0] != RES_XML_TYPE:
        raise ValueError("不是二进制 AXML")
    pool = AxmlStringPool(axml)

    if verbose:
        # 打印包名字符串条目的全部形态：恰好等于包名的那条会被替换，
        # 「包名.xxx」形式（权限名 / authority / action）必须保持原样
        for i, s in enumerate(pool.strings):
            if s == old_pkg or s.startswith(old_pkg + "."):
                print(f"  [{i:3d}] {s!r}")

    hits = [i for i, s in enumerate(pool.strings) if s == old_pkg]
    if len(hits) != 1:
        raise ValueError(
            f"期望恰好 1 个字符串条目等于 {old_pkg!r}，实际 {len(hits)} 个 {hits}")
    idx = hits[0]
    pool.strings[idx] = new_pkg

    new_chunk = pool.build()
    out = bytearray()
    out += axml[:8]                       # XML 根 chunk 头
    out += new_chunk
    out += pool.tail                      # 字符串池之后的全部数据

    total = len(out)
    struct.pack_into("<I", out, 4, total)  # 修正根 chunk 的 size
    return bytes(out), idx, total


RES_TABLE_TYPE = 0x0002
RES_TABLE_PACKAGE_TYPE = 0x0200
PKG_NAME_FIELD = 256  # ResTable_package.name[128] —— 固定长度，可原地无损改写

# ── 二进制 AXML 结构解析（供侦查 / 校验 / auto-ability 使用）─────────────────
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
TYPE_STRING = 0x03


def iter_chunks(buf: bytes, start: int = 0):
    """按 ResChunk_header 顺序遍历 chunk，产出 (偏移, 类型, 尺寸)。"""
    off = start
    while off + 8 <= len(buf):
        ctype, _chdr, csize = struct.unpack_from("<HHI", buf, off)
        if csize < 8 or off + csize > len(buf):
            break
        yield off, ctype, csize
        off += csize


def _decode_attrs(buf: bytes, off: int, pool) -> dict:
    """解码 START_ELEMENT chunk 的属性表为 {属性名: 字符串值 或 (类型, 原始值)}。"""
    (_ns, _nm, astart, asize, acount) = struct.unpack_from("<IIHHH", buf, off + 16)
    attrs = {}
    base = off + 16 + astart
    for i in range(acount):
        a = base + i * asize
        _a_ns, a_nm, _raw = struct.unpack_from("<III", buf, a)
        _ds, _r0, dt, dd = struct.unpack_from("<HBBI", buf, a + 12)
        key = pool.strings[a_nm] if a_nm < len(pool.strings) else f"#{a_nm}"
        if dt == TYPE_STRING and dd < len(pool.strings):
            attrs[key] = pool.strings[dd]
        else:
            attrs[key] = (dt, dd)
    return attrs


def read_elements(axml: bytes, pool=None):
    """遍历 AXML 的 XML 节点，产出 ('start'|'end', 元素名, 属性字典)。

    ``struct`` 的 ``<IIHHHHHH`` 解析出 attributeStart 等字段；attributeStart
    是**相对 attrExt 起始**（即节点头 16 字节之后）的偏移。
    """
    if pool is None:
        pool = AxmlStringPool(axml)
    body = 8 + pool.size
    for off, ctype, _csize in iter_chunks(axml, body):
        if ctype == RES_XML_START_ELEMENT_TYPE:
            nm = struct.unpack_from("<I", axml, off + 20)[0]
            name = pool.strings[nm] if nm < len(pool.strings) else f"#{nm}"
            yield "start", name, _decode_attrs(axml, off, pool)
        elif ctype == RES_XML_END_ELEMENT_TYPE:
            nm = struct.unpack_from("<I", axml, off + 20)[0]
            yield "end", (pool.strings[nm] if nm < len(pool.strings) else f"#{nm}"), {}


def get_manifest_package(axml: bytes) -> str:
    """读取 <manifest package="..."> 的值。"""
    pool = AxmlStringPool(axml)
    for kind, name, attrs in read_elements(axml, pool):
        if kind == "start" and name == "manifest":
            pkg = attrs.get("package")
            if isinstance(pkg, str):
                return pkg
            break
    raise ValueError("清单中未找到 package 属性")


def find_launcher_activities(axml: bytes):
    """返回声明了 MAIN + LAUNCHER 的 activity / activity-alias 名称列表。"""
    root = {"name": "#root", "attrs": {}, "children": []}
    stack = [root]
    for kind, name, attrs in read_elements(axml):
        if kind == "start":
            node = {"name": name, "attrs": attrs, "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        elif len(stack) > 1:
            stack.pop()

    def find_app(node):
        for c in node["children"]:
            if c["name"] == "application":
                return c
            hit = find_app(c)
            if hit:
                return hit
        return None

    app = find_app(root)
    out = []
    if not app:
        return out
    for c in app["children"]:
        if c["name"] not in ("activity", "activity-alias"):
            continue
        for f in c["children"]:
            if f["name"] != "intent-filter":
                continue
            actions = [x["attrs"].get("name") for x in f["children"] if x["name"] == "action"]
            cats = [x["attrs"].get("name") for x in f["children"] if x["name"] == "category"]
            if ("android.intent.action.MAIN" in actions
                    and "android.intent.category.LAUNCHER" in cats):
                n = c["attrs"].get("name")
                if isinstance(n, str) and n not in out:
                    out.append(n)
    return out


def patch_arsc(arsc: bytes, new_pkg: str, verbose: bool = False):
    """同步 resources.arsc 中的包名（固定长度字段，无需重建字符串池）。"""
    typ, hdr = struct.unpack_from("<HH", arsc, 0)
    if typ != RES_TABLE_TYPE:
        raise ValueError(f"不是资源表: 0x{typ:04x}")
    total = struct.unpack_from("<I", arsc, 4)[0]

    out = bytearray(arsc)
    found = 0
    off = hdr
    while off < total:
        ctype, chdr, csize = struct.unpack_from("<HHI", arsc, off)
        if csize <= 0:
            break
        if ctype == RES_TABLE_PACKAGE_TYPE:
            pos = off + 12  # chunk头(8) + id(4)
            old = arsc[pos:pos + PKG_NAME_FIELD].decode("utf-16-le", "replace").split("\x00")[0]
            if verbose:
                print(f"  资源表 package chunk @0x{off:x} name={old!r}")
            enc = new_pkg.encode("utf-16-le")
            if len(enc) > PKG_NAME_FIELD:
                raise ValueError("新包名过长")
            buf = bytearray(PKG_NAME_FIELD)
            buf[:len(enc)] = enc
            out[pos:pos + PKG_NAME_FIELD] = buf
            found += 1
        off += csize
    return bytes(out), found


def rebuild_apk(src: str, dst: str, replacements: dict):
    zin = zipfile.ZipFile(src, "r")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = replacements.get(item.filename, zin.read(item.filename))
            zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
            zi.compress_type = item.compress_type
            zi.external_attr = item.external_attr
            zi.internal_attr = item.internal_attr
            zi.create_system = item.create_system
            zi.flag_bits = 0
            zi.file_size = len(data)
            zout.writestr(zi, data)
    zin.close()


def main():
    args = [a for a in sys.argv[1:] if a != "--list"]
    src, dst, new_pkg = args[0], args[1], args[2]
    verbose = "--list" in sys.argv

    with zipfile.ZipFile(src) as z:
        axml = z.read("AndroidManifest.xml")
        arsc = z.read("resources.arsc")
    old_pkg = get_manifest_package(axml)   # 从清单自身读出，不硬编码
    print(f"原始 manifest: {len(axml)} 字节；资源表: {len(arsc)} 字节")

    new_axml, idx, total = patch_manifest(axml, old_pkg, new_pkg, verbose)
    print(f"字符串池条目 #{idx}: {old_pkg!r} -> {new_pkg!r}")
    print(f"新 manifest: {len(new_axml)} 字节 (根 size={total})")

    new_arsc, n = patch_arsc(arsc, new_pkg, verbose)
    print(f"资源表包名已同步（命中 {n} 个 package chunk）")

    rebuild_apk(src, dst, {
        "AndroidManifest.xml": new_axml,
        "resources.arsc": new_arsc,
    })
    print(f"已写出: {dst}")


if __name__ == "__main__":
    main()
