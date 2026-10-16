/**
 * 前端渲染验证：在 DOM 桩中真实执行 public/app.js，
 * 校验渲染结果与 API 字段严格对齐（捕捉字段名不一致等问题）。
 *
 * 说明：本环境无法运行浏览器（Chromium sandbox 被禁），故不做像素级视觉验证；
 * 该测试覆盖"页面能否正确渲染出数据"这一核心风险。
 */
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = 8899;
const BASE = `http://127.0.0.1:${PORT}`;
const DB = path.join(ROOT, 'data', 'test-frontend.db');

let child;
const stores = new Map();

function makeEl(sel) {
  const el = {
    _sel: sel, _html: '', textContent: '', value: '', dataset: {},
    style: {}, onclick: null, onchange: null, onkeydown: null, onsubmit: null,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; stores.set(this._sel, v); },
    querySelector: () => null,
  };
  return el;
}

function installDom() {
  stores.clear();
  globalThis.document = {
    title: '',
    querySelector(sel) {
      if (!stores.has(sel)) stores.set(sel, '');
      return makeEl(sel);
    },
    // 渲染后绑定事件用的选择器，返回空集合即可（不影响渲染验证）
    querySelectorAll: () => [],
    createElement: () => makeEl('created'),
  };
  globalThis.FormData = class { constructor() {} get() { return null; } };

  const realFetch = globalThis.fetch;
  globalThis.fetch = (url, opts) => realFetch(url.startsWith('http') ? url : BASE + url, opts);
}

function html(sel) { return stores.get(sel) || ''; }

before(async () => {
  fs.rmSync(DB, { force: true });
  // 用占位进程方式启动真实服务，确保端口就绪
  child = spawn(process.execPath, [path.join(ROOT, 'src', 'server.js')], {
    cwd: ROOT,
    env: { ...process.env, PORT: String(PORT), DB_FILE: DB },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let log = '';
  child.stdout.on('data', (d) => { log += d; });
  child.stderr.on('data', (d) => { log += d; });

  let ok = false;
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`${BASE}/api/meta`); if (r.ok) { ok = true; break; } } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  assert.ok(ok, `服务未就绪，日志: ${log}`);
  installDom();
});

after(async () => {
  if (child) child.kill('SIGKILL');
  fs.rmSync(DB, { force: true });
  fs.rmSync(DB + '-journal', { force: true });
});

