/** 前端应用：四个视图 */
const state = { meta: null, year: null, wages: [], tax: [], bank: [], bonus: [], reconcile: [] };

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const n = (v) => (v === null || v === undefined || v === '' ? '' : Number(v));
const fmt = (v) => (v === null || v === undefined || v === '' ? '' : Number(v).toFixed(2));
const monthLabel = (p) => `${Number(p.slice(5, 7))}月`;
const today = () => new Date().toISOString().slice(0, 10);

let toastTimer;
function toast(msg, isErr) {
  const t = $('#toast');
  t.textContent = msg;
  t.style.background = isErr ? '#b91c1c' : '#111827';
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
}

/**
 * 保存前的带入选择弹窗。
 * 返回 'now'（更新至最新行）/ 'only'（只修改当前）/ 'cancel'。
 */
function askCarryModal(period) {
  return new Promise((resolve) => {
    const mask = $('#modal');
    $('#modal-title').textContent = `保存 ${period}`;
    $('#modal-text').textContent =
      `是否把本次修改按「常规项带入」逐月更新到最新行（${state.meta.today.slice(0, 7)}）？`
      + '选择「只修改当前」则仅保存本行，不影响后续月份。';
    mask.hidden = false;

    const done = (choice) => {
      mask.hidden = true;
      $('#modal-now').onclick = $('#modal-only').onclick = $('#modal-cancel').onclick = null;
      resolve(choice);
    };
    $('#modal-now').onclick = () => done('now');
    $('#modal-only').onclick = () => done('only');
    $('#modal-cancel').onclick = () => done('cancel');
  });
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `请求失败 ${res.status}`);
  return data;
}

async function loadAll() {
  state.meta = await api('GET', '/api/meta');
  const years = [];
  const cur = Number(state.meta.today.slice(0, 4));
  for (let y = cur + 1; y >= cur - 3; y--) years.push(y);
  const sel = $('#year');
  sel.innerHTML = years.map((y) => `<option value="${y}">${y} 年</option>`).join('');
  state.year = cur;
  sel.value = String(cur);
  sel.onchange = () => { state.year = Number(sel.value); refresh(); };

  $('#bank-type').innerHTML = state.meta.bankTypes.map((t) => `<option>${t}</option>`).join('');
  $('#meta-hint').textContent = `今天 ${state.meta.today}`;
  await refresh();
}

async function refresh() {
  const y = state.year;
  const [w, t, b, bo, r] = await Promise.all([
    api('GET', `/api/wages/${y}`),
    api('GET', `/api/tax/${y}`),
    api('GET', `/api/bank?from=${y}-01-01&to=${y}-12-31`),
    api('GET', '/api/bonus'),
    api('GET', `/api/reconcile/${y}`),
  ]);
  state.wages = w.months;
  state.tax = t.periods;
  state.bank = b;
  state.bonus = bo;
  state.reconcile = r.rows;
  renderWages();
  renderTax();
  renderBank();
  renderReconcile();
}

// ---------------- 工资明细 ----------------

