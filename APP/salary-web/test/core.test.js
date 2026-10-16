/**
 * 核心逻辑测试：零依赖 node:test
 * 覆盖：带入（补发补扣不带入/级联/12月跨年）、个税次月计算、跨年写死
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createService } from '../src/service.js';
import { taxPeriodOf, addMonths, round2 } from '../src/period.js';
import { calcBonusTax, calcCumulativeTax } from '../src/tax.js';

/** 取结果字段的最终值（结果字段形如 { auto, value, overridden }） */
const V = (x) => (x && typeof x === 'object' && 'value' in x ? x.value : x);
const A = (x) => (x && typeof x === 'object' && 'auto' in x ? x.auto : x);

function fresh() {
  return createService(':memory:');
}

test('期间工具：次月计算上月', () => {
  assert.equal(taxPeriodOf('2026-01'), '2026-02');
  assert.equal(taxPeriodOf('2026-12'), '2027-01');
  assert.equal(addMonths('2026-12', 1), '2027-01');
});

test('税率表：一次性奖金与累计预扣', () => {
  assert.equal(calcBonusTax(36000), round2(36000 * 0.03));
  assert.equal(calcBonusTax(0), 0);
  assert.equal(calcCumulativeTax(0), 0);
  assert.equal(calcCumulativeTax(36000), round2(36000 * 0.03));
  assert.equal(calcCumulativeTax(100000), round2(100000 * 0.1 - 2520));
});

test('带入：常规项带入下月，补发补扣不带入', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', {
    regular: { post_salary: 1000, grade_salary: 2000, fund: 100 },
    adjustments: [
      { code: 'post_salary', type: 'makeup', amount: 500 },
      { code: 'fund', type: 'clawback', amount: 60 },
    ],
  });

  const feb = svc.getMonth('2026-02');
  // 常规项带入
  assert.equal(feb.regular.post_salary.amount, 1000);
  assert.equal(feb.regular.post_salary.source, 'carried');
  assert.equal(feb.regular.grade_salary.amount, 2000);
  assert.equal(feb.regular.fund.amount, 100);
  // 补发补扣不带入
  assert.equal(feb.adjustments.length, 0);

  // 应发合计：1月 = 1000+2000+500 = 3500
  const jan = svc.getMonth('2026-01');
  assert.equal(V(jan.gross), 3500);
  // 专项：公积金 100（基准）+ 60（补扣）= 160
  assert.equal(V(jan.special), 160);
});

test('带入：级联到更后月份', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  svc.saveMonth('2026-02', { regular: {} }); // 触发 2 月保存，3 月带入
  const mar = svc.getMonth('2026-03');
  assert.equal(mar.regular.post_salary.amount, 1000);
  assert.equal(mar.regular.post_salary.source, 'carried');
});

test('带入：修改 1 月会级联更新后续手工未占用月份', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  svc.saveMonth('2026-02', { regular: {} });   // 2、3 月带入 1000
  svc.saveMonth('2026-03', { regular: {} });

  // 修改 1 月
  svc.saveMonth('2026-01', { regular: { post_salary: 1500 } });
  assert.equal(svc.getMonth('2026-01').regular.post_salary.amount, 1500);
  assert.equal(svc.getMonth('2026-02').regular.post_salary.amount, 1500);
  assert.equal(svc.getMonth('2026-03').regular.post_salary.amount, 1500);
});

test('带入：下月已有手工值时保留手工值', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  svc.saveMonth('2026-02', { regular: { post_salary: 2222 } }); // 手工
  svc.saveMonth('2026-01', { regular: { post_salary: 1500 } }); // 改 1 月
  // 2 月手工值不被覆盖
  assert.equal(svc.getMonth('2026-02').regular.post_salary.amount, 2222);
  assert.equal(svc.getMonth('2026-02').regular.post_salary.source, 'manual');
});

test('带入：12 月修改后带入次年 1 月', () => {
  const svc = fresh();
  svc.saveMonth('2026-12', { regular: { post_salary: 3000 } });
  const jan27 = svc.getMonth('2027-01');
  assert.equal(jan27.regular.post_salary.amount, 3000);
});

test('带入：已确认月份不向外传播', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  svc.saveMonth('2026-02', { regular: {} });        // 2 月带入 1000
  svc.confirmMonth('2026-02', true);                // 2 月确认
  svc.saveMonth('2026-01', { regular: { post_salary: 9999 } }); // 改 1 月
  // 2 月已确认，不被覆盖
  assert.equal(svc.getMonth('2026-02').regular.post_salary.amount, 1000);
});

test('带入：未到达月份只生成不显示（记录存在但可标记为未来）', () => {
  const svc = fresh();
  svc.saveMonth('2026-05', { regular: { post_salary: 1234 } });
  const periods = svc.listPeriods().map((p) => p.period);
  assert.ok(periods.includes('2026-06'), '下月记录已生成');
});

test('带入：从录入行一路延伸到当前月（空库录入 1 月 → 带到当前月）', () => {
  const svc = fresh();
  const todayP = new Date().toISOString().slice(0, 7); // 当前月 YYYY-MM
  const year = Number(todayP.slice(0, 4));
  const jan = `${year}-01`;
  svc.saveMonth(jan, { regular: { post_salary: 5000 } });

  // 当前月及其之前的每个月都应已被带入相同值
  const monthsToToday = Number(todayP.slice(5, 7));
  for (let m = 1; m <= monthsToToday; m++) {
    const p = `${year}-${String(m).padStart(2, '0')}`;
    const v = svc.getMonth(p).regular.post_salary;
    assert.ok(v, `${p} 应有带入值`);
    assert.equal(v.amount, 5000, `${p} 带入值应为 5000`);
  }
  // 保存行紧邻的下月一定生成（未到达只生成不显示）
  assert.ok(svc.listPeriods().map((x) => x.period).includes(`${year}-02`), '紧邻下月记录已生成');
});

