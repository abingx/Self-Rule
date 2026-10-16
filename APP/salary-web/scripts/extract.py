#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 工资.xlsx 抽取历史数据 -> data/seed.json（同时导出缓存计算值用于校验）

用法：
    python3 scripts/extract.py [工资.xlsx 路径]

不传路径时依次尝试以下位置，找到即用：
    1. ../工资.xlsx                      （仓库内 APP/工资.xlsx）
    2. ~/DSH/工资.xlsx                   （原始来源目录）
本脚本仅供口径核对，业务数据不由此导入。
"""
import json, datetime, os, sys
import openpyxl

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = [
    os.path.join(_HERE, "..", "..", "工资.xlsx"),
    os.path.expanduser("~/DSH/工资.xlsx"),
]

if len(sys.argv) > 1:
    SRC = sys.argv[1]
else:
    SRC = next((p for p in _CANDIDATES if os.path.exists(p)), _CANDIDATES[0])

OUT = os.path.join(_HERE, "..", "data", "seed.json")

if not os.path.exists(SRC):
    sys.exit(
        "未找到 工资.xlsx，请显式传入路径：\n"
        "    python3 scripts/extract.py /path/to/工资.xlsx\n"
        "已尝试：\n    " + "\n    ".join(_CANDIDATES)
    )

wb = openpyxl.load_workbook(SRC, data_only=True)


def d(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d")
    return v


def ym(v):
    """把 datetime / excel 序列号 / 字符串统一成 YYYY-MM"""
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m")
    if isinstance(v, (int, float)):
        base = datetime.date(1899, 12, 30)
        return (base + datetime.timedelta(days=int(v))).strftime("%Y-%m")
    return str(v)[:7]


# ---------- 工资核实 ----------
ws = wb["工资核实"]
EARN_ITEMS = [
    ("post_salary", "职务", 2, 3),
    ("grade_salary", "级别", 4, 5),
    ("reserve_allowance", "保留补贴", 6, 7),
    ("living_allowance", "生活性补贴", 8, 9),
    ("work_allowance", "工作性津贴", 10, 11),
    ("base_perf", "基础绩效", 12, 13),
]
DED_ITEMS = [
    ("fund", "公积金", 15),
    ("medical", "医保", 16),
    ("pension", "养老", 17),
    ("annuity", "年金", 18),
]

wages = []
for r in range(3, 401):
    a = ws.cell(r, 1).value
    if a is None:
        continue
    period = ym(a)
    if not period or len(period) != 7:
        continue
    rec = {
        "period": period,
        "regular": {},
        "adjustments": [],
        "taxActual": ws.cell(r, 19).value,      # S 个税（缓存值，历史手填/公式结果）
        "grossCalc": ws.cell(r, 14).value,      # N 应发合计
        "deductCalc": ws.cell(r, 20).value,     # T 代扣合计
        "netCalc": ws.cell(r, 21).value,        # U 预计实发
        "remark": ws.cell(r, 22).value,
    }
    for code, name, c_main, c_adj in EARN_ITEMS:
        if ws.cell(r, c_main).value is not None:
            rec["regular"][code] = ws.cell(r, c_main).value
        if ws.cell(r, c_adj).value is not None:
            rec["adjustments"].append(
                {"code": code, "type": "makeup", "amount": ws.cell(r, c_adj).value, "refPeriod": None}
            )
    for code, name, c in DED_ITEMS:
        if ws.cell(r, c).value is not None:
            rec["regular"][code] = ws.cell(r, c).value
    wages.append(rec)

# ---------- 个税计算表 ----------
ws = wb["个税计算表"]
tax_rows = []
for r in range(2, 50):
    a = ws.cell(r, 1).value
    if a is None:
        continue
    tax_rows.append({
        "wagePeriod": ym(a),
        "taxPeriod": ym(ws.cell(r, 2).value),
        "bonusAmount": ws.cell(r, 3).value,        # C
        "wageIncome": ws.cell(r, 4).value,         # D（可能是公式->缓存值）
        "wageSupplement": ws.cell(r, 5).value,     # E
        "cumIncome": ws.cell(r, 6).value,          # F
        "cumBase": ws.cell(r, 7).value,            # G
        "special": ws.cell(r, 8).value,            # H
        "cumSpecial": ws.cell(r, 9).value,         # I
        "other": ws.cell(r, 10).value,             # J
        "cumOther": ws.cell(r, 11).value,          # K
        "additional": ws.cell(r, 12).value,        # L
        "taxable": ws.cell(r, 13).value,           # M
        "bonusTax": ws.cell(r, 14).value,          # N
        "wageTax": ws.cell(r, 15).value,           # O
        "paidTax": ws.cell(r, 16).value,           # P
        "totalTax": ws.cell(r, 17).value,          # Q
    })

# ---------- 银行卡收入 ----------
ws = wb["银行卡收入"]
bank = []
for r in range(2, 226):
    a = ws.cell(r, 1).value
    if a is None:
        continue
    bank.append({
        "date": d(a),
        "type": ws.cell(r, 2).value,
        "amount": ws.cell(r, 3).value,
        "note": ws.cell(r, 4).value,
    })

data = {"wages": wages, "taxRows": tax_rows, "bank": bank}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

print("工资核实 月份数:", len(wages), wages[0]["period"], "->", wages[-1]["period"])
print("个税行数:", len(tax_rows), tax_rows[0]["wagePeriod"], "->", tax_rows[-1]["wagePeriod"])
print("银行流水条数:", len(bank), bank[0]["date"], "->", bank[-1]["date"])
print("已写出:", os.path.abspath(OUT))
