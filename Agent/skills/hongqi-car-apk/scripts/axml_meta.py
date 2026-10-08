#!/usr/bin/env python3
"""
axml_meta.py — 二进制 AXML 补丁工具：改包名 + 注入车机桌面注册 meta-data。

背景：部分车机（含红旗）的原厂 Launcher 不按标准 LAUNCHER 意图扫描桌面图标，
而是读取应用 <application> 下的一组约定 meta-data（Group / Domain / Ability /
MoreApp）来构建桌面入口。缺少这组声明的应用即使有 MAIN/LAUNCHER Activity，
也不会出现在桌面上（只能从系统管理后台启动）。

本脚本在二进制 AXML 上做**纯增量**修改：
  * 字符串池仅在末尾追加新字符串，已有条目索引全部保持不变；
  * 在 </application> 前插入 <meta-data> 元素 chunk；
  * 不改动 dex；改包名时同步 resources.arsc 的固定长度包名字段。

用法:
  # 只改包名
  python3 axml_meta.py <src.apk> <dst.apk> <new.package>

  # 改包名 + 注入桌面注册
  python3 axml_meta.py <src.apk> <dst.apk> <new.package> \
      --meta "Group=GROUP CARPLAY" --meta "MoreApp=true"

  # 不改包名，仅注入（用于加工加固/已有的白名单版 APK）
  python3 axml_meta.py <src.apk> <dst.apk> --keep-package \
      --meta "Group=GROUP CARPLAY" --auto-ability

  # 只做侦查（不写文件）
  python3 axml_meta.py <src.apk> --detect

选项:
  --keep-package    不改包名，也不同步 resources.arsc
  --auto-ability    用清单里探测到的 MAIN/LAUNCHER Activity 自动填充 Ability
  --detect          打印包名 / 启动 Activity / <application> 级 meta-data 后退出
  --verbose         输出明细
"""
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from axml_rename import (  # noqa: E402
    AxmlStringPool, RES_XML_TYPE, patch_arsc, patch_manifest, rebuild_apk,
    iter_chunks, get_manifest_package, find_launcher_activities, read_elements,
)

RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
NO_INDEX = 0xFFFFFFFF          # 无命名空间 / 无注释
TYPE_STRING = 0x03
TYPE_INT_BOOLEAN = 0x12        # 样本中 MoreApp 的取值类型
ATTR_STRIDE = 20               # ns(4) + name(4) + rawValue(4) + Res_value(8)


def _build_start_element(line: int, ns_idx: int, elem_name_idx: int, attrs) -> bytes:
    """构造 RES_XML_START_ELEMENT chunk。attrs: [(ns, name, raw, dtype, data)]"""
    payload = struct.pack(
        "<IIHHHHHH", ns_idx, elem_name_idx,
        ATTR_STRIDE,           # attributeStart：相对 attrExt 起始的偏移
        ATTR_STRIDE,           # attributeSize
        len(attrs), 0, 0, 0,   # attributeCount, idIndex, classIndex, styleIndex
    )
    for a_ns, a_name, raw, dtype, data in attrs:
        # Res_value: size=8, res0=0, dataType, data
        payload += struct.pack("<IIIHBBI", a_ns, a_name, raw, 8, 0, dtype, data)
    size = 16 + len(payload)   # 8(chunk 头) + 8(node: line+comment) + attrExt+attrs
    return (struct.pack("<HHI", RES_XML_START_ELEMENT_TYPE, 16, size)
            + struct.pack("<II", line, NO_INDEX) + payload)


def _build_end_element(line: int, ns_idx: int, elem_name_idx: int) -> bytes:
    """构造 RES_XML_END_ELEMENT chunk（固定 24 字节）。"""
    return (struct.pack("<HHI", RES_XML_END_ELEMENT_TYPE, 16, 24)
            + struct.pack("<II", line, NO_INDEX)
            + struct.pack("<II", ns_idx, elem_name_idx))


def _find_end_element(tail: bytes, elem_name_idx: int) -> int:
    for off, ctype, _size in iter_chunks(tail):
        if ctype == RES_XML_END_ELEMENT_TYPE:
            _ns, nm = struct.unpack_from("<II", tail, off + 16)
            if nm == elem_name_idx:
                return off
    return -1


def application_meta(axml: bytes):
    """返回 <application> 直属的 meta-data 列表 [(name, value, resource), ...]。"""
    pool = AxmlStringPool(axml)
    depth = 0
    in_app = 0            # <application> 所在深度；0 表示尚未进入
    out = []
    for kind, name, attrs in read_elements(axml, pool):
        if kind == "start":
            depth += 1
            if name == "application":
                in_app = depth
            elif in_app and depth == in_app + 1 and name == "meta-data":
                out.append((attrs.get("name"), attrs.get("value"), attrs.get("resource")))
        else:
            if in_app and depth == in_app:
                in_app = 0
            depth -= 1
    return out