function renderWages() {
  const items = state.meta.items;
  const earn = items.filter((i) => i.category === 'earning');
  const ded = items.filter((i) => i.category === 'deduction');
  const todayP = state.meta.today.slice(0, 7);

  let h = '<div class="table-wrap"><table><thead><tr><th class="label">月份</th>';
  for (const i of earn) h += `<th>${i.name}<br><span class="tag">本月</span></th>`;
  for (const i of earn) h += `<th>${i.name}<br><span class="tag warn">补发</span></th>`;
  h += '<th>应发合计</th>';
  for (const i of ded) h += `<th>${i.name}</th>`;
  for (const i of ded) h += `<th>${i.name}<br><span class="tag warn">补扣</span></th>`;
  h += '<th>专项合计</th><th>个税</th><th>代扣合计</th><th>预计实发</th><th>状态</th></tr></thead><tbody>';

  for (const m of state.wages) {
    const isFuture = m.period > todayP;
    const cls = [isFuture ? 'future' : '', m.period === todayP ? 'current' : ''].join(' ');
    h += `<tr class="${cls}" data-period="${m.period}">`;
    h += `<td class="label">${m.period.slice(2)}${m.anyOverridden ? ' <span class="tag changed" title="本月有手动改写">改写</span>' : ''}</td>`;
    for (const i of earn) h += cellInput(m.period, i.code, m.regular[i.code], 'regular');
    for (const i of earn) {
      const a = m.adjustments.find((x) => x.code === i.code && x.type === 'makeup');
      h += cellInput(m.period, i.code, a ? { amount: a.amount, source: 'manual' } : null, 'makeup');
    }
    h += resultCell(m.period, 'gross', m.gross, 'total');
    for (const i of ded) h += cellInput(m.period, i.code, m.regular[i.code], 'regular');
    for (const i of ded) {
      const a = m.adjustments.find((x) => x.code === i.code && x.type === 'clawback');
      h += cellInput(m.period, i.code, a ? { amount: a.amount, source: 'manual' } : null, 'clawback');
    }
    h += resultCell(m.period, 'special', m.special, 'total');
    h += resultCell(m.period, 'tax', m.tax, '', { title: `计税期 ${m.taxPeriod}` });
    h += resultCell(m.period, 'deduct', m.deduct, 'total');
    h += resultCell(m.period, 'net', m.net, 'total');
    h += `<td>${m.status === 'confirmed' ? '<span class="tag ok">已确认</span>' : '<span class="tag">草稿</span>'}</td>`;
    h += '</tr>';
  }
  h += '</tbody></table></div>';
  $('#wages-table').innerHTML = h;

  bindInputs('#wages-table');
  bindResultCells('#wages-table', 'wage');
}

/** 计算结果单元格：可编辑，且区分"自动计算"与"手动改写" */
function resultCell(period, fieldName, x, extraClass, opts = {}) {
  const o = x || { auto: 0, value: 0, overridden: false };
  const cls = [extraClass, o.overridden ? 'ov' : 'auto', 'result-cell'].filter(Boolean).join(' ');
  const title = o.overridden
    ? `手动改写（自动值 ${fmt(o.auto)}）— 点击右下角 ↺ 可还原`
    : (opts.title || `自动计算 ${fmt(o.auto)}`);
  return `<td class="${cls}" title="${title}">`
    + `<input data-period="${period}" data-field="${fieldName}" data-kind="override" value="${fmt(o.value)}">`
    + (o.overridden ? `<button class="revert" data-period="${period}" data-field="${fieldName}" title="还原为自动计算 ${fmt(o.auto)}">↺</button>` : '')
    + '</td>';
}

function bindInputs(root) {
  $$(`${root} input[data-kind=regular]`).forEach((el) => {
    el.onchange = () => saveCell(el, 'regular');
    el.onkeydown = (e) => { if (e.key === 'Enter') el.blur(); };
  });
  $$(`${root} input[data-kind=makeup], ${root} input[data-kind=clawback]`).forEach((el) => {
    el.onchange = () => saveCell(el, el.dataset.kind);
    el.onkeydown = (e) => { if (e.key === 'Enter') el.blur(); };
  });
}

/** 结果字段改写：输入值 == auto 时视为未改写（自动清除） */
function bindResultCells(root, scope) {
  $$(`${root} input[data-kind=override]`).forEach((el) => {
    el.onchange = () => saveResultOverride(el, scope);
    el.onkeydown = (e) => { if (e.key === 'Enter') el.blur(); };
  });
  $$(`${root} button.revert`).forEach((btn) => {
    btn.onclick = async () => {
      const url = scope === 'wage'
        ? `/api/override/wage/${btn.dataset.period}`
        : `/api/override/tax/${btn.dataset.period}`;
      try {
        await api('PUT', url, { overrides: { [btn.dataset.field]: null } });
        await refresh();
        toast(`${btn.dataset.field} 已还原为自动计算`);
      } catch (e) { toast(e.message, true); }
    };
  });
}

