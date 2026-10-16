/**
 * 数据库层：使用 Node 内置 node:sqlite，零第三方依赖。
 * 零初始业务数据：只建表 + 写入工资项字典（可用于手工录入测试）。
 */
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WAGE_ITEMS, BANK_TYPES } from './config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, '..', 'data');

export const SCHEMA = `
PRAGMA foreign_keys = ON;

-- 工资项字典：支持后续增删/改名/调整顺序（本期暂不含改名 UI）
CREATE TABLE IF NOT EXISTS wage_item (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  code          TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  category      TEXT NOT NULL CHECK (category IN ('earning','deduction')),
  side          TEXT NOT NULL DEFAULT 'regular' CHECK (side IN ('regular','adjustment')),
  carry_forward INTEGER NOT NULL DEFAULT 1,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1
);

-- 月度工资记录
CREATE TABLE IF NOT EXISTS wage_record (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  period       TEXT NOT NULL UNIQUE,             -- YYYY-MM
  status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed')),
  remark       TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 常规项取值（只装 regular，"带入下月"只扫这张表）
CREATE TABLE IF NOT EXISTS wage_item_value (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  wage_record_id        INTEGER NOT NULL REFERENCES wage_record(id) ON DELETE CASCADE,
  item_id               INTEGER NOT NULL REFERENCES wage_item(id),
  amount                REAL NOT NULL DEFAULT 0,
  source                TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','carried')),
  carried_from_period   TEXT,
  UNIQUE (wage_record_id, item_id)
);

-- 补发/补扣（独立存放，天然不参与带入）
CREATE TABLE IF NOT EXISTS wage_adjustment (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  wage_record_id INTEGER NOT NULL REFERENCES wage_record(id) ON DELETE CASCADE,
  item_id        INTEGER NOT NULL REFERENCES wage_item(id),
  adj_type       TEXT NOT NULL CHECK (adj_type IN ('makeup','clawback')),
  amount         REAL NOT NULL DEFAULT 0,
  ref_period     TEXT,
  reason         TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 计税期：计算月 = 工资月 + 1（次月计算上月）
CREATE TABLE IF NOT EXISTS tax_period (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  tax_period         TEXT NOT NULL UNIQUE,       -- 计算月/申报月 YYYY-MM
  wage_period        TEXT NOT NULL,              -- 工资月 = 计算月 - 1
  wage_income        REAL NOT NULL DEFAULT 0,    -- 依据的"工资收入"
  wage_supplement    REAL NOT NULL DEFAULT 0,    -- 补计（目标计入工资）
  special_deduction  REAL NOT NULL DEFAULT 0,    -- 本期专项扣除（同类代扣合并）
  other_deduction    REAL NOT NULL DEFAULT 0,
  -- 以下为计算结果快照
  cum_income         REAL NOT NULL DEFAULT 0,
  cum_base           REAL NOT NULL DEFAULT 0,
  cum_special        REAL NOT NULL DEFAULT 0,
  cum_other          REAL NOT NULL DEFAULT 0,
  additional         REAL NOT NULL DEFAULT 0,
  taxable            REAL NOT NULL DEFAULT 0,
  bonus_amount       REAL NOT NULL DEFAULT 0,    -- 一次性奖金（单独计税）
  bonus_tax          REAL NOT NULL DEFAULT 0,
  wage_tax           REAL NOT NULL DEFAULT 0,    -- 累计已算税额
  paid_tax           REAL NOT NULL DEFAULT 0,    -- 本期应缴（工资部分）
  total_tax          REAL NOT NULL DEFAULT 0,    -- 奖金税 + 本期应缴
  is_seeded          INTEGER NOT NULL DEFAULT 0, -- 是否使用写死的跨年衔接值
  autos              TEXT,                       -- JSON：各字段的自动计算值（用于区分计算/改写）
  note               TEXT,
  updated_at         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 一次性奖金：同一目标可能多笔，每年只能确认一笔（第 16 条）
CREATE TABLE IF NOT EXISTS bonus_selection (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  tax_year    INTEGER NOT NULL UNIQUE,          -- 每年只能一笔
  tax_period  TEXT NOT NULL,                    -- 记入哪个计税期
  bank_income_id INTEGER,                       -- 来自哪条银行卡目标流水
  amount      REAL NOT NULL,
  note        TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 银行卡实际收入
CREATE TABLE IF NOT EXISTS bank_income (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  date         TEXT NOT NULL,
  type         TEXT NOT NULL,
  amount       REAL NOT NULL,
  note         TEXT,
  is_bonus     INTEGER NOT NULL DEFAULT 0,      -- 是否被确认为一次性奖金
  period       TEXT NOT NULL,                   -- YYYY-MM，按到账日期
  created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 带入审计日志
CREATE TABLE IF NOT EXISTS carry_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  from_period   TEXT NOT NULL,
  to_period     TEXT NOT NULL,
  item_code     TEXT NOT NULL,
  old_value     REAL,
  new_value     REAL,
  action        TEXT NOT NULL,                  -- carried | skipped_manual | skipped_confirmed
  created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- 手动改写：所有自动计算结果均可被人工覆盖，且保留 auto 计算值以便区分/还原
CREATE TABLE IF NOT EXISTS value_override (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  scope      TEXT NOT NULL CHECK (scope IN ('wage','tax')),
  scope_key  TEXT NOT NULL,          -- wage: YYYY-MM ; tax: 计税期 YYYY-MM
  field      TEXT NOT NULL,
  amount     REAL NOT NULL,
  note       TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE (scope, scope_key, field)
);

CREATE INDEX IF NOT EXISTS idx_wiv_record ON wage_item_value(wage_record_id);
CREATE INDEX IF NOT EXISTS idx_adj_record ON wage_adjustment(wage_record_id);
CREATE INDEX IF NOT EXISTS idx_bank_period ON bank_income(period);
CREATE INDEX IF NOT EXISTS idx_tax_period ON tax_period(tax_period);
`;

export function openDb(filename = 'salary.db') {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const file = filename === ':memory:'
    ? ':memory:'
    : (path.isAbsolute(filename) ? filename : path.join(DATA_DIR, filename));
  if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec(SCHEMA);
  seedItems(db);
  return db;
}

/** 写入/对齐工资项字典（幂等） */
export function seedItems(db) {
  const up = db.prepare(`
    INSERT INTO wage_item (code, name, category, side, carry_forward, sort_order, is_active)
    VALUES (?, ?, ?, ?, ?, ?, 1)
    ON CONFLICT(code) DO UPDATE SET
      name = excluded.name,
      category = excluded.category,
      side = excluded.side,
      carry_forward = excluded.carry_forward,
      sort_order = excluded.sort_order
  `);
  for (const it of WAGE_ITEMS) {
    up.run(it.code, it.name, it.category, it.side, it.carry ? 1 : 0, it.sort);
  }
}

export function listItems(db) {
  return db.prepare(`SELECT * FROM wage_item WHERE is_active = 1 ORDER BY sort_order, id`).all();
}

export function itemByCode(db, code) {
  return db.prepare(`SELECT * FROM wage_item WHERE code = ?`).get(code);
}

export { BANK_TYPES, DATA_DIR };
