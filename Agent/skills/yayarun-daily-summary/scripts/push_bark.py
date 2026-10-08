#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑鸭卡片生成后，推一条 Bark 通知到 iPhone。

用法：
    python3 push_bark.py --file run-summary-2026-09-29.html --date 2026-09-29
    python3 push_bark.py --file run-summary-2026-09-29.html --dry-run
    python3 push_bark.py --self-test

与旧版的关键差异：改用 Bark 的 **POST /push（JSON 请求体）**，而不是把 key 拼进 GET 路径：
  - key 不再出现在 URL / curl 命令行里（`ps` 看不到，也不进任何 URL 日志）
  - `url`（shortcuts 回调）作为 JSON 字段原样传递，**不再需要"整体再编码一次"**，
    旧版最容易踩的「回调被 & 截断、通知照发点了没反应」这一类问题从根上消失
  - 不依赖 curl，纯标准库

取 key 顺序：环境变量 BARK_API_KEY_iPhone14 → ~/.zshrc（取最后一条；用 shlex 解析，
支持引号与行尾注释；含 $VAR / $(...) 的值无法静态解析，会明确报错而不是拿到半截字符串）。

退出码：0=推送成功(code 200) / 1=失败或没取到 key / 3=仅 dry-run
安全：任何输出都不得出现完整 key，一律掩码。
"""

import argparse
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

KEY_NAME = "BARK_API_KEY_iPhone14"
KEY_RE = re.compile(r"^[ \t]*(?:export[ \t]+)?" + KEY_NAME + r"[ \t]*=(.*)$", re.M)
SHORTCUT_NAME = "跑步概况预览"
TITLE = "训练概况"
GROUP = "跑鸭"
ICON = "https://img.remit.ee/i/quVvHGq5WXlT"
API_BASE = "https://api.day.app"
CARD_DIR = "~/Documents/YaYaRun"
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
FILE_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def mask(secret):
    """只暴露首尾各 4 位；短值全掩。"""
    if not secret:
        return "(empty)"
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


def read_key(zshrc=None):
    """返回 (key, 错误原因)。只报存在性与原因，绝不回显值内容。"""
    env = os.environ.get(KEY_NAME, "").strip()
    if env and not zshrc:
        return env, None

    path = os.path.expanduser(zshrc or "~/.zshrc")
    if not os.path.isfile(path):
        return None, f"未找到配置文件 {path}"
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        hits = KEY_RE.findall(fh.read())
    if not hits:
        return None, f"{path} 中没有 {KEY_NAME}"
    raw = hits[-1].strip()                       # 同名重复 export 时后者覆盖前者
    if "$" in raw or "`" in raw:
        return None, f"{KEY_NAME} 的值含变量/命令替换，无法静态解析；请设成环境变量后重试"
    try:
        parts = shlex.split(raw, comments=True)   # 处理成对引号与行尾 # 注释
    except ValueError as exc:
        return None, f"{KEY_NAME} 的值引号不匹配: {exc}"
    if len(parts) != 1 or not parts[0]:
        return None, f"{KEY_NAME} 的值为空或含多个词"
    return parts[0], None


def resolve_date(date_arg, filename):
    """--date 优先；否则从文件名里的 YYYY-MM-DD 反推。绝不回落到"今天"（要的是跑步日）。"""
    if date_arg:
        try:
            return datetime.strptime(date_arg, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit(f"[错误] --date 格式应为 YYYY-MM-DD，收到：{date_arg}")
    m = FILE_DATE_RE.search(filename or "")
    if m:
        try:
            return date(*(int(x) for x in m.groups()))
        except ValueError:
            pass
    raise SystemExit("[错误] 无法确定日期：文件名里没有 YYYY-MM-DD，请显式传 --date YYYY-MM-DD")


def build_callback(filename):
    """shortcuts 回调；name 与 text 各编码一次即可（JSON 传输，无需二次编码）。"""
    return ("shortcuts://run-shortcut"
            f"?name={urllib.parse.quote(SHORTCUT_NAME, safe='')}"
            f"&input=text"
            f"&text={urllib.parse.quote(filename, safe='')}")


def build_payload(key, day, filename):
    body = f"{day.isoformat()} {WEEKDAYS[day.weekday()]}"
    return {
        "device_key": key,
        "title": TITLE,
        "body": body,
        "group": GROUP,
        "icon": ICON,
        "url": build_callback(filename),
    }, body


def masked_view(payload):
    """给 dry-run / verbose 用的脱敏副本。"""
    return {**payload, "device_key": mask(payload["device_key"])}


def send(api_base, payload, timeout=30):
    """POST {api_base}/push，返回 (ok, 说明)。异常信息里不含 key（key 只在请求体内）。"""
    parts = urllib.parse.urlsplit(api_base)
    if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost"):
        return False, f"拒绝向非 https 地址发送 key：{parts.scheme}://{parts.hostname}"
    req = urllib.request.Request(
        api_base.rstrip("/") + "/push",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as exc:
        # Bark 业务错误（如 400 device key 无效）也带 JSON
        raw = exc.read().decode("utf-8", errors="replace").strip()
        if not raw.startswith("{"):
            return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"网络错误: {reason}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, f"响应不是 JSON: {raw[:200]}"
    if data.get("code") == 200:
        return True, f"Bark code=200 ({data.get('message', 'success')})"
    return False, f"Bark code={data.get('code')} message={data.get('message')}"


def self_test():
    """起本地假 Bark 服务，验证：key 只在请求体、回调原样不二次编码、日期是跑步日、掩码有效。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    got = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            got["path"] = self.path
            got["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"code": 200, "message": "success"}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(out)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    key = "VLYPabcdefghijk9LXN"
    day = date(2026, 9, 29)                      # 周二；"今天"是 9/30，必须用跑步日
    payload, body = build_payload(key, day, "run-summary-2026-09-29.html")
    ok, msg = send(f"http://127.0.0.1:{srv.server_port}", payload)
    srv.shutdown()

    res = []
    def check(label, cond):
        res.append(cond); print(f"  {label} … {'OK' if cond else 'FAIL'}")

    print("[self-test] 本地假 Bark …")
    check("推送成功 code=200", ok)
    check("key 不在 URL 路径里", key not in got.get("path", ""))
    check("key 在请求体 device_key", got["body"]["device_key"] == key)
    check("回调 & 原样保留（无需二次编码）", got["body"]["url"].count("&") == 2 and "%26" not in got["body"]["url"])
    check("回调含 name/text 且已各编码一次",
          "name=%E8%B7%91" in got["body"]["url"] and "text=run-summary-2026-09-29.html" in got["body"]["url"])
    check("正文用跑步日 + 正确周几：2026-09-29 周二", got["body"]["body"] == "2026-09-29 周二")
    check("dry-run 脱敏后不含完整 key", key not in json.dumps(masked_view(payload)))
    check("拒绝向明文 http 远端发 key", send("http://example.com", payload)[0] is False)

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rc = Path(td) / "zshrc"
        rc.write_text('export BARK_API_KEY_iPhone14="old"\n'
                      '# export BARK_API_KEY_iPhone14="commented"\n'
                      "export BARK_API_KEY_iPhone14='newkey123'   # 备注\n", encoding="utf-8")
        check("zshrc：取最后一条、剥引号、去行尾注释", read_key(str(rc))[0] == "newkey123")
        rc.write_text('export BARK_API_KEY_iPhone14="$(security find-generic-password -w)"\n', encoding="utf-8")
        k, err = read_key(str(rc))
        check("zshrc：含 $(...) 明确报错而非返回半截值", k is None and "无法静态解析" in err)
    ok_all = all(res)
    print("[self-test] " + ("全部通过" if ok_all else "存在失败项"))
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(description="推送跑鸭跑步卡片 Bark 通知")
    ap.add_argument("--file", help="卡片文件名，如 run-summary-2026-09-29.html")
    ap.add_argument("--date", help="跑步日期 YYYY-MM-DD；省略则从文件名反推")
    ap.add_argument("--dir", default=CARD_DIR, help=f"卡片目录，用于确认文件存在，默认 {CARD_DIR}")
    ap.add_argument("--zshrc", help="指定 shell 配置文件（指定后不读环境变量）")
    ap.add_argument("--api-base", default=os.environ.get("BARK_API_BASE", API_BASE),
                    help="Bark 服务地址，默认官方；自建服务可传自己的 https 地址")
    ap.add_argument("--dry-run", action="store_true", help="只打印（脱敏的）请求内容，不发送")
    ap.add_argument("--no-check-file", action="store_true", help="跳过卡片文件存在性检查")
    ap.add_argument("--self-test", action="store_true", help="本地假 Bark 服务自检")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.file:
        ap.error("--file 必填（或用 --self-test）")

    filename = os.path.basename(args.file)
    day = resolve_date(args.date, filename)

    card = Path(os.path.expanduser(args.dir)) / filename
    if not args.no_check_file and not card.is_file():
        # 卡片没生成成功就推通知，用户点开是个死链
        print(f"[失败] 卡片文件不存在：{card}（渲染步骤失败了？确认后可用 --no-check-file 跳过）", file=sys.stderr)
        return 1

    key, err = read_key(args.zshrc)
    if not key:
        print(f"[失败] {err}", file=sys.stderr)
        return 1
    print(f"[key ] {KEY_NAME} 长度={len(key)} 掩码={mask(key)}")

    payload, body = build_payload(key, day, filename)
    print(f"[时间] {body}")
    print(f"[回调] {payload['url']}")

    if args.dry_run:
        print("[请求] POST " + args.api_base.rstrip("/") + "/push")
        print("[载荷] " + json.dumps(masked_view(payload), ensure_ascii=False))
        print("[dry ] 未发送")
        return 3

    ok, msg = send(args.api_base, payload)
    print(("[成功] " if ok else "[失败] ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())