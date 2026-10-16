/**
 * 个税计算引擎（支持手动改写）
 *
 * 口径（需求 3 已确认）：
 *  - 计税期 = 工资月 + 1（次月计算上月）
 *  - 年度累计按【工资月】归年（口径 A，与现有电子版一致）
 *  - 2026-01 计税期跨年衔接：只写死"计算后的个税"
 *  - 2026-12 工资月的个税不写死，归入 2027-01 计税期正常计算
 *
 * 改写语义：每个字段先算 auto 值，再叠加人工改写；改写按依赖顺序向下游传播。
 */
import {
  BASE_DEDUCTION_PER_MONTH,
  BONUS_TAX_BRACKETS,
  WAGE_TAX_BRACKETS,
  TAX_SEED_BY_TAX_PERIOD,
  additionalDeductionFor,
} from './config.js';
import { addMonths, yearOf, monthOf, round2 } from './period.js';
import { field, val, pack } from './override.js';

function bracketOf(brackets, taxable) {
  for (const b of brackets) if (taxable <= b.limit) return b;
  return brackets[brackets.length - 1];
}

export function calcBonusTax(amount) {
  const a = Number(amount) || 0;
  if (a <= 0) return 0;
  const b = bracketOf(BONUS_TAX_BRACKETS, a);
  return round2(a * b.rate - b.quick);
}

export function calcCumulativeTax(taxable) {
  const t = Number(taxable) || 0;
  if (t <= 0) return 0;
  const b = bracketOf(WAGE_TAX_BRACKETS, t);
  return round2(t * b.rate - b.quick);
}

/**
 * 计算某一【计税期】。
 * @param {string} taxPeriod 计算月 YYYY-MM
 * @param {object} ctx 原始输入 + 上期累计（均为最终值）
 * @param {object} ovMap 该计税期的改写表
 */
export function calcTaxPeriod(taxPeriod, ctx = {}, ovMap = {}) {
  const wagePeriod = addMonths(taxPeriod, -1);
  const wageYear = yearOf(wagePeriod);
  const nth = monthOf(wagePeriod);          // 期数按【工资月】
  const seed = TAX_SEED_BY_TAX_PERIOD[taxPeriod];
  const prev = ctx.cumPrev || {};

  // ---------- 输入字段 ----------
  const fWageIncome = field(ovMap, 'wage_income', round2(ctx.wageIncome || 0));
  const fSupplement = field(ovMap, 'wage_supplement', round2(ctx.wageSupplement || 0));
  const fSpecial = field(ovMap, 'special_deduction', round2(ctx.specialDeduction || 0));
  const fOther = field(ovMap, 'other_deduction', round2(ctx.otherDeduction || 0));
  const fBonus = field(ovMap, 'bonus_amount', round2(ctx.bonusAmount || 0));

  // ---------- 累计字段（基于上期最终值 + 本期最终值） ----------
  const autoCumIncome = round2(val(prev.cum_income) + val(fWageIncome) + val(fSupplement));
  const autoCumBase = round2(val(prev.cum_base) + BASE_DEDUCTION_PER_MONTH);
  const autoCumSpecial = round2(val(prev.cum_special) + val(fSpecial));
  const autoCumOther = round2(val(prev.cum_other) + val(fOther));
  const autoAdditional = round2(additionalDeductionFor(wageYear) * nth);

  const fCumIncome = field(ovMap, 'cum_income', autoCumIncome);
  const fCumBase = field(ovMap, 'cum_base', autoCumBase);
  const fCumSpecial = field(ovMap, 'cum_special', autoCumSpecial);
  const fCumOther = field(ovMap, 'cum_other', autoCumOther);
  const fAdditional = field(ovMap, 'additional', autoAdditional);

  // ---------- 派生字段 ----------
  const rawTaxable = val(fCumIncome) - val(fCumBase) - val(fCumSpecial) - val(fCumOther) - val(fAdditional);
  const fTaxable = field(ovMap, 'taxable', round2(Math.max(0, rawTaxable)));

  const fWageTax = field(ovMap, 'wage_tax', calcCumulativeTax(val(fTaxable)));
  const fBonusTax = field(ovMap, 'bonus_tax', calcBonusTax(val(fBonus)));

  const prevPaid = val(prev.cum_paid);
  const autoPaid = round2(Math.max(0, val(fWageTax) - prevPaid));
  const fPaid = field(ovMap, 'paid_tax', autoPaid);

  const fTotal = field(ovMap, 'total_tax', round2(val(fBonusTax) + val(fPaid)));

  return {
    taxPeriod,
    wagePeriod,
    isSeeded: !!seed,
    note: seed ? seed.note : null,

    wage_income: pack(fWageIncome),
    wage_supplement: pack(fSupplement),
    special_deduction: pack(fSpecial),
    other_deduction: pack(fOther),
    cum_income: pack(fCumIncome),
    cum_base: pack(fCumBase),
    cum_special: pack(fCumSpecial),
    cum_other: pack(fCumOther),
    additional: pack(fAdditional),
    taxable: pack(fTaxable),
    bonus_amount: pack(fBonus),
    bonus_tax: pack(fBonusTax),
    wage_tax: pack(fWageTax),
    paid_tax: pack(fPaid),
    total_tax: pack(fTotal),
  };
}

/**
 * 跨年写死期：所有字段的 auto 值。
 * 只写死结果本身（个税合计），其余输入保持真实采集值。
 */
export function seedAuto(taxPeriod) {
  const seed = TAX_SEED_BY_TAX_PERIOD[taxPeriod];
  return seed ? round2(seed.amount) : null;
}

/**
 * 从结果中取最终值，供下游累计使用。
 * 注意：cum_paid 必须"累加"，即上期已缴 + 本期应缴。
 */
export function finalCum(result, prevCum) {
  const prevPaid = prevCum ? val(prevCum.cum_paid) : 0;
  return {
    cum_income: result.cum_income,
    cum_base: result.cum_base,
    cum_special: result.cum_special,
    cum_other: result.cum_other,
    cum_paid: round2(prevPaid + val(result.paid_tax)),
  };
}
