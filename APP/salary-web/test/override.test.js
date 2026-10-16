/**
 * 手动改写（override）测试
 *
 * 需求：所有自动计算的结果允许手动修改，并能明显区分"计算值"与"改写值"。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createService } from '../src/service.js';
import { round2 } from '../src/period.js';

const V = (x) => (x && typeof x === 'object' && 'value' in x ? x.value : x);
const A = (x) => (x && typeof x === 'object' && 'auto' in x ? x.auto : x);
const OV = (x) => !!(x && typeof x === 'object' && x.overridden);

function fresh() { return createService(':memory:'); }

test('改写：工资月结果字段可改写，并保留 auto 计算值', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000, fund: 1000 } });

  let m = svc.getMonth('2026-01');
  assert.equal(V(m.gross), 10000, '应发合计自动值');
  assert.equal(OV(m.gross), false, '默认未改写');
  assert.ok(m.gross.auto !== undefined, '应回传 auto 值');

  // 改写应发合计
  m = svc.setWageOverride('2026-01', 'gross', 12345);
  assert.equal(V(m.gross), 12345, '改写后取改写值');
  assert.equal(A(m.gross), 10000, 'auto 值仍保留为原计算值');
  assert.equal(OV(m.gross), true, '应标记为已改写');
  assert.equal(m.anyOverridden, true);

  // 下游自动跟随：代扣合计 = 专项 + 个税（不受应发影响）；预计实发 = 应发 - 代扣
  assert.equal(V(m.net), round2(12345 - V(m.deduct)));
});

test('改写：清除改写后恢复自动计算', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000 } });
  svc.setWageOverride('2026-01', 'gross', 99999);
  assert.equal(V(svc.getMonth('2026-01').gross), 99999);

  const m = svc.setWageOverride('2026-01', 'gross', null);
  assert.equal(V(m.gross), 10000, '应恢复自动值');
  assert.equal(OV(m.gross), false);
});

test('改写：一次性还原某月全部改写', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000, fund: 1000 } });
  svc.setWageOverride('2026-01', 'gross', 1);
  svc.setWageOverride('2026-01', 'net', 2);
  const m = svc.resetOverrides('wage', '2026-01');
  assert.equal(OV(m.gross), false);
  assert.equal(OV(m.net), false);
  assert.equal(m.anyOverridden, false);
});

test('改写：应发合计改写会向下游传播到计税输入', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000 } });
  // 计税期 2026-02 依据 1 月收入
  assert.equal(V(svc.getTaxPeriod('2026-02').wage_income), 10000);

  svc.setWageOverride('2026-01', 'gross', 20000);
  assert.equal(V(svc.getTaxPeriod('2026-02').wage_income), 20000, '改写应发后计税输入应跟随');
});

test('改写：专项合计改写会传播到计税的专项扣除', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000, fund: 1000 } });
  assert.equal(V(svc.getTaxPeriod('2026-02').special_deduction), 1000);

  svc.setWageOverride('2026-01', 'special', 1500);
  assert.equal(V(svc.getTaxPeriod('2026-02').special_deduction), 1500);
});

test('改写：个税字段改写独立于计税表（覆盖工资行的税额）', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000 } });
  const before = V(svc.getMonth('2026-01').tax);

  const m = svc.setWageOverride('2026-01', 'tax', 888);
  assert.equal(V(m.tax), 888);
  assert.equal(A(m.tax), before, 'auto 保留');
  // 代扣合计与实发随之变化
  assert.equal(V(m.deduct), round2(V(m.special) + 888));
  assert.equal(V(m.net), round2(V(m.gross) - V(m.deduct)));
});

test('改写：计税期字段可改写，且按依赖顺序向下游传播', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 30000 } });
  const p2 = '2026-02';

  // 原始：30000 - 5000 - 3000 = 22000 → 3% = 660
  assert.equal(V(svc.getTaxPeriod(p2).taxable), 22000);
  assert.equal(V(svc.getTaxPeriod(p2).paid_tax), 660);

  // 改累计收入 → 应纳税额、税额应跟随
  svc.setTaxOverride(p2, 'cum_income', 100000);
  const t = svc.getTaxPeriod(p2);
  assert.equal(V(t.cum_income), 100000);
  assert.equal(A(t.cum_income), 30000, 'auto 保留');
  assert.equal(V(t.taxable), round2(100000 - 5000 - 3000), '应纳税额跟随');
  assert.equal(V(t.wage_tax), round2(92000 * 0.1 - 2520), '累计税额跟随');
  assert.equal(V(t.paid_tax), round2(92000 * 0.1 - 2520), '本期应缴跟随');
});

test('改写：下游自有改写优先于上游传播', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 30000 } });
  const p2 = '2026-02';

  // 先锁定本期应缴
  svc.setTaxOverride(p2, 'paid_tax', 999);
  // 再改上游累计收入（会重算，但不应覆盖已改写的下游）
  svc.setTaxOverride(p2, 'cum_income', 100000);

  const t = svc.getTaxPeriod(p2);
  assert.equal(V(t.cum_income), 100000);
  assert.equal(V(t.paid_tax), 999, '下游改写优先，不被上游传播覆盖');
  assert.equal(OV(t.paid_tax), true);
});

test('改写：合计字段被改写后不再等于奖金税+本期应缴（以改写为准）', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 30000 } });
  const p2 = '2026-02';
  svc.setTaxOverride(p2, 'total_tax', 1.23);
  const t = svc.getTaxPeriod(p2);
  assert.equal(V(t.total_tax), 1.23);
  assert.equal(OV(t.total_tax), true);
});

test('改写：跨年写死期也可改写', () => {
  const svc = fresh();
  svc.recalcAll();
  assert.equal(V(svc.getTaxPeriod('2026-01').total_tax), 29.36);
  svc.setTaxOverride('2026-01', 'total_tax', 50);
  assert.equal(V(svc.getTaxPeriod('2026-01').total_tax), 50);
  assert.equal(A(svc.getTaxPeriod('2026-01').total_tax), 29.36);
});

test('改写：非法字段被拒绝', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1 } });
  assert.throws(() => svc.setWageOverride('2026-01', 'not_a_field', 1), /不支持改写/);
});

test('改写：计税累计会采纳上游改写值（跨期传播）', () => {
  const svc = fresh();
  for (let m = 1; m <= 2; m++) {
    svc.saveMonth(`2026-${String(m).padStart(2, '0')}`, { regular: { post_salary: 30000 } });
  }
  // 3 月计税：累计收入应为 2 月累计 + 3 月收入。
  // 改 2 月(计税期 2026-03)的累计收入，应影响 3 月(计税期 2026-04)的期初。
  const p3 = '2026-03';
  const p4 = '2026-04';
  svc.setTaxOverride(p3, 'cum_income', 500000);

  const t4 = svc.getTaxPeriod(p4);
  // 60000 中 2 月那 30000 被替换为 500000 的累计，故 4 月累计 = 500000 + 30000
  assert.equal(V(t4.cum_income), 530000, '下游期初应采纳上游改写后的累计');
});

test('改写：API 层返回结构与字段清单一致', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  for (const f of svc.WAGE_OVERRIDE_FIELDS) {
    const m = svc.getMonth('2026-01');
    assert.ok(f.field in m, `工资月应含结果字段 ${f.field}`);
  }
  for (const f of svc.TAX_OVERRIDE_FIELDS) {
    const t = svc.getTaxPeriod('2026-02');
    assert.ok(f.field in t, `计税期应含结果字段 ${f.field}`);
    assert.ok('auto' in t[f.field] && 'value' in t[f.field] && 'overridden' in t[f.field],
      `${f.field} 应含 auto/value/overridden`);
  }
});