async function saveResultOverride(el, scope) {
  const period = el.dataset.period;
  const fieldName = el.dataset.field;
  const raw = el.value.trim();
  const url = scope === 'wage'
    ? `/api/override/wage/${period}`
    : `/api/override/tax/${period}`;
  try {
    if (raw === '') {
      await api('PUT', url, { overrides: { [fieldName]: null } });
    } else {
      await api('PUT', url, { overrides: { [fieldName]: Number(raw) } });
    }
    await refresh();
    toast(raw === '' ? '已还原为自动计算' : '已保存手动改写');
  } catch (e) {
    toast(e.message, true);
    await refresh();
  }
}

function cellInput(period, code, v, kind) {
  const amount = v ? fmt(v.amount) : '';
  const src = v ? v.source : '';
  const carried = src === 'carried' && kind === 'regular';
  const title = carried ? `带入自 ${v.from}` : '';
  return `<td class="${kind === 'regular' ? (carried ? 'carried' : 'manual') : ''}">`
    + `<input data-period="${period}" data-code="${code}" data-kind="${kind}" value="${amount}" title="${title}" placeholder="-">`
    + '</td>';
}

/** 单元格保存：按当前行汇总出完整 payload 后提交（触发带入） */
async function saveCell(el, kind) {
  const period = el.dataset.period;
  const m = state.wages.find((x) => x.period === period);
  const items = state.meta.items;
  const val = el.value === '' ? null : Number(el.value);

  const regular = {};
  const adjustments = [];
  for (const it of items) {
    if (it.category === 'earning') {
      regular[it.code] = readCell(period, it.code, 'regular', m);
      const mk = readCell(period, it.code, 'makeup', m);
      if (mk !== null) adjustments.push({ code: it.code, type: 'makeup', amount: mk });
    } else {
      regular[it.code] = readCell(period, it.code, 'regular', m);
      const cb = readCell(period, it.code, 'clawback', m);
      if (cb !== null) adjustments.push({ code: it.code, type: 'clawback', amount: cb });
    }
  }
  // 当前编辑的单元格以输入值为准
  if (kind === 'regular') regular[el.dataset.code] = val;
  else {
    const code = el.dataset.code;
    const list = adjustments.filter((a) => !(a.code === code && a.type === kind));
    if (val !== null) list.push({ code, type: kind, amount: val });
    adjustments.length = 0;
    adjustments.push(...list);
  }

  // 保存前询问：是否把修改带入后续月份直到最新行
  const todayP = state.meta.today.slice(0, 7);
  let propagate = false;
  if (period < todayP) {
    const choice = await askCarryModal(period);
    if (choice === 'cancel') { await refresh(); return; }
    propagate = choice === 'now';
  }

  try {
    const r = await api('PUT', `/api/wage/${period}`, { regular, adjustments, propagate });
    const carried = r.carryLogs.filter((l) => l.action === 'carried');
    const skipped = r.carryLogs.filter((l) => l.action === 'skipped_manual');
    let msg = propagate ? `${period} 已保存，并带入后续月份` : `${period} 已保存（仅当前行）`;
    if (carried.length) msg += `，${carried.length} 项带入`;
    if (skipped.length) msg += `，后续月份已手工填写已保留`;
    toast(msg);
    await refresh();
  } catch (e) {
    toast(e.message, true);
  }
}

function readCell(period, code, kind, m) {
  const el = document.querySelector(`input[data-period="${period}"][data-code="${code}"][data-kind="${kind}"]`);
  if (el) return el.value === '' ? null : Number(el.value);
  if (kind === 'regular') {
    const v = m.regular[code];
    return v ? v.amount : null;
  }
  const a = m.adjustments.find((x) => x.code === code && x.type === kind);
  return a ? a.amount : null;
}

$('#save-all').onclick = async () => {
  const todayP = state.meta.today.slice(0, 7);
  const m = state.wages.find((x) => x.period === todayP) || state.wages[state.wages.length - 1];
  const el = document.querySelector(`input[data-period="${m.period}"]`);
  if (el) await saveCell(el, el.dataset.kind);
};

// ---------------- 个税 ----------------

