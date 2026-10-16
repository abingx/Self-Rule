/**
 * 服务层：工资明细 / 带入 / 个税（次月计算）/ 银行卡 / 核对 / 手动改写
 *
 * 改写语义（本轮新增）：
 *  - 所有自动计算结果都可人工改写，并保留 auto 计算值用于区分与"还原"。
 *  - 改按依赖顺序向下游传播。
 */
import { openDb, listItems } from './db.js';
import {
  addMonths, yearOf, round2, periodRange, todayPeriod,
} from './period.js';
import { carryForward, ensureRecord, getRecord, getRegularValues, setRegularValue } from './carry.js';
import { calcTaxPeriod, finalCum, seedAuto } from './tax.js';
import {
  TAX_SEED_BY_TAX_PERIOD, CREATE_FUTURE_MONTHS,
} from './config.js';
import {
  loadOverrides, setOverride, clearOverride, field, val, pack, isOverridable,
  WAGE_OVERRIDE_FIELDS, TAX_OVERRIDE_FIELDS,
} from './override.js';

export function createService(filename) {
  const db = openDb(filename);
  const items = listItems(db);

  // ---------------- 工资明细 ----------------

  /**
   * 单月详情。
   * 计算顺序：常规项 → 应发合计 → 专项合计 → 个税(来自计税期) → 代扣合计 → 预计实发。
   * 每一步都先算 auto，再叠加改写；下游用上游的最终值。
   */
  function getMonth(period) {
    const rec = getRecord(db, period);
    const ovMap = loadOverrides(db, 'wage', period);
    const regular = {};
    const adjustments = [];

    if (rec) {
      const vals = getRegularValues(db, rec.id);
      for (const it of items) {
        const v = vals.get(it.id);
        regular[it.code] = v
          ? { amount: round2(v.amount), source: v.source, from: v.carried_from_period }
          : null;
      }
      const rows = db.prepare(`
        SELECT a.*, i.code, i.name, i.category FROM wage_adjustment a
        JOIN wage_item i ON i.id = a.item_id
        WHERE a.wage_record_id = ? ORDER BY a.id
      `).all(rec.id);
      for (const r of rows) {
        adjustments.push({
          id: r.id, code: r.code, name: r.name, category: r.category,
          type: r.adj_type, amount: round2(r.amount), refPeriod: r.ref_period, reason: r.reason,
        });
      }
    } else {
      for (const it of items) regular[it.code] = null;
    }

    // 应发合计
    const autoGross = round2(
      items.filter((i) => i.category === 'earning').reduce((s, i) => s + (regular[i.code]?.amount || 0), 0)
      + adjustments.filter((a) => a.category === 'earning')
        .reduce((s, a) => s + (a.type === 'makeup' ? a.amount : -a.amount), 0)
    );
    const fGross = field(ovMap, 'gross', autoGross);

    // 专项合计（同类代扣合并：基准 + 补扣）
    const autoSpecial = round2(
      items.filter((i) => i.category === 'deduction').reduce((s, i) => s + (regular[i.code]?.amount || 0), 0)
      + adjustments.filter((a) => a.category === 'deduction')
        .reduce((s, a) => s + (a.type === 'clawback' ? a.amount : -a.amount), 0)
    );
    const fSpecial = field(ovMap, 'special', autoSpecial);

    // 个税：某月的个税 = "计算月 == 该月"的计税期结果
    const taxPeriod = period;
    const taxDetail = getTaxPeriod(taxPeriod);
    const autoTax = taxDetail ? Number(taxDetail.total_tax.value) : 0;
    const fTax = field(ovMap, 'tax', round2(autoTax));

    // 代扣合计 = 专项合计 + 个税
    const fDeduct = field(ovMap, 'deduct', round2(val(fSpecial) + val(fTax)));

    // 预计实发 = 应发合计 - 代扣合计
    const fNet = field(ovMap, 'net', round2(val(fGross) - val(fDeduct)));

    return {
      period,
      exists: !!rec,
      status: rec ? rec.status : 'draft',
      remark: rec ? rec.remark : null,
      regular,
      adjustments,
      overrideOrder: WAGE_OVERRIDE_FIELDS.map((f) => f.field),
      // 计算结果：每个字段都带 auto/value/overridden
      gross: pack(fGross),
      special: pack(fSpecial),
      tax: pack(fTax),
      deduct: pack(fDeduct),
      net: pack(fNet),
      taxPeriod,
      taxDetail,
      anyOverridden: [fGross, fSpecial, fTax, fDeduct, fNet].some((x) => x.overridden),
    };
  }

  /** 采集某月"最终值"口径的收入/专项（用于计税输入），含改写 */
  function monthFinalInputs(period) {
    const rec = getRecord(db, period);
    const ovMap = loadOverrides(db, 'wage', period);
    let wageIncome = 0, specialDeduction = 0, otherDeduction = 0;
    if (rec) {
      const vals = getRegularValues(db, rec.id);
      const adjs = db.prepare(`
        SELECT a.adj_type, a.amount, i.category FROM wage_adjustment a
        JOIN wage_item i ON i.id = a.item_id WHERE a.wage_record_id = ?
      `).all(rec.id);
      for (const it of items) {
        const v = vals.get(it.id);
        const amt = v ? Number(v.amount) : 0;
        if (it.category === 'earning') wageIncome += amt;
        else if (it.category === 'deduction') specialDeduction += amt;
      }
      for (const a of adjs) {
        if (a.category === 'earning' && a.adj_type === 'makeup') wageIncome += Number(a.amount);
        if (a.category === 'deduction' && a.adj_type === 'clawback') specialDeduction += Number(a.amount);
      }
    }
    const fGross = field(ovMap, 'gross', round2(wageIncome));
    const fSpecial = field(ovMap, 'special', round2(specialDeduction));
    return {
      wageIncome: round2(val(fGross)),
      wageSupplement: 0,
      specialDeduction: round2(val(fSpecial)),
      otherDeduction: round2(otherDeduction),
    };
  }

  /** 保存单月（触发带入） */
  function saveMonth(period, payload) {
    const rec = ensureRecord(db, period);

    if (payload.remark !== undefined) {
      db.prepare(`UPDATE wage_record SET remark = ?, updated_at = datetime('now','localtime') WHERE id = ?`)
        .run(payload.remark, rec.id);
    }

    // 现有常规项取值（用于判断"值是否真的变了"，避免把整行带入值固化为手工值）
    const existing = getRegularValues(db, rec.id);

    for (const [code, amount] of Object.entries(payload.regular || {})) {
      const it = items.find((i) => i.code === code);
      if (!it) continue;
      const cur = existing.get(it.id);
      const curAmount = cur ? round2(cur.amount) : null;
      const nextAmount = (amount === null || amount === undefined || amount === '') ? null : round2(Number(amount));

      if (nextAmount === curAmount) continue; // 值未变化：保留原来源（带入/手工）

      if (nextAmount === null) {
        db.prepare(`DELETE FROM wage_item_value WHERE wage_record_id = ? AND item_id = ?`).run(rec.id, it.id);
      } else {
        setRegularValue(db, rec.id, it.id, nextAmount);
      }
    }

    if (payload.adjustments) {
      db.prepare(`DELETE FROM wage_adjustment WHERE wage_record_id = ?`).run(rec.id);
      for (const a of payload.adjustments) {
        const it = items.find((i) => i.code === a.code);
        if (!it || !a.amount) continue;
        db.prepare(`
          INSERT INTO wage_adjustment (wage_record_id, item_id, adj_type, amount, ref_period, reason)
          VALUES (?, ?, ?, ?, ?, ?)
        `).run(rec.id, it.id, a.type, round2(Number(a.amount)), a.refPeriod || null, a.reason || null);
      }
    }

    // 改写值（若有）
    applyOverrides('wage', period, payload.overrides);

    // 需求 2：保存草稿后触发带入（已确认月份不向外传播）
    // propagate=false 时只写入当前行，不带入后续月份（由前端弹窗让用户选择）。
    let logs = [];
    const propagate = payload.propagate !== false;
    if (propagate && rec.status !== 'confirmed') {
      logs = carryForward(db, period);
    }

    recalcTaxAround(period);
    return { month: getMonth(period), carryLogs: logs, propagated: propagate };
  }

  function applyOverrides(scope, scopeKey, overrides) {
    if (!overrides) return;
    for (const [f, v] of Object.entries(overrides)) {
      if (!isOverridable(scope, f)) continue;
      if (v === null || v === undefined || v === '') clearOverride(db, scope, scopeKey, f);
      else setOverride(db, scope, scopeKey, f, v, null);
    }
  }

  function confirmMonth(period, confirmed = true) {
    ensureRecord(db, period);
    db.prepare(`UPDATE wage_record SET status = ?, updated_at = datetime('now','localtime') WHERE period = ?`)
      .run(confirmed ? 'confirmed' : 'draft', period);
    recalcTaxAround(period);
    return getMonth(period);
  }

  // ---------------- 个税 ----------------

  function getTaxPeriod(taxPeriod) {
    const row = db.prepare(`SELECT * FROM tax_period WHERE tax_period = ?`).get(taxPeriod) || null;
    if (!row) return null;
    const autos = row.autos ? JSON.parse(row.autos) : {};
    const ovMap = loadOverrides(db, 'tax', taxPeriod);
    // 组装成带 auto/overridden 的结构
    const out = { ...row, autos: undefined };
    for (const f of TAX_OVERRIDE_FIELDS) {
      const value = row[f.field];
      const auto = f.field in autos ? autos[f.field] : value;
      out[f.field] = {
        auto: round2(auto),
        value: round2(value),
        overridden: !!ovMap[f.field],
        note: ovMap[f.field]?.note || null,
      };
    }
    out.anyOverridden = Object.keys(ovMap).length > 0;
    out.overrideOrder = TAX_OVERRIDE_FIELDS.map((f) => f.field);
    return out;
  }

  /** 采集某计税期的原始输入（自动值，不含税表改写） */
  function collectRaw(taxPeriod) {
    const wagePeriod = addMonths(taxPeriod, -1);
    const inputs = monthFinalInputs(wagePeriod);

    // 补计（目标计入工资）：到账月中未被确认为一次性奖金的目标收入
    const sup = db.prepare(`
      SELECT COALESCE(SUM(amount),0) AS s FROM bank_income
      WHERE period = ? AND is_bonus = 0 AND type = '目标'
    `).get(wagePeriod).s;

    const bonus = db.prepare(`SELECT * FROM bonus_selection WHERE tax_period = ?`).get(taxPeriod);

    return {
      wageIncome: round2(inputs.wageIncome),
      wageSupplement: round2(inputs.wageSupplement + Number(sup || 0)),
      specialDeduction: round2(inputs.specialDeduction),
      otherDeduction: round2(inputs.otherDeduction),
      bonusAmount: bonus ? round2(bonus.amount) : 0,
    };
  }

  /**
   * 逐期重算某【工资年】。
   * 口径 A：累计块 = 工资月年份；工资月 Y-01..Y-12 → 计税期 Y-02..Y+1-01。
   * 每个工资年 1 月累计从头开始（工作簿已验证：工资月 2026-01 行累计收入=11911、累计减除=5000）。
   * 跨年衔接：计税期 2026-01（工资月 2025-12）只写死结果。
   */
  function recalcYear(wageYear) {
    ensureSeedPeriods();

    let cum = {
      cum_income: pack(field({}, 'x', 0)),
      cum_base: pack(field({}, 'x', 0)),
      cum_special: pack(field({}, 'x', 0)),
      cum_other: pack(field({}, 'x', 0)),
      cum_paid: 0,
    };

    for (let m = 1; m <= 12; m++) {
      const wagePeriod = `${wageYear}-${String(m).padStart(2, '0')}`;
      const taxPeriod = addMonths(wagePeriod, 1);

      const seed = TAX_SEED_BY_TAX_PERIOD[taxPeriod];
      const raw = collectRaw(taxPeriod);
      const ovMap = loadOverrides(db, 'tax', taxPeriod);

      if (seed) {
        // 写死期：输入真实采集，个税结果写死
        const r = calcTaxPeriod(taxPeriod, { ...raw, cumPrev: cum }, ovMap);
        r.total_tax = field(ovMap, 'total_tax', round2(seed.amount));
        r.paid_tax = field(ovMap, 'paid_tax', round2(seed.amount));
        r.isSeeded = true;
        r.note = seed.note;
        upsertTaxPeriod(r);
        continue; // 不参与累计
      }

      const r = calcTaxPeriod(taxPeriod, { ...raw, cumPrev: cum }, ovMap);
      upsertTaxPeriod(r);
      cum = finalCum(r, cum);
    }
  }

  function ensureSeedPeriods() {
    for (const taxPeriod of Object.keys(TAX_SEED_BY_TAX_PERIOD)) {
      if (getTaxPeriodRow(taxPeriod)) continue;
      const ovMap = loadOverrides(db, 'tax', taxPeriod);
      const r = calcTaxPeriod(taxPeriod, {}, ovMap);
      r.total_tax = field(ovMap, 'total_tax', round2(seedAuto(taxPeriod)));
      r.paid_tax = field(ovMap, 'paid_tax', round2(seedAuto(taxPeriod)));
      r.isSeeded = true;
      upsertTaxPeriod(r);
    }
  }

  function getTaxPeriodRow(taxPeriod) {
    return db.prepare(`SELECT * FROM tax_period WHERE tax_period = ?`).get(taxPeriod) || null;
  }

  function upsertTaxPeriod(r) {
    const autos = {};
    for (const f of TAX_OVERRIDE_FIELDS) autos[f.field] = r[f.field]?.auto ?? 0;
    db.prepare(`
      INSERT INTO tax_period (tax_period, wage_period, wage_income, wage_supplement, special_deduction,
        other_deduction, cum_income, cum_base, cum_special, cum_other, additional, taxable,
        bonus_amount, bonus_tax, wage_tax, paid_tax, total_tax, is_seeded, autos, note, updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))
      ON CONFLICT(tax_period) DO UPDATE SET
        wage_period=excluded.wage_period, wage_income=excluded.wage_income,
        wage_supplement=excluded.wage_supplement, special_deduction=excluded.special_deduction,
        other_deduction=excluded.other_deduction, cum_income=excluded.cum_income,
        cum_base=excluded.cum_base, cum_special=excluded.cum_special, cum_other=excluded.cum_other,
        additional=excluded.additional, taxable=excluded.taxable, bonus_amount=excluded.bonus_amount,
        bonus_tax=excluded.bonus_tax, wage_tax=excluded.wage_tax, paid_tax=excluded.paid_tax,
        total_tax=excluded.total_tax, is_seeded=excluded.is_seeded, autos=excluded.autos,
        note=excluded.note, updated_at=datetime('now','localtime')
    `).run(
      r.taxPeriod, r.wagePeriod,
      round2(val(r.wage_income)), round2(val(r.wage_supplement)),
      round2(val(r.special_deduction)), round2(val(r.other_deduction)),
      round2(val(r.cum_income)), round2(val(r.cum_base)), round2(val(r.cum_special)),
      round2(val(r.cum_other)), round2(val(r.additional)), round2(val(r.taxable)),
      round2(val(r.bonus_amount)), round2(val(r.bonus_tax)), round2(val(r.wage_tax)),
      round2(val(r.paid_tax)), round2(val(r.total_tax)),
      r.isSeeded ? 1 : 0, JSON.stringify(autos), r.note
    );
  }

  function recalcTaxAround(period) {
    const y = yearOf(period);
    const years = new Set([y]);
    if (getRecord(db, `${y + 1}-01`)) years.add(y + 1);
    for (const yy of [...years].sort()) recalcYear(yy);
  }

  function recalcAll() {
    ensureSeedPeriods();
    const years = new Set();
    for (const r of db.prepare(`SELECT DISTINCT period FROM wage_record`).all()) years.add(yearOf(r.period));
    for (const r of db.prepare(`SELECT DISTINCT period FROM bank_income`).all()) years.add(yearOf(r.period));
    for (const tp of Object.keys(TAX_SEED_BY_TAX_PERIOD)) years.add(yearOf(addMonths(tp, -1)));
    years.add(yearOf(todayPeriod()));
    for (const y of [...years].sort()) recalcYear(y);
  }

  /** 设置/清除改写后，需要重算的范围 */
  function afterOverrideChange(scope, scopeKey) {
    if (scope === 'wage') recalcTaxAround(scopeKey);
    else recalcTaxAround(addMonths(scopeKey, -1));
  }

  function setTaxOverride(taxPeriod, fieldName, amount) {
    if (!getTaxPeriodRow(taxPeriod)) throw new Error(`计税期 ${taxPeriod} 不存在`);
    if (amount === null || amount === undefined || amount === '') {
      clearOverride(db, 'tax', taxPeriod, fieldName);
    } else {
      setOverride(db, 'tax', taxPeriod, fieldName, amount, null);
    }
    afterOverrideChange('tax', taxPeriod);
    return getTaxPeriod(taxPeriod);
  }

  function setWageOverride(period, fieldName, amount) {
    if (amount === null || amount === undefined || amount === '') {
      clearOverride(db, 'wage', period, fieldName);
    } else {
      setOverride(db, 'wage', period, fieldName, amount, null);
    }
    afterOverrideChange('wage', period);
    return getMonth(period);
  }

  function resetOverrides(scope, scopeKey) {
    db.prepare(`DELETE FROM value_override WHERE scope = ? AND scope_key = ?`).run(scope, scopeKey);
    afterOverrideChange(scope, scopeKey);
    return scope === 'wage' ? getMonth(scopeKey) : getTaxPeriod(scopeKey);
  }

  // ---------------- 视图 ----------------

  function getYearView(wageYear) {
    return periodRange(`${wageYear}-01`, `${wageYear}-12`).map((p) => getMonth(p));
  }

  /**
   * 计税期列表（按工资年）。
   * 额外包含跨年衔接期（计税期 Y-01，工资月 (Y-1)-12），它正是 Y 年 1 月工资行引用的税额。
   */
  function getTaxYear(wageYear) {
    const rows = db.prepare(`
      SELECT tax_period FROM tax_period WHERE wage_period >= ? AND wage_period <= ? ORDER BY wage_period
    `).all(`${wageYear}-01`, `${wageYear}-12`).map((r) => r.tax_period);

    const seedPeriod = `${wageYear}-01`;
    const seeded = getTaxPeriodRow(seedPeriod);
    if (seeded && Number(seeded.is_seeded) === 1 && !rows.includes(seedPeriod)) rows.unshift(seedPeriod);

    return rows.map((tp) => getTaxPeriod(tp));
  }

  // ---------------- 一次性奖金 ----------------

  function listBonusSelections() {
    return db.prepare(`SELECT * FROM bonus_selection ORDER BY tax_year DESC`).all();
  }

  function selectBonus(taxYear, { bankIncomeId = null, amount = null, note = null }) {
    const existing = db.prepare(`SELECT * FROM bonus_selection WHERE tax_year = ?`).get(taxYear);
    if (existing) throw new Error(`${taxYear} 年已确认一次性奖金，每年只能确认一笔`);

    let amt = amount, period = null;
    if (bankIncomeId) {
      const bank = db.prepare(`SELECT * FROM bank_income WHERE id = ?`).get(bankIncomeId);
      if (!bank) throw new Error('银行卡收入记录不存在');
      amt = bank.amount;
      period = bank.period;
      db.prepare(`UPDATE bank_income SET is_bonus = 1 WHERE id = ?`).run(bankIncomeId);
    }
    if (amt === null || amt === undefined) throw new Error('必须提供金额或银行卡收入记录');

    const taxPeriod = period ? addMonths(period, 1) : `${taxYear}-12`;
    db.prepare(`
      INSERT INTO bonus_selection (tax_year, tax_period, bank_income_id, amount, note)
      VALUES (?, ?, ?, ?, ?)
    `).run(taxYear, taxPeriod, bankIncomeId, round2(Number(amt)), note);

    recalcAll();
    return db.prepare(`SELECT * FROM bonus_selection WHERE tax_year = ?`).get(taxYear);
  }

  function clearBonus(taxYear) {
    const b = db.prepare(`SELECT * FROM bonus_selection WHERE tax_year = ?`).get(taxYear);
    if (b?.bank_income_id) {
      db.prepare(`UPDATE bank_income SET is_bonus = 0 WHERE id = ?`).run(b.bank_income_id);
    }
    db.prepare(`DELETE FROM bonus_selection WHERE tax_year = ?`).run(taxYear);
    recalcAll();
    return { ok: true };
  }

  // ---------------- 银行卡 ----------------

  function listBank({ from, to, type } = {}) {
    const where = [], args = [];
    if (from) { where.push('date >= ?'); args.push(from); }
    if (to) { where.push('date <= ?'); args.push(to); }
    if (type) { where.push('type = ?'); args.push(type); }
    const sql = `SELECT * FROM bank_income ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY date, id`;
    return db.prepare(sql).all(...args);
  }

  function addBank({ date, type, amount, note }) {
    const period = String(date).slice(0, 7);
    const info = db.prepare(`
      INSERT INTO bank_income (date, type, amount, note, period) VALUES (?,?,?,?,?)
    `).run(date, type, round2(Number(amount)), note || null, period);
    recalcAll();
    return db.prepare(`SELECT * FROM bank_income WHERE id = ?`).get(info.lastInsertRowid);
  }

  function updateBank(id, { date, type, amount, note }) {
    const cur = db.prepare(`SELECT * FROM bank_income WHERE id = ?`).get(id);
    if (!cur) throw new Error('记录不存在');
    const d = date ?? cur.date;
    db.prepare(`UPDATE bank_income SET date=?, type=?, amount=?, note=?, period=? WHERE id=?`)
      .run(d, type ?? cur.type,
        amount !== undefined ? round2(Number(amount)) : cur.amount,
        note ?? cur.note, String(d).slice(0, 7), id);
    recalcAll();
    return db.prepare(`SELECT * FROM bank_income WHERE id = ?`).get(id);
  }

  function deleteBank(id) {
    db.prepare(`DELETE FROM bank_income WHERE id = ?`).run(id);
    recalcAll();
  }

  // ---------------- 核对 ----------------

  function getReconcile(wageYear) {
    const from = `${wageYear}-01`, to = `${wageYear}-12`;
    const bankRows = db.prepare(`SELECT * FROM bank_income WHERE period >= ? AND period <= ?`).all(from, to);
    const types = [...new Set(bankRows.map((r) => r.type))];
    return periodRange(from, to).map((p) => {
      const m = getMonth(p);
      const byType = {};
      for (const t of types) byType[t] = 0;
      let actual = 0;
      for (const r of bankRows) {
        if (r.period === p) { byType[r.type] = round2((byType[r.type] || 0) + r.amount); actual += r.amount; }
      }
      const diff = round2(actual - m.net.value);
      return {
        period: p,
        expectedNet: m.net.value,
        expectedNetAuto: m.net.auto,
        netOverridden: m.net.overridden,
        byType,
        actual: round2(actual),
        diff,
      };
    });
  }

  function listPeriods() {
    return db.prepare(`SELECT period, status FROM wage_record ORDER BY period`).all();
  }

  return {
    db, items,
    getMonth, saveMonth, confirmMonth, getYearView, listPeriods, getTaxYear,
    recalcYear, recalcAll, getTaxPeriod, getTaxPeriodRow,
    selectBonus, clearBonus, listBonusSelections,
    listBank, addBank, updateBank, deleteBank, getReconcile,
    setWageOverride, setTaxOverride, resetOverrides,
    WAGE_OVERRIDE_FIELDS, TAX_OVERRIDE_FIELDS,
  };
}
