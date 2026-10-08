#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从跑鸭·RunYay MCP 取数，原样落盘到 _work/latest.json。

用法：
    python3 fetch_data.py --days 7
    python3 fetch_data.py --days 7 --end 20260930 --out _work/latest.json
    python3 fetch_data.py --self-test          # 起本地假 MCP 服务，端到端验证传输层

三次 MCP 调用，结果原样落盘（不裁剪字段）：
    runyay_get_latest_run_summary  -> latest
    runyay_get_run_segments        -> segments（空数组照常保留，不重试）
    runyay_get_run_summaries       -> recent（回看 N 天，含今天共 N 天）

凭据来源（按优先级）：
  1. **~/.config/magpie/library.json** 的 mcp[] 里 name=="yayarun" 的那条
  2. 环境变量 RUNYAY_MCP_URL / RUNYAY_MCP_TOKEN
token 只读进内存，**不打印、不落盘**；配置文件权限过宽会告警。
安全：带 token 时只允许 https（本机 localhost 除外）。

退出码：0=成功 / 1=取数失败 / 2=凭据缺失
"""

import argparse
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# 凭据来源：优先读 magpie 的 ~/.config/magpie/library.json（mcp[] 数组），
# 读不到再用环境变量 RUNYAY_MCP_URL / RUNYAY_MCP_TOKEN 兜底。
MCP_CONFIG = "~/.config/magpie/library.json"
SERVER_KEYS = ("yayarun", "runyay", "yaya")     # 精确匹配优先，其次按子串模糊匹配
PROTOCOL_VERSION = "2025-03-26"                 # Streamable HTTP 传输；服务端会在响应里协商
TIMEOUT = 30
RETRIES = 2                                     # 仅对网络错误 / 5xx 重试；MCP 业务错误与空分段不重试

WORK_SUBDIR = Path(".yayarun-daily-summary") / "_work"   # 中间产物目录（相对项目根）
PROJECT_MARKERS = (".git", ".yayarun-daily-summary")     # 认定"这是项目根"的标志


def resolve_project_dir(start=None):
    """定位当前项目根目录：从 start（默认 CWD）向上找带 .git / .yayarun-daily-summary 的目录。

    技能本身由 magpie 托管（库在 ~/.config/magpie/library/skills/），属于公共资产；
    中间产物若写在技能目录里，既污染被托管的库、也可能被 magpie 同步清掉。
    因此默认落到"当前项目"内。找不到任何标志时退回 start 本身（即当前工作目录）。
    """
    cur = Path(start or Path.cwd()).resolve()
    for base in (cur, *cur.parents):
        if any((base / m).exists() for m in PROJECT_MARKERS):
            return base
    return cur


def resolve_work_dir(explicit=None, start=None):
    """中间产物目录：显式指定 > <项目根>/.yayarun-daily-summary/_work。"""
    if explicit:
        return Path(os.path.expanduser(str(explicit))).resolve()
    return resolve_project_dir(start) / WORK_SUBDIR


# ---------------------------------------------------------------- 凭据

def _pick_server(cfg):
    """从 magpie 的 library.json 里取出跑鸭条目。

    结构：{"mcp": [{"name": "yayarun", "transport": "http", "url": ..., "headers": {...}}, ...]}
    为兼容也认 claude 风格的 {"mcpServers": {"yayarun": {...}}}。
    """
    entries = {}
    for item in (cfg.get("mcp") or []):          # magpie：数组，用 name 做键
        if isinstance(item, dict) and item.get("name"):
            entries[str(item["name"])] = item
    servers = cfg.get("mcpServers") or {}        # 兼容：name -> 配置 的映射
    if isinstance(servers, dict):
        for name, server in servers.items():
            entries.setdefault(str(name), server)

    for key in SERVER_KEYS:                      # 精确
        if key in entries:
            return entries[key]
    for name, server in entries.items():         # 模糊：配置里叫 "RunYay-MCP" 之类也能找到
        if any(k in name.lower() for k in SERVER_KEYS):
            return server
    return None


def _warn_if_world_readable(path):
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(f"[警告] {path} 对同组/其他用户可读，里面有 token，建议 chmod 600",
              file=sys.stderr)


def load_endpoint():
    """返回 (url, token, 错误原因)；成功时错误原因为 None。

    顺序：~/.config/magpie/library.json → 环境变量 RUNYAY_MCP_URL / RUNYAY_MCP_TOKEN。
    """
    path = Path(os.path.expanduser(MCP_CONFIG))
    missing = None
    if path.is_file():
        _warn_if_world_readable(path)
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            missing = f"{path} 解析失败: {exc}"
            cfg = None
        if cfg is not None:
            server = _pick_server(cfg)
            if not server:
                missing = f"{path} 里没有跑鸭条目（已找 {'/'.join(SERVER_KEYS)}）"
            else:
                url = server.get("url")
                auth = (server.get("headers") or {}).get("Authorization", "")
                token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
                if not url:
                    missing = f"{path} 里跑鸭条目缺 url"
                else:
                    return url, token, None
    else:
        missing = f"未找到 {path}"

    url = os.environ.get("RUNYAY_MCP_URL")
    token = os.environ.get("RUNYAY_MCP_TOKEN")
    if url:
        print("[警告] 回退环境变量 RUNYAY_MCP_URL / RUNYAY_MCP_TOKEN", file=sys.stderr)
        return url, token, None
    return None, None, missing


def check_transport_safe(url, token):
    """带 token 却走明文 http，等于把凭据发到网线上。localhost 放行（自检/本地调试）。"""
    parts = urllib.parse.urlsplit(url)
    if token and parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost"):
        return f"拒绝向非 https 地址发送凭据：{parts.scheme}://{parts.hostname}"
    return None


# ---------------------------------------------------------------- MCP 传输

class McpError(RuntimeError):
    pass


class McpClient:
    """极简 MCP Streamable-HTTP 客户端（JSON-RPC over HTTP POST）。

    握手：initialize -> 记下服务端返回的 Mcp-Session-Id -> 发 notifications/initialized。
    之后每个请求都带 session id。（原版既不带 session id 也不发 initialized 通知，
    遇到有状态的服务端会 400/404。）
    """

    def __init__(self, url, token, timeout=TIMEOUT):
        self.url, self.token, self.timeout = url, token, timeout
        self._id = 0
        self._initialized = False
        self._session = None

    def _headers(self):
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self._session:
            h["Mcp-Session-Id"] = self._session
        return h

    def _post_once(self, payload):
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"),
                                     headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            ctype = resp.headers.get("Content-Type", "")
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self._session = sid
        return raw, ctype

    def _post(self, payload, want_id=None):
        last = None
        for attempt in range(RETRIES + 1):
            try:
                raw, ctype = self._post_once(payload)
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:200]
                if exc.code >= 500 and attempt < RETRIES:
                    last = f"HTTP {exc.code}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise McpError(f"HTTP {exc.code}: {body}") from exc
            except urllib.error.URLError as exc:
                last = f"网络错误: {exc.reason}"
                if attempt < RETRIES:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise McpError(last) from exc
        else:
            raise McpError(last or "请求失败")

        if not raw.strip():                       # notification 的 202 空响应
            return {}
        if "text/event-stream" in ctype or raw.lstrip().startswith(("event:", "data:")):
            # SSE 里可能夹着服务端通知，按 id 挑出真正的响应
            msgs = []
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        msgs.append(json.loads(line[5:].strip()))
                    except json.JSONDecodeError:
                        pass
            for m in msgs:
                if isinstance(m, dict) and m.get("id") == want_id:
                    return m
            if not msgs:
                raise McpError(f"SSE 响应里没有可解析的数据: {raw[:200]}")
            return msgs[-1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise McpError(f"响应不是 JSON: {raw[:200]}") from exc

    def _call(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        reply = self._post(msg, want_id=self._id)
        if "error" in reply:
            err = reply["error"]
            raise McpError(f"{err.get('code')} {err.get('message')}")
        return reply.get("result", {})

    def ensure_init(self):
        if self._initialized:
            return
        self._call("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "yayarun-daily-summary", "version": "1.1"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def tools_call(self, name, arguments=None):
        self.ensure_init()
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        if not isinstance(result, dict):
            return result
        if result.get("isError"):
            text = " ".join(c.get("text", "") for c in result.get("content", []))
            raise McpError(f"工具 {name} 报错: {text[:200]}")
        if result.get("structuredContent"):
            return result["structuredContent"]
        for chunk in result.get("content", []):
            if chunk.get("type") == "text":
                try:
                    return json.loads(chunk["text"])
                except json.JSONDecodeError:
                    # 原版这里返回 {"raw": ...} 让后续悄悄拿到一份没有 activityId 的"摘要"
                    raise McpError(f"工具 {name} 返回了非 JSON 文本: {chunk['text'][:120]}")
        return result


# ---------------------------------------------------------------- 主流程

def run_date_of(summary):
    """startTimeInSeconds 形如 '20260929053122'（YYYYMMDDHHMMSS）-> date；解析不了返回 None。"""
    st = str(summary.get("startTimeInSeconds") or "")
    if len(st) >= 8 and st[:8].isdigit():
        try:
            return datetime.strptime(st[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def fetch(url, token, days, end_day):
    cli = McpClient(url, token)
    start_day = end_day - timedelta(days=days - 1)

    print("[1/3] get_latest_run_summary …")
    latest = cli.tools_call("runyay_get_latest_run_summary")
    if not isinstance(latest, dict) or not latest.get("found", True):
        raise McpError("没有找到任何跑步记录")
    summary = dict(latest.get("summary") or latest)

    activity_id = summary.get("activityId")
    segments = []
    if activity_id:
        print(f"[2/3] get_run_segments({activity_id}) …")
        try:
            seg_resp = cli.tools_call("runyay_get_run_segments", {"activityId": activity_id})
            segments = (seg_resp or {}).get("segments") or []
            print(f"      分段 {len(segments)} 条"
                  + ("（空数组：服务端可能稍后才返回，照常出卡片，不要连发重试）" if not segments else ""))
        except McpError as exc:
            print(f"      [警告] 取分段失败，继续：{exc}", file=sys.stderr)
    else:
        print("[2/3] 跳过分段：summary 里没有 activityId", file=sys.stderr)

    print(f"[3/3] get_run_summaries({start_day:%Y%m%d}~{end_day:%Y%m%d}) …")
    recent = []
    try:
        rec = cli.tools_call("runyay_get_run_summaries", {
            "startDate": f"{start_day:%Y%m%d}", "endDate": f"{end_day:%Y%m%d}", "pageSize": 100})
        recent = (rec or {}).get("summaries") or []
        print(f"      近期 {len(recent)} 条")
    except McpError as exc:
        print(f"      [警告] 取列表失败，继续：{exc}", file=sys.stderr)

    run_day = run_date_of(summary)
    return {
        "segments": segments,                  # 分段只存一份（原版在 latest 里又复制了一遍）
        "latest": summary,
        "recent": recent,
        "_meta": {
            "fetchedAt": datetime.now().isoformat(timespec="seconds"),
            "latestFound": True,
            "segmentsCount": len(segments),
            "recentCount": len(recent),
            "range": [f"{start_day:%Y-%m-%d}", f"{end_day:%Y-%m-%d}"],
            "runDate": run_day.isoformat() if run_day else None,
            "runIsToday": (run_day == end_day) if run_day else None,
        },
    }


def write_atomic(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)                          # 同目录 replace 原子；中途失败不会留下半截 JSON


# ---------------------------------------------------------------- 自检（真的跑传输层）

def self_test():
    """本地起一个假 MCP 服务（要求 session id + initialized 通知，回 SSE），端到端验证客户端。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = {"initialized": False, "bad": []}
    SUMMARY = {"found": True, "summary": {"activityId": "644993818-file",
               "startTimeInSeconds": "20260929053122", "distanceInMeters": 9798.21}}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            method, mid = body.get("method"), body.get("id")
            if self.headers.get("Authorization") != "Bearer T0KEN":
                self.send_response(401); self.end_headers(); return
            if method != "initialize" and self.headers.get("Mcp-Session-Id") != "sess-1":
                seen["bad"].append(f"{method} 缺 session id"); self.send_response(400); self.end_headers(); return
            if method == "notifications/initialized":
                seen["initialized"] = True; self.send_response(202); self.end_headers(); return
            if method == "initialize":
                res, extra = {"protocolVersion": PROTOCOL_VERSION}, {"Mcp-Session-Id": "sess-1"}
            else:
                extra = {}
                name = body["params"]["name"]
                data = ({"found": True, **SUMMARY} if name == "runyay_get_latest_run_summary"
                        else {"segments": []} if name == "runyay_get_run_segments"
                        else {"summaries": [SUMMARY["summary"]]})
                res = {"content": [{"type": "text", "text": json.dumps(data)}]}
            # 先夹一条无关通知，再给真正的响应（验证按 id 取）
            sse = ('event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
                   f'event: message\ndata: {json.dumps({"jsonrpc": "2.0", "id": mid, "result": res})}\n\n')
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            for k, v in extra.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(sse.encode())

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/mcp"

    results = []
    def check(label, cond):
        results.append(cond); print(f"  {label} … {'OK' if cond else 'FAIL'}")

    print("[self-test] 本地假 MCP 服务 …")
    check("https 强制：明文 http 远端应被拒", check_transport_safe("http://example.com/mcp", "t") is not None)
    check("https 强制：localhost 放行", check_transport_safe(url, "T0KEN") is None)
    check("日期解析 20260929053122 -> 2026-09-29",
          run_date_of(SUMMARY["summary"]) == date(2026, 9, 29))
    try:
        payload = fetch(url, "T0KEN", 7, date(2026, 9, 30))
        check("握手带 session id 且发出 initialized 通知", seen["initialized"] and not seen["bad"])
        check("SSE 夹带通知时按 id 取到正确响应", payload["latest"]["activityId"] == "644993818-file")
        check("空分段原样保留、不报错", payload["segments"] == [] and payload["_meta"]["segmentsCount"] == 0)
        check("_meta.runIsToday 正确（跑步日 9/29 vs 结束日 9/30 => False）", payload["_meta"]["runIsToday"] is False)
        check("近期列表取到 1 条", payload["_meta"]["recentCount"] == 1)
    except McpError as exc:
        check(f"传输层无异常（{exc}）", False)
    srv.shutdown()

    # --- 凭据解析：~/.config/magpie/library.json → 环境变量兜底 ---
    import tempfile
    global MCP_CONFIG
    saved_cfg = MCP_CONFIG
    saved_env = (os.environ.pop("RUNYAY_MCP_URL", None),
                 os.environ.pop("RUNYAY_MCP_TOKEN", None))
    tmpdir = Path(tempfile.mkdtemp())
    try:
        cases = [
            # --- magpie 主格式 mcp[] ---
            ("magpie mcp[]：常规 bearer",
             {"mcp": [{"name": "yayarun", "transport": "http", "url": "https://d/mcp",
                       "headers": {"Authorization": "Bearer TK4"}}]},
             ("https://d/mcp", "TK4", None)),
            ("magpie mcp[]：混有其他 MCP 时仍取跑鸭",
             {"mcp": [{"name": "other", "url": "https://o/mcp"},
                      {"name": "yayarun", "url": "https://e/mcp",
                       "headers": {"Authorization": "Bearer TK5"}}]},
             ("https://e/mcp", "TK5", None)),
            ("magpie mcp[]：键名写 RunYay-MCP 也能模糊匹配",
             {"mcp": [{"name": "RunYay-MCP", "url": "https://c/mcp",
                       "headers": {"Authorization": "Bearer TK3"}}]},
             ("https://c/mcp", "TK3", None)),
            ("magpie mcp[]：Authorization 无 Bearer 前缀",
             {"mcp": [{"name": "yayarun", "url": "https://b/mcp",
                       "headers": {"Authorization": "TK2"}}]},
             ("https://b/mcp", "TK2", None)),
            ("magpie mcp[]：缺 url 应报错",
             {"mcp": [{"name": "yayarun", "headers": {"Authorization": "Bearer T"}}]},
             (None, None, "缺 url")),
            ("magpie mcp[]：没有跑鸭条目应报错",
             {"mcp": [{"name": "other", "url": "https://o/mcp"}]},
             (None, None, "没有跑鸭条目")),
            # --- 兼容 claude 风格 mcpServers ---
            ("mcpServers（兼容）：常规 bearer",
             {"mcpServers": {"yayarun": {"url": "https://a/mcp",
                                         "headers": {"Authorization": "Bearer TK1"}}}},
             ("https://a/mcp", "TK1", None)),
            # --- 两套格式同时存在时，magpie 的 mcp[] 优先 ---
            ("mcp[] 与 mcpServers 并存时优先 mcp[]",
             {"mcp": [{"name": "yayarun", "url": "https://new/mcp",
                       "headers": {"Authorization": "Bearer NEW"}}],
              "mcpServers": {"yayarun": {"url": "https://old/mcp",
                                         "headers": {"Authorization": "Bearer OLD"}}}},
             ("https://new/mcp", "NEW", None)),
        ]
        for label, doc, (want_url, want_tok, want_err_frag) in cases:
            cfgfile = tmpdir / "library.json"
            cfgfile.write_text(json.dumps(doc), encoding="utf-8")
            MCP_CONFIG = str(cfgfile)
            got_url, got_tok, got_err = load_endpoint()
            if want_err_frag:
                good = got_url is None and want_err_frag in (got_err or "")
            else:
                good = got_url == want_url and got_tok == want_tok
            check(label, good)

        # 配置不存在 -> 环境变量兜底
        MCP_CONFIG = str(tmpdir / "does-not-exist.json")
        os.environ["RUNYAY_MCP_URL"] = "https://env.example.com/mcp"
        os.environ["RUNYAY_MCP_TOKEN"] = "ENVTOKEN"
        got_url, got_tok, _ = load_endpoint()
        check("配置缺失时回退环境变量", (got_url, got_tok) ==
              ("https://env.example.com/mcp", "ENVTOKEN"))

        # 配置文件在、但没有跑鸭条目 -> 同样回落环境变量
        noentry = tmpdir / "noentry.json"
        noentry.write_text(json.dumps({"mcp": [{"name": "other", "url": "https://o/mcp"}]}),
                           encoding="utf-8")
        MCP_CONFIG = str(noentry)
        got_url, got_tok, _ = load_endpoint()
        check("配置里无跑鸭条目时也回退环境变量",
              (got_url, got_tok) == ("https://env.example.com/mcp", "ENVTOKEN"))

        # 两者都没有 -> 明确报错、不回落其他来源
        os.environ.pop("RUNYAY_MCP_URL", None)
        os.environ.pop("RUNYAY_MCP_TOKEN", None)
        got_url, got_tok, got_err = load_endpoint()
        check("配置与环境变量都没有时应报错", got_url is None and got_tok is None and bool(got_err))
    finally:
        MCP_CONFIG = saved_cfg
        for k, v in zip(("RUNYAY_MCP_URL", "RUNYAY_MCP_TOKEN"), saved_env):
            if v is not None:
                os.environ[k] = v

    ok = all(results)
    print("[self-test] " + ("全部通过" if ok else "存在失败项"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="跑鸭 MCP 取数")
    ap.add_argument("--days", type=int, default=7, help="近期列表回看天数（含结束日），默认 7")
    ap.add_argument("--end", help="结束日 YYYYMMDD，默认今天")
    ap.add_argument("--out", default=None,
                    help="输出文件路径，默认 <项目目录>/.yayarun-daily-summary/_work/latest.json")
    ap.add_argument("--work-dir", default=None,
                    help="中间产物目录，默认 <项目目录>/.yayarun-daily-summary/_work")
    ap.add_argument("--self-test", action="store_true", help="本地假服务端到端自检")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.days < 1:
        print("[失败] --days 至少为 1", file=sys.stderr)
        return 1

    if args.end:
        try:
            end_day = datetime.strptime(args.end, "%Y%m%d").date()
        except ValueError:
            print("[失败] --end 格式应为 YYYYMMDD", file=sys.stderr)
            return 1
    else:
        end_day = date.today()

    url, token, err = load_endpoint()
    if not url:
        print(f"[失败] {err}", file=sys.stderr)
        return 2
    unsafe = check_transport_safe(url, token)
    if unsafe:
        print(f"[失败] {unsafe}", file=sys.stderr)
        return 2
    host = urllib.parse.urlsplit(url).hostname
    print(f"端点 {host} | 凭据 {'已加载' if token else '缺失(匿名)'} | 结束日 {end_day:%Y-%m-%d}")

    try:
        payload = fetch(url, token, args.days, end_day)
    except McpError as exc:
        print(f"[失败] {exc}", file=sys.stderr)
        return 1

    # 默认写到当前项目内，避免污染 magpie 托管的公共技能库
    if args.out:
        out = Path(os.path.expanduser(args.out))
    else:
        out = resolve_work_dir(args.work_dir) / "latest.json"
    write_atomic(out, json.dumps(payload, ensure_ascii=False, indent=2))

    latest, meta = payload["latest"], payload["_meta"]
    print(f"已写入 {out}")
    print(f"  activityId {latest.get('activityId')} | 距离 {(latest.get('distanceInMeters') or 0) / 1000:.2f} km | "
          f"分段 {meta['segmentsCount']} 条 | 近期 {meta['recentCount']} 条")
    if meta["runIsToday"] is False:
        # 对应 SKILL「前置：确认日期口径」：脚本不能替用户决定，只负责把事实亮出来
        print(f"[注意] 最新一次跑步是 {meta['runDate']}，不是 {end_day:%Y-%m-%d}（今天）。"
              f"卡片文件名 / Bark 日期请用 {meta['runDate']}，并先向用户确认是否用这条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())