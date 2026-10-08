#!/bin/bash
# build_variant.sh —— 一条龙生成「(可选)改包名 + (可选)桌面注册 + AOSP testkey 签名」的 APK
#
# 用法:
#   build_variant.sh <原始apk> <新包名>              # 改包名 + 注入桌面注册
#   build_variant.sh <原始apk> --keep-package        # 不改包名，只注入桌面注册
#   build_variant.sh <原始apk> <新包名> --no-meta    # 只改包名（后台启动版）
#   build_variant.sh <原始apk> <新包名> -o 输出.apk  # 指定交付文件；-o 给目录则自动命名
#
# 输出位置:
#   默认 <交付目录>/<源文件名>-<包名>.apk。
#   两种目录都由 _dirs.py 解析，**跟着当前项目走**：
#     <当前项目>/.hongqi-car-apk/out   交付物：变体 APK / 原版备份 / 安装说明
#     <当前项目>/.hongqi-car-apk/work  中间产物：未签名中间件、工具缓存
#   可用 -o 覆盖交付文件，或设 $HQCAR_OUT_DIR / $HQCAR_WORK_DIR 钉死目录。
#
# 说明:
#   * Ability 用 @auto 占位，自动取该 APK 自己的 MAIN/LAUNCHER Activity；
#   * MoreApp 以**布尔型**注入（与车机样本一致），故用 --meta-bool；
#   * 签名用脚本同级目录的 testkey.jks（AOSP 官方 testkey，别名/口令均为 testkey）。
set -euo pipefail

TOOLS="$(cd "$(dirname "$0")" && pwd)"
SIGNER_BUNDLED="$TOOLS/uber-apk-signer.jar"
SIGNER_URL="https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"

usage() {
    sed -n '/^# 用法:/,/^#$/p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-1}"
}

# ── 定位 JDK ────────────────────────────────────────────────
if [ -z "${JAVA_HOME:-}" ]; then
    for c in /usr/local/opt/openjdk /opt/homebrew/opt/openjdk \
             /opt/homebrew/opt/openjdk@21 /usr/local/opt/openjdk@21; do
        [ -x "$c/bin/java" ] && JAVA_HOME="$c" && break
    done
fi
JAVA="${JAVA_HOME:-}/bin/java"
[ -x "$JAVA" ] || JAVA="$(command -v java || true)"
[ -x "$JAVA" ] || { echo "✗ 找不到 JDK（可用 JAVA_HOME 指定）"; exit 1; }

# ── 定位 Python ──────────────────────────────────────────────
PY="${PY:-$(command -v python3 || true)}"
[ -x "${PY:-}" ] || { echo "✗ 找不到 python3（可用 PY 指定）"; exit 1; }

# ── 两种目录：跟着「当前项目」走，绝不写进别的项目 / 别人的工作目录 ──
WORK_DIR="$("$PY" "$TOOLS/_dirs.py" work)"
OUT_DIR="$("$PY" "$TOOLS/_dirs.py" out)"
TOOL_CACHE="$("$PY" "$TOOLS/_dirs.py" tools)"
mkdir -p "$WORK_DIR" "$OUT_DIR" "$TOOL_CACHE"

# ── 签名器：优先用随技能打包的 jar；缺失则下载到工具缓存，避免"静默不签名" ──
SIGNER="$SIGNER_BUNDLED"
if [ ! -f "$SIGNER" ]; then
    SIGNER="$TOOL_CACHE/uber-apk-signer.jar"
    if [ ! -f "$SIGNER" ]; then
        echo "→ 未找到 uber-apk-signer.jar，正在下载…"
        curl -fsSL -o "$SIGNER" "$SIGNER_URL" || {
            echo "✗ 下载失败。请手动下载到：$SIGNER"; echo "  $SIGNER_URL"; exit 1; }
    fi
fi

# ── 参数解析 ─────────────────────────────────────────────────
[ $# -ge 2 ] || usage

SRC="$1"; shift
OUT=""; PKG=""; KEEP=0; META_ON=1
while [ $# -gt 0 ]; do
    case "$1" in
        --keep-package) KEEP=1 ;;
        --no-meta)      META_ON=0 ;;
        -o|--out)       OUT="${2:-}"; [ -n "$OUT" ] || usage; shift ;;
        -h|--help)      usage 0 ;;
        --*)            echo "✗ 未知参数：$1"; usage ;;
        *.apk|*.APK)    if [ -z "$OUT" ]; then OUT="$1"; else PKG="$1"; fi ;;
        *)              PKG="$1" ;;
    esac
    shift
done

[ -f "$SRC" ] || { echo "✗ 找不到源文件：$SRC"; exit 1; }
if [ "$KEEP" != "1" ]; then
    [ -n "$PKG" ] || { echo "✗ 缺少新包名（或改用 --keep-package）"; usage; }
fi

# ── 输出路径：默认落到「交付目录」，文件名取「源文件名-包名.apk」 ──
if [ -z "$OUT" ]; then
    STEM="$(basename "$SRC")"; STEM="${STEM%.*}"    # 去掉 .apk/.APK
    OUT="$OUT_DIR/${STEM}-${PKG:-keep-package}.apk"
elif [ -d "$OUT" ]; then
    STEM="$(basename "$SRC")"; STEM="${STEM%.*}"
    OUT="$OUT/${STEM}-${PKG:-keep-package}.apk"
fi
mkdir -p "$(dirname "$OUT")"

# ── 车机桌面注册协议（对齐车机上可正常显示图标的样本，声明顺序保持一致）──
META=(--meta "Group=GROUP CARPLAY"
      --meta "Domain=DOMAIN CARPLAY"
      --meta "Ability=@auto"
      --meta-bool "MoreApp=true")

# 中间产物落在 work 目录内的临时子目录，跑完即清，不留垃圾
WORK="$(mktemp -d "$WORK_DIR/.tmp.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "──────────────────────────────────────────────"
echo "源文件 : $SRC"
if [ "$KEEP" = "1" ]; then
    echo "包名   : 保持原样"
else
    echo "包名   : -> $PKG"
fi
echo "桌面注册: $([ "$META_ON" = "1" ] && echo '注入 4 项 meta-data' || echo '不注入（后台启动版）')"
echo "中间产物: $WORK"
echo "输出   : $OUT"

ARGS=()
[ "$KEEP" = "1" ] && ARGS+=(--keep-package) || ARGS+=("$PKG")
[ "$META_ON" = "1" ] && ARGS+=("${META[@]}")
$PY "$TOOLS/axml_meta.py" "$SRC" "$WORK/patched.apk" "${ARGS[@]}"

echo "→ 签名 (AOSP testkey)"
mkdir -p "$WORK/out"
"$JAVA" -jar "$SIGNER" -a "$WORK/patched.apk" \
    --ks "$TOOLS/testkey.jks" --ksAlias testkey \
    --ksPass android --ksKeyPass android \
    -o "$WORK/out" | grep -E "zipalign|Verif|Signed|error|Successfully" || true

PRODUCED="$WORK/out/patched-aligned-signed.apk"
[ -f "$PRODUCED" ] || { echo "✗ 签名未产出文件，请检查上面的签名器输出"; exit 1; }

cp -f "$PRODUCED" "$OUT"
echo "→ 已写出 $OUT"
$PY "$TOOLS/axml_meta.py" "$OUT" --detect