def inject_meta(axml: bytes, entries, parent: str = "application",
                verbose: bool = False) -> bytes:
    """在 <parent> 元素的结束标记前插入一组 <meta-data android:name=... android:value=...>。

    ``entries`` 为 ``(key, value, dtype)`` 三元组；``dtype`` 默认 0x03（字符串），
    传 0x12 则写成布尔（与样本中 ``MoreApp`` 的类型一致）。
    """
    if struct.unpack_from("<H", axml, 0)[0] != RES_XML_TYPE:
        raise ValueError("不是二进制 AXML")
    pool = AxmlStringPool(axml)

    def sidx(s: str) -> int:
        """取字符串池索引；不存在则在末尾追加（不打乱既有索引）。"""
        try:
            return pool.strings.index(s)
        except ValueError:
            pool.strings.append(s)
            return len(pool.strings) - 1

    i_parent = pool.strings.index(parent)     # 必须已存在
    i_elem = sidx("meta-data")
    ns_android = sidx("http://schemas.android.com/apk/res/android")
    i_name = sidx("name")
    i_value = sidx("value")

    tail = pool.tail
    end_off = _find_end_element(tail, i_parent)
    if end_off < 0:
        raise ValueError(f"未找到 </{parent}> 结束标记")
    line = struct.unpack_from("<I", tail, end_off + 8)[0]

    blob = bytearray()
    for key, val, dtype in entries:
        ik = sidx(key)
        if dtype == TYPE_STRING:
            iv = sidx(val)
            data = iv
        else:                                  # 布尔 / 整型：data 为数值本身
            iv = NO_INDEX
            data = 0xFFFFFFFF if val in ("true", "1") else 0
        blob += _build_start_element(line, NO_INDEX, i_elem, [
            (ns_android, i_name, ik, TYPE_STRING, ik),
            (ns_android, i_value, iv, dtype, data),
        ])
        blob += _build_end_element(line, NO_INDEX, i_elem)
        if verbose:
            print(f"  + <meta-data android:name={key!r} "
                  f"android:value={val!r}（类型 0x{dtype:02x}）/>")

    pool.string_count = len(pool.strings)   # 追加后同步计数
    new_tail = tail[:end_off] + bytes(blob) + tail[end_off:]
    out = bytearray(axml[:8]) + pool.build() + new_tail
    struct.pack_into("<I", out, 4, len(out))   # 修正根 XML chunk 的 size
    return bytes(out)


def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    keep_pkg = "--keep-package" in argv
    detect = "--detect" in argv
    auto_ability = "--auto-ability" in argv

    entries, rest = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--meta", "--meta-bool"):
            k, _, v = argv[i + 1].partition("=")
            entries.append((k, v, TYPE_INT_BOOLEAN if a == "--meta-bool" else TYPE_STRING))
            i += 2
        elif a.startswith("--"):
            i += 1
        else:
            rest.append(a)
            i += 1

    if not rest:
        raise SystemExit(__doc__.strip().split("用法:")[0].strip())

    src = rest[0]
    dst = rest[1] if len(rest) > 1 else None
    with zipfile.ZipFile(src) as z:
        axml = z.read("AndroidManifest.xml")
        arsc = z.read("resources.arsc")

    old_pkg = get_manifest_package(axml)
    launchers = find_launcher_activities(axml)

    if detect:
        print(f"包名            : {old_pkg}")
        print(f"启动 Activity   : {launchers or '（未声明 MAIN/LAUNCHER）'}")
        metas = application_meta(axml)
        print(f"application 级 meta-data ({len(metas)} 项):")
        for k, v, r in metas:
            if r is not None:
                print(f"    {k}  @resource={r}")
            elif isinstance(v, tuple):
                print(f"    {k} = <类型 0x{v[0]:02x}, 值 {v[1]}>")
            else:
                print(f"    {k} = {v!r}")
        print(f"manifest {len(axml)} 字节 / 资源表 {len(arsc)} 字节")
        return

    new_pkg = rest[2] if len(rest) > 2 else old_pkg
    if keep_pkg:
        new_pkg = old_pkg

    if auto_ability:
        entries = [e for e in entries if e[0] != "Ability"]
        entries.append(("Ability", "@auto", TYPE_STRING))

    # 「@auto」占位符就地展开为清单探测到的 MAIN/LAUNCHER Activity（保持声明顺序）
    if any(v == "@auto" for _k, v, _t in entries):
        if not launchers:
            raise ValueError("@auto：清单未声明 MAIN/LAUNCHER Activity")
        entries = [(k, launchers[0] if v == "@auto" else v, t) for k, v, t in entries]
        print(f"自动填充 Ability = {launchers[0]}")

    print(f"原始 manifest {len(axml)} 字节 / 资源表 {len(arsc)} 字节")
    print(f"包名: {old_pkg} -> {new_pkg}{'（保持）' if new_pkg == old_pkg else ''}")

    axml2 = axml
    if new_pkg != old_pkg:
        axml2, idx, _tot = patch_manifest(axml, old_pkg, new_pkg, verbose)
        print(f"  命名字符串条目 #{idx}")

    if entries:
        print(f"注入桌面注册 meta-data（{len(entries)} 项）:")
        axml2 = inject_meta(axml2, entries, verbose=verbose)

    repl = {"AndroidManifest.xml": axml2}
    if new_pkg != old_pkg:
        arsc2, n = patch_arsc(arsc, new_pkg, verbose)
        print(f"资源表包名同步命中 {n} 个 package chunk")
        repl["resources.arsc"] = arsc2

    if not dst:
        raise SystemExit("用法: axml_meta.py <src.apk> <dst.apk> [<new.package>] "
                         "[--keep-package] [--auto-ability] [--meta K=V]... | "
                         "axml_meta.py <src.apk> --detect")

    print(f"新 manifest {len(axml2)} 字节")
    rebuild_apk(src, dst, repl)
    print(f"已写出 {dst}")


if __name__ == "__main__":
    main()
