/**
 * 手动改写（override）支持
 *
 * 需求：所有自动计算的结果都允许手动修改，并能明显区分"计算值"与"改写值"。
 *
 * 语义：
 *  - 每个可改写字段都有公式算出的 auto 值；
 *  - 若存在改写记录，则该字段的最终值取改写值，但 auto 值仍然保留并回传给前端；
 *  - 改写按依赖顺序向下游传播：改了上游（如累计收入），下游（应纳税额、税额）会基于改写值重算；
 *    下游若自己也有改写，则以下游自己的改写为准。
 */

export const WAGE_OVERRIDE_FIELDS = [
  { field: 'gross', label: '应发合计' },
  { field: 'special', label: '专项合计' },
  { field: 'tax', label: '个税' },
  { field: 'deduct', label: '代扣合计' },
  { field: 'net', label: '预计实发' },
];

export const TAX_OVERRIDE_FIELDS = [
  { field: 'wage_income', label: '工资收入' },
  { field: 'wage_supplement', label: '补计' },
  { field: 'special_deduction', label: '专项扣除' },
  { field: 'other_deduction', label: '其他扣除' },
  { field: 'cum_income', label: '累计收入' },
  { field: 'cum_base', label: '累计减除' },
  { field: 'cum_special', label: '专项累计' },
  { field: 'cum_other', label: '其他扣除累计' },
  { field: 'additional', label: '专项附加' },
  { field: 'taxable', label: '应纳税额' },
  { field: 'bonus_amount', label: '一次性奖金' },
  { field: 'bonus_tax', label: '奖金税' },
  { field: 'wage_tax', label: '累计税额' },
  { field: 'paid_tax', label: '本期应缴' },
  { field: 'total_tax', label: '合计' },
];

export const OVERRIDE_SCOPES = {
  wage: WAGE_OVERRIDE_FIELDS,
  tax: TAX_OVERRIDE_FIELDS,
};

export function isOverridable(scope, field) {
  return (OVERRIDE_SCOPES[scope] || []).some((f) => f.field === field);
}

/**
 * 取某 period 的改写表：{ field: { amount, note } }
 */
export function loadOverrides(db, scope, scopeKey) {
  const rows = db.prepare(`
    SELECT field, amount, note FROM value_override WHERE scope = ? AND scope_key = ?
  `).all(scope, scopeKey);
  const map = {};
  for (const r of rows) map[r.field] = { amount: r.amount, note: r.note };
  return map;
}

export function setOverride(db, scope, scopeKey, field, amount, note) {
  if (!isOverridable(scope, field)) throw new Error(`字段 ${field} 不支持改写`);
  const num = Number(amount);
  if (!Number.isFinite(num)) throw new Error('改写值必须是数字');
  db.prepare(`
    INSERT INTO value_override (scope, scope_key, field, amount, note)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(scope, scope_key, field) DO UPDATE SET
      amount = excluded.amount, note = excluded.note,
      created_at = datetime('now','localtime')
  `).run(scope, scopeKey, field, num, note || null);
}

export function clearOverride(db, scope, scopeKey, field) {
  db.prepare(`DELETE FROM value_override WHERE scope = ? AND scope_key = ? AND field = ?`)
    .run(scope, scopeKey, field);
}

/** 一次性取出某字段的改写记录（无则 undefined） */
export function ovOf(ovMap, field) {
  return ovMap ? ovMap[field] : undefined;
}

/**
 * 计算一个字段：先有公式 auto 值，再看是否被改写。
 * @returns {{auto:number, value:number, overridden:boolean, note:(string|null)}}
 */
export function field(ovMap, name, autoValue) {
  const auto = Number.isFinite(autoValue) ? autoValue : 0;
  const o = ovOf(ovMap, name);
  if (!o) return { auto, value: auto, overridden: false, note: null };
  return { auto, value: Number(o.amount), overridden: true, note: o.note || null };
}

/** 只取最终值 */
export function val(x) {
  return x && typeof x === 'object' && 'value' in x ? x.value : x;
}

/** 序列化给前端/存库：把 {auto,value,overridden,note} 压平 */
export function pack(x) {
  return { auto: round2(x.auto), value: round2(x.value), overridden: x.overridden, note: x.note };
}

function round2(n) {
  if (!Number.isFinite(n)) return 0;
  return Math.round((n + Number.EPSILON) * 100) / 100;
}
