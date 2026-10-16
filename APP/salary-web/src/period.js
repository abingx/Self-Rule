/** 期间（YYYY-MM）工具 */

export function parsePeriod(p) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(p || ''));
  if (!m) throw new Error(`非法期间: ${p}`);
  return { year: Number(m[1]), month: Number(m[2]) };
}

export function toPeriod(year, month) {
  let y = year, m = month;
  while (m > 12) { m -= 12; y += 1; }
  while (m < 1) { m += 12; y -= 1; }
  return `${y}-${String(m).padStart(2, '0')}`;
}

export function addMonths(p, n) {
  const { year, month } = parsePeriod(p);
  return toPeriod(year, month + n);
}

/** 工资月 -> 计算月（次月） */
export function taxPeriodOf(wagePeriod) {
  return addMonths(wagePeriod, 1);
}

export function yearOf(p) { return parsePeriod(p).year; }
export function monthOf(p) { return parsePeriod(p).month; }

/** 该期间的年份块首月（按工资月归年时，年度块从 Y-01 起） */
export function blockStart(period) {
  return `${yearOf(period)}-01`;
}

export function periodRange(from, to) {
  const out = [];
  let cur = from;
  while (cur <= to) { out.push(cur); cur = addMonths(cur, 1); }
  return out;
}

export function todayPeriod(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

/** 统一四舍五入到 2 位，避免浮点尾差 */
export function round2(n) {
  if (!Number.isFinite(n)) return 0;
  return Math.round((n + Number.EPSILON) * 100) / 100;
}