function renderTax() {
  const rows = state.tax;
  const F = [
    ['wage_income', '工资收入'], ['wage_supplement', '补计'], ['special_deduction', '专项扣除'],
    ['other_deduction', '其他扣除'], ['cum_income', '累计收入'], ['cum_base', '累计减除'],
    ['cum_special', '专项累计'], ['cum_other', '其他扣除累计'], ['additional', '专项附加'],
    ['taxable', '应纳税额'], ['bonus_amount', '一次性奖金'], ['bonus_tax', '奖金税'],
    ['wage_tax', '累计税额'], ['paid_tax', '本期应缴'], ['total_tax', '合计'],
  ];
  const ovCount = rows.filter((r) => r.anyOverridden).length;

  let h = '<div class="toolbar"><span class="hint">所有结果列均可直接修改；'
    + '<span class="legend-box auto">自动</span> 为公式计算，'
    + '<span class="legend-box ov">改写</span> 为人工覆盖，点 ↺ 还原。</span>'
    + (ovCount ? `<span class="tag changed">本年有 ${ovCount} 个计税期被改写</span>` : '')
    + '</div>';
  h += '<div class="table-wrap"><table><thead><tr><th class="label">工资月</th><th>计算月</th>';
  for (const [, label] of F) h += `<th>${label}</th>`;
  h += '<th>说明</th></tr></thead><tbody>';

  for (const r of rows) {
    h += `<tr class="${r.is_seeded ? 'seeded' : ''}">`
      + `<td class="label">${r.wage_period}</td><td>${r.tax_period}</td>`;
    for (const [f] of F) h += taxCell(r.tax_period, f, r[f]);
    h += `<td class="label">${r.is_seeded ? `<span class="tag warn">${r.note || '跨年写死'}</span>` : ''}</td></tr>`;
  }
  h += '</tbody></table></div>';
  $('#tax-table').innerHTML = rows.length ? h : '<p class="hint">该年度暂无计税数据，请先在「工资明细」录入。</p>';

  bindResultCells('#tax-table', 'tax');
}

function taxCell(period, fieldName, x) {
  const o = x || { auto: 0, value: 0, overridden: false };
  return `<td class="${o.overridden ? 'ov' : 'auto'} result-cell" title="${o.overridden ? `手动改写（自动值 ${fmt(o.auto)}）` : `自动计算 ${fmt(o.auto)}`}">`
    + `<input data-period="${period}" data-field="${fieldName}" data-kind="override" value="${fmt(o.value)}">`
    + (o.overridden ? `<button class="revert" data-period="${period}" data-field="${fieldName}" title="还原为 ${fmt(o.auto)}">↺</button>` : '')
    + '</td>';
}

$('#recalc').onclick = async () => {
  await api('POST', '/api/recalc');
  await refresh();
  toast('已重算');
};

// ---------------- 银行卡 ----------------