test('保存：propagate=false 只改当前行，不跨行带入', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 1000 } });
  svc.saveMonth('2026-02', { regular: {} }); // 2 月带入 1000

  // 只改 2 月：不传播
  const r = svc.saveMonth('2026-02', { regular: { post_salary: 7777 }, propagate: false });
  assert.equal(r.propagated, false);
  assert.equal(svc.getMonth('2026-02').regular.post_salary.amount, 7777);
  // 3 月保持不变（没有被 2 月的新值覆盖）
  assert.equal(svc.getMonth('2026-03').regular.post_salary.amount, 1000);

  // 默认（不传 propagate）= 传播
  svc.saveMonth('2026-02', { regular: { post_salary: 5555 } });
  assert.equal(svc.getMonth('2026-03').regular.post_salary.amount, 5555);
});

test('个税：次月计算上月（1 月工资 → 2 月计税）', () => {
  const svc = fresh();
  svc.saveMonth('2026-01', { regular: { post_salary: 10000, fund: 1000 } });
  const febPeriod = svc.getTaxPeriod('2026-02');
  assert.ok(febPeriod, '计税期 2026-02 应存在');
  assert.equal(febPeriod.wage_period, '2026-01');
  assert.equal(V(febPeriod.wage_income), 10000);
  assert.equal(V(febPeriod.special_deduction), 1000);
  // 累计：10000 - 5000 - 1000 - 3000(专项附加) = 1000 → 3%
  assert.equal(V(febPeriod.taxable), 1000);
  assert.equal(V(febPeriod.paid_tax), round2(1000 * 0.03));

  // 1 月自身的个税来自计税期 2026-01（跨年写死，工资月为 2025-12）
  const jan = svc.getMonth('2026-01');
  assert.equal(jan.taxPeriod, '2026-01');
  assert.equal(V(jan.tax), 29.36);
});

test('个税：跨年衔接 2026-01 计税期写死为 29.36', () => {
  const svc = fresh();
  svc.recalcAll();
  const seeded = svc.getTaxPeriod('2026-01');
  assert.ok(seeded, '写死期应存在');
  assert.equal(Number(seeded.is_seeded), 1);
  assert.equal(V(seeded.total_tax), 29.36);
  // 写死期不污染 2026 年度累计
  const p2 = svc.getTaxPeriod('2026-02');
  assert.equal(V(p2.cum_income), 0);
});

test('个税：2026-12 工资月的税归入 2027-01 正常计算（不写死）', () => {
  const svc = fresh();
  for (let m = 1; m <= 12; m++) {
    svc.saveMonth(`2026-${String(m).padStart(2, '0')}`, { regular: { post_salary: 30000 } });
  }
  const p = svc.getTaxPeriod('2027-01');
  assert.ok(p, '计税期 2027-01 应存在');
  assert.equal(p.wage_period, '2026-12');
  assert.equal(Number(p.is_seeded), 0, '12 月的税不写死');

  // 累计口径：360000 - 60000(减除) - 36000(专项附加) = 264000 → 20% - 16920 = 35880
  assert.equal(V(p.cum_income), 360000);
  assert.equal(V(p.taxable), 264000);
  assert.equal(V(p.wage_tax), round2(264000 * 0.2 - 16920));
  // 本期应缴 = 累计税额 - 截至 11 月已缴
  const p11 = svc.getTaxPeriod('2026-12'); // 工资月 2026-11
  assert.equal(V(p11.taxable), 242000);
  assert.equal(V(p.paid_tax), round2(V(p.wage_tax) - V(p11.wage_tax)));
});

test('个税：累计预扣跨月递减（先多后补）', () => {
  const svc = fresh();
  for (let m = 1; m <= 3; m++) {
    svc.saveMonth(`2026-${String(m).padStart(2, '0')}`, { regular: { post_salary: 30000 } });
  }
  const p2 = svc.getTaxPeriod('2026-02');
  const p3 = svc.getTaxPeriod('2026-03');
  const p4 = svc.getTaxPeriod('2026-04');
  // 2 月: 30000-5000-3000 = 22000 → 3% = 660
  assert.equal(V(p2.paid_tax), 660);
  // 3 月: 累计 60000-10000-6000 = 44000 → 10%-2520 = 1880，减去已缴 660 = 1220
  assert.equal(V(p3.paid_tax), round2(44000 * 0.1 - 2520 - 660));
  // 4 月: 累计 90000-15000-9000 = 66000 → 10%-2520 = 4080，减已缴 1880 = 2200
  assert.equal(V(p4.paid_tax), round2(66000 * 0.1 - 2520 - 1880));
});

test('一次性奖金：每年只能确认一笔', () => {
  const svc = fresh();
  svc.addBank({ date: '2026-02-12', type: '目标', amount: 20400, note: '目标第一笔' });
  const banks = svc.listBank({ type: '目标' });
  svc.selectBonus(2026, { bankIncomeId: banks[0].id });
  assert.throws(() => svc.selectBonus(2026, { amount: 1000 }), /每年只能确认一笔/);
});

test('银行卡：目标未确认为奖金时计入当月工资', () => {
  const svc = fresh();
  svc.saveMonth('2026-03', { regular: { post_salary: 10000 } });
  svc.addBank({ date: '2026-03-30', type: '目标', amount: 6000, note: '目标第二笔' });
  const p = svc.getTaxPeriod('2026-04'); // 3 月的计税期
  assert.equal(V(p.wage_income), 10000);
  assert.equal(V(p.wage_supplement), 6000);
  assert.equal(V(p.cum_income), 16000);
});
