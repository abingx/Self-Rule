/**
 * 业务配置常量
 * 所有"暂定/待补充"的规则都集中在这里，便于后续调整。
 */

/** 个税：年度累计归集口径（需求 3 确认：按工资月归年） */
export const TAX_YEAR_GROUPING = 'wage_month'; // 'wage_month' | 'tax_month'

/** 计税期 = 工资月 + 1（次月计算上月） */
export const TAX_PERIOD_OFFSET_MONTHS = 1;

/** 每月减除费用 */
export const BASE_DEDUCTION_PER_MONTH = 5000;

/** 每月专项附加扣除定额：按【工资月】的年份取，未配置的年份用 DEFAULT */
export const ADDITIONAL_DEDUCTION_BY_YEAR = {
  2023: 4000,
  2024: 4000,
  2025: 3000,
  2026: 3000,
};
export const ADDITIONAL_DEDUCTION_DEFAULT = 3000;

/**
 * 跨年衔接：直接写死"计算后的个税"（需求 3 第 13 条）
 * key = 计税期(YYYY-MM)，value = 该期应缴个税合计
 * 计税期 2026-01 的工资月是 2025-12，属上一年度，先写死结果，不参与真实跨年计算。
 * 后续完善时把 source 改为 carried 并接入上一年度真实重算即可。
 */
export const TAX_SEED_BY_TAX_PERIOD = {
  '2026-01': { amount: 29.36, note: '跨年衔接：工资月 2025-12，暂写死计算结果' },
};

/** 一次性奖金税率表（按月换算，不并入综合所得） */
export const BONUS_TAX_BRACKETS = [
  { limit: 36000, rate: 0.03, quick: 0 },
  { limit: 144000, rate: 0.1, quick: 210 },
  { limit: 300000, rate: 0.2, quick: 1410 },
  { limit: 420000, rate: 0.25, quick: 2660 },
  { limit: 660000, rate: 0.3, quick: 4410 },
  { limit: 960000, rate: 0.35, quick: 7160 },
  { limit: Infinity, rate: 0.45, quick: 15160 },
];

/** 工资薪金累计预扣预缴税率表 */
export const WAGE_TAX_BRACKETS = [
  { limit: 36000, rate: 0.03, quick: 0 },
  { limit: 144000, rate: 0.1, quick: 2520 },
  { limit: 300000, rate: 0.2, quick: 16920 },
  { limit: 420000, rate: 0.25, quick: 31920 },
  { limit: 660000, rate: 0.3, quick: 52920 },
  { limit: 960000, rate: 0.35, quick: 85920 },
  { limit: Infinity, rate: 0.45, quick: 181920 },
];

// ---------------- 带入规则（需求 2 确认） ----------------

/** 带入触发时机：保存草稿（方案 A） */
export const CARRY_TRIGGER = 'on_save_draft';

/** 下月已有"手工"值时是否覆盖。需求 2 第 7 条按"不覆盖"实现，如需改为覆盖改此常量。 */
export const CARRY_OVERWRITE_MANUAL = false;

/** 带入是否级联到更后月份（需求 2 第 8 条：需要级联） */
export const CARRY_CASCADE = true;

/** 已确认(confirmed)月份是否允许修改（第 11 条：允许，且改动只在当前行生效，不向外传播） */
export const CONFIRMED_EDITABLE = true;
export const CONFIRMED_MONTH_PROPAGATES = false;

/** 12 月修改后是否带入次年 1 月（第 9 条：是） */
export const CARRY_ACROSS_YEAR = true;

/** 带入生成的下月记录落在未到达月份时：只生成不显示（第 10 条） */
export const CREATE_FUTURE_MONTHS = true;

/**
 * 保存某月时，是否把带入一路延伸到"当前月"。
 * true  = 从保存行逐月级联，直到当前月为止（例如当前 2026-10，录入 2026-01 → 一路带入到 10 月）。
 * false = 仅带入到下一月（旧行为）。
 * 注意：无论 true/false，都会至少生成"下一月"记录（未来月只生成不显示）。
 */
export const CARRY_THROUGH_TO_TODAY = true;

/** 补计（目标计入工资）默认归入"收款当月"（第 16 条） */
export const SUPPLEMENT_PERIOD_RULE = 'receipt_month';

/** 工资项目字典：6 个应发项 + 4 个代扣项（第 1 条：暂定不修改） */
export const WAGE_ITEMS = [
  { code: 'post_salary', name: '职务', category: 'earning', side: 'regular', carry: true, sort: 10 },
  { code: 'grade_salary', name: '级别', category: 'earning', side: 'regular', carry: true, sort: 20 },
  { code: 'reserve_allowance', name: '保留补贴', category: 'earning', side: 'regular', carry: true, sort: 30 },
  { code: 'living_allowance', name: '生活性补贴', category: 'earning', side: 'regular', carry: true, sort: 40 },
  { code: 'work_allowance', name: '工作性津贴', category: 'earning', side: 'regular', carry: true, sort: 50 },
  { code: 'base_perf', name: '基础绩效', category: 'earning', side: 'regular', carry: true, sort: 60 },
  { code: 'fund', name: '公积金', category: 'deduction', side: 'regular', carry: true, sort: 110 },
  { code: 'medical', name: '医保', category: 'deduction', side: 'regular', carry: true, sort: 120 },
  { code: 'pension', name: '养老', category: 'deduction', side: 'regular', carry: true, sort: 130 },
  { code: 'annuity', name: '年金', category: 'deduction', side: 'regular', carry: true, sort: 140 },
];

/** 银行卡收入类型 */
export const BANK_TYPES = ['工资', '车贴', '通讯', '工会', '目标', '应休未休', '平时考核', '门诊'];

export function additionalDeductionFor(wageYear) {
  return ADDITIONAL_DEDUCTION_BY_YEAR[wageYear] ?? ADDITIONAL_DEDUCTION_DEFAULT;
}