function renderBank() {
  const rows = [...state.bank].sort((a, b) => (a.date < b.date ? 1 : -1));
  let h = '<div class="table-wrap"><table><thead><tr><th class="label">日期</th><th>类型</th>'
    + '<th>金额</th><th class="label">备注</th><th>归属月</th><th>奖金</th><th>操作</th></tr></thead><tbody>';
  for (const r of rows) {
    h += `<tr><td class="label">${r.date}</td><td>${r.type}</td><td>${fmt(r.amount)}</td>`
      + `<td class="label">${r.note || ''}</td><td>${r.period}</td>`
      + `<td>${r.is_bonus ? '<span class="tag ok">已确认</span>' : ''}</td>`
      + `<td><button data-del="${r.id}">删除</button></td></tr>`;
  }
  h += '</tbody></table></div>';
  $('#bank-table').innerHTML = rows.length ? h : '<p class="hint">该年度暂无流水。</p>';
  $$('#bank-table button[data-del]').forEach((b) => {
    b.onclick = async () => {
      if (!confirm('确认删除这条流水？')) return;
      await api('DELETE', `/api/bank/${b.dataset.del}`);
      await refresh();
      toast('已删除');
    };
  });

  // 一次性奖金确认区
  const y = state.year;
  const sel = state.bonus.find((b) => b.tax_year === y);
  let bh = `<div class="panel"><h3>${y} 年一次性奖金确认</h3>`;
  const targets = rows.filter((r) => r.type === '目标');
  if (sel) {
    bh += `<p>已确认：<b>${fmt(sel.amount)}</b>（计入计税期 ${sel.tax_period}）`
      + `${sel.note ? ' · ' + sel.note : ''}</p>`
      + `<p class="hint">每年只能确认一笔。其余「目标」收入已自动计入当月工资收入。</p>`;
  } else {
    bh += '<p class="hint">每年只能确认一笔一次性奖金；未确认的「目标」收入自动计入当月工资收入。</p>';
    if (targets.length) {
      bh += '<p>可选目标记录：</p><ul>'
        + targets.map((t) => `<li>${t.date} · ${fmt(t.amount)} · ${t.note || ''} `
          + `<button data-bonus="${t.id}" data-amt="${t.amount}">确认为 ${y} 年一次性奖金</button></li>`).join('')
        + '</ul>';
    }
    bh += `<p><button id="bonus-manual">手工输入奖金金额</button></p>`;
  }
  bh += '</div>';
  $('#bonus-box').innerHTML = bh;

  $$('#bonus-box button[data-bonus]').forEach((b) => {
    b.onclick = async () => {
      try {
        await api('POST', '/api/bonus', { taxYear: y, bankIncomeId: Number(b.dataset.bonus) });
        await refresh();
        toast('已确认一次性奖金');
      } catch (e) { toast(e.message, true); }
    };
  });
  const bm = $('#bonus-manual');
  if (bm) bm.onclick = async () => {
    const v = prompt('请输入一次性奖金金额');
    if (!v) return;
    try {
      await api('POST', '/api/bonus', { taxYear: y, amount: Number(v) });
      await refresh();
      toast('已确认一次性奖金');
    } catch (e) { toast(e.message, true); }
  };
}

$('#bank-form').onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api('POST', '/api/bank', {
      date: f.get('date') || today(),
      type: f.get('type'),
      amount: Number(f.get('amount')),
      note: f.get('note') || null,
    });
    e.target.reset();
    await refresh();
    toast('已添加');
  } catch (err) { toast(err.message, true); }
};

// ---------------- 核对 ----------------

function renderReconcile() {
  const rows = state.reconcile;
  const types = [...new Set(rows.flatMap((r) => Object.keys(r.byType)))];
  let h = '<div class="table-wrap"><table><thead><tr><th class="label">月份</th><th>预计实发</th>';
  for (const t of types) h += `<th>${t}</th>`;
  h += '<th>实际合计</th><th>差额</th><th>结果</th></tr></thead><tbody>';
  for (const r of rows) {
    if (!r.expectedNet && !r.actual) continue;
    h += `<tr><td class="label">${r.period}</td>`
      + `<td class="${r.netOverridden ? 'ov' : 'auto'}" title="${r.netOverridden ? `预计实发已改写（自动值 ${fmt(r.expectedNetAuto)}）` : `自动计算 ${fmt(r.expectedNetAuto)}`}">${fmt(r.expectedNet)}${r.netOverridden ? ' <span class="tag changed">改写</span>' : ''}</td>`;
    for (const t of types) h += `<td>${fmt(r.byType[t] || 0)}</td>`;
    const bad = Math.abs(r.diff) > 0.01;
    h += `<td class="total">${fmt(r.actual)}</td><td>${fmt(r.diff)}</td>`
      + `<td>${bad ? '<span class="tag bad">有差异</span>' : '<span class="tag ok">一致</span>'}</td></tr>`;
  }
  h += '</tbody></table></div>';
  $('#reconcile-table').innerHTML = h;
}

// ---------------- 视图切换 ----------------

$$('.tab').forEach((b) => {
  b.onclick = () => {
    $$('.tab').forEach((x) => x.classList.toggle('active', x === b));
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${b.dataset.view}`));
  };
});

loadAll().catch((e) => toast(e.message, true));

// 导出供测试使用（浏览器中无副作用）
export { refresh, saveResultOverride, renderWages, renderTax };