test('前端：app.js 可加载并渲染工资明细表', async () => {
  // 造两条数据：1 月常规+补发，2 月由带入产生
  await fetch('/api/wage/2026-01', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      regular: { post_salary: 1170, grade_salary: 1907, fund: 2050, pension: 474.48 },
      adjustments: [{ code: 'post_salary', type: 'makeup', amount: 500 }],
    }),
  });

  const mod = await import(path.join(ROOT, 'public', 'app.js') + '?t=' + Date.now());
  assert.ok(mod, 'app.js 应可加载');
  globalThis.refreshRef = mod.refresh;
  await new Promise((r) => setTimeout(r, 900));

  const wageHtml = html('#wages-table');
  assert.ok(wageHtml.includes('2026-01'), '表格应含 2026-01 行');
  assert.ok(wageHtml.includes('2026-12'), '表格应含 2026-12 行');
  // 月份数 = 12 行
  assert.equal((wageHtml.match(/data-period="2026-\d{2}"/g) || []).length >= 12, true);

  // 表头应包含全部工资项名称
  for (const name of ['职务', '级别', '保留补贴', '生活性补贴', '工作性津贴', '基础绩效', '公积金', '医保', '养老', '年金']) {
    assert.ok(wageHtml.includes(name), `表头应含 ${name}`);
  }
  assert.ok(wageHtml.includes('应发合计'), '应含应发合计');
  assert.ok(wageHtml.includes('预计实发'), '应含预计实发');
  assert.ok(wageHtml.includes('补发'), '应含补发分组');
  assert.ok(wageHtml.includes('补扣'), '应含补扣分组');

  // 应发合计 6785（1170+1907+500 为应发项... 实际 earning: 1170+1907+500 = 3577）
  // 校验页面出现了实际计算值而非空白
  assert.ok(/3577\.00/.test(wageHtml), '应渲染出应发合计 3577.00');
  assert.ok(wageHtml.includes('result-cell'), '结果单元格应带 result-cell 标记');
  assert.ok(wageHtml.includes('td class="auto'), '未改写的结果应为 auto 样式');

  // 未到达月份应带 future 类
  assert.ok(wageHtml.includes('future'), '未到达月份应有 future 标记');

  // 个税表
  const taxHtml = html('#tax-table');
  assert.ok(taxHtml.includes('工资月'), '个税表应有表头');
  assert.ok(taxHtml.includes('计算月'), '个税表应有计算月列');
  assert.ok(taxHtml.includes('跨年写死') || taxHtml.includes('29.36'), '应显示跨年写死提示或值');

  // 核对表
  const recHtml = html('#reconcile-table');
  assert.ok(recHtml.includes('预计实发'), '核对表应有预计实发列');

  // 一次性奖金区
  const bonusHtml = html('#bonus-box');
  assert.ok(bonusHtml.includes('一次性奖金'), '应有一次性奖金确认区');

  // 改写后：应渲染出 ov 样式与还原按钮，从而与自动计算明显区分
  await fetch('/api/override/wage/2026-01', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ overrides: { gross: 12345 } }),
  });
  await refreshRef();
  const ovHtml = html('#wages-table');
  assert.ok(ovHtml.includes('class="total ov result-cell"') || ovHtml.includes(' ov '), '改写后应带 ov 样式');
  assert.ok(ovHtml.includes('button class="revert"'), '改写后应有还原按钮');
  assert.ok(/12345\.00/.test(ovHtml), '应显示改写值');
  assert.ok(ovHtml.includes('tag changed'), '月份标签应提示有改写');

  // 还原，保证后续测试独立
  await fetch('/api/override/wage/2026-01/reset', { method: 'POST' });
  await refreshRef();
});

test('前端：导入历史可用字段与 API 一致（防止字段名漂移）', async () => {
  const wage = await (await fetch('/api/wage/2026-01')).json();
  for (const k of ['period', 'regular', 'adjustments', 'gross', 'special', 'tax', 'deduct', 'net', 'taxPeriod', 'status']) {
    assert.ok(k in wage, `工资月接口应含字段 ${k}`);
  }
  const V = (x) => (x && typeof x === 'object' && 'value' in x ? x.value : x);
  assert.equal(V(wage.gross), 3577, '最终值应为自动计算');
  assert.equal(wage.gross.auto, 3577, 'auto 值应稳定为自动计算结果');
  assert.equal(wage.adjustments.length, 1);
  // 结果字段应带 auto/value/overridden，供前端区分计算与改写
  for (const f of ['gross', 'special', 'tax', 'deduct', 'net']) {
    assert.ok('auto' in wage[f] && 'value' in wage[f] && 'overridden' in wage[f], `${f} 应含 auto/value/overridden`);
  }

  const tax = await (await fetch('/api/tax/2026')).json();
  const p = tax.periods.find((x) => x.tax_period === '2026-02');
  for (const k of ['tax_period', 'wage_period', 'wage_income', 'wage_supplement', 'special_deduction',
    'cum_income', 'cum_base', 'cum_special', 'additional', 'taxable', 'bonus_amount',
    'bonus_tax', 'wage_tax', 'paid_tax', 'total_tax', 'is_seeded']) {
    assert.ok(k in p, `计税期接口应含字段 ${k}`);
  }
  assert.equal(p.wage_period, '2026-01');
  assert.equal(V(p.wage_income), 3577);
  for (const f of ['wage_income', 'cum_income', 'taxable', 'paid_tax', 'total_tax']) {
    assert.ok('auto' in p[f] && 'value' in p[f] && 'overridden' in p[f], `${f} 应含 auto/value/overridden`);
  }

  const rec = await (await fetch('/api/reconcile/2026')).json();
  assert.ok(rec.rows.length === 12);
  assert.ok('expectedNet' in rec.rows[0] && 'byType' in rec.rows[0] && 'diff' in rec.rows[0]);
});
