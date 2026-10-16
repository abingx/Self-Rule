/**
 * HTTP 服务：零第三方依赖（node:http + node:sqlite）
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createService } from './service.js';
import { todayPeriod } from './period.js';
import { BANK_TYPES, WAGE_ITEMS, TAX_SEED_BY_TAX_PERIOD, ADDITIONAL_DEDUCTION_BY_YEAR } from './config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');
const PORT = Number(process.env.PORT || 8788);

const svc = createService(process.env.DB_FILE || 'salary.db');
svc.recalcAll();

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function json(res, code, data) {
  const body = JSON.stringify(data);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 1e6) reject(new Error('body too large')); });
    req.on('end', () => {
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); } catch (e) { reject(new Error('JSON 解析失败')); }
    });
    req.on('error', reject);
  });
}

const routes = [
  ['GET', /^\/api\/meta$/, () => ({
    items: svc.items,
    bankTypes: BANK_TYPES,
    today: todayPeriod(),
    taxSeeds: TAX_SEED_BY_TAX_PERIOD,
    additionalByYear: ADDITIONAL_DEDUCTION_BY_YEAR,
  })],

  // 工资明细：按年
  ['GET', /^\/api\/wages\/(\d{4})$/, (m) => ({
    year: Number(m[1]),
    months: svc.getYearView(Number(m[1])),
    overrideFields: svc.WAGE_OVERRIDE_FIELDS,
  })],
  ['GET', /^\/api\/wage\/(\d{4}-\d{2})$/, (m) => svc.getMonth(m[1])],
  ['PUT', /^\/api\/wage\/(\d{4}-\d{2})$/, async (m, req) => svc.saveMonth(m[1], await readBody(req))],
  ['POST', /^\/api\/wage\/(\d{4}-\d{2})\/confirm$/, async (m, req) => {
    const b = await readBody(req);
    return svc.confirmMonth(m[1], b.confirmed !== false);
  }],

  // 个税
  ['GET', /^\/api\/tax\/(\d{4})$/, (m) => ({
    year: Number(m[1]),
    periods: svc.getTaxYear(Number(m[1])),
    overrideFields: svc.TAX_OVERRIDE_FIELDS,
  })],
  ['POST', /^\/api\/recalc$/, () => { svc.recalcAll(); return { ok: true }; }],

  // 手动改写：所有自动计算结果均可改写/还原
  ['PUT', /^\/api\/override\/wage\/(\d{4}-\d{2})$/, async (m, req) => {
    const b = await readBody(req);
    let month = null;
    for (const [f, v] of Object.entries(b.overrides || {})) {
      month = svc.setWageOverride(m[1], f, v);
    }
    return month || svc.getMonth(m[1]);
  }],
  ['PUT', /^\/api\/override\/tax\/(\d{4}-\d{2})$/, async (m, req) => {
    const b = await readBody(req);
    let tp = null;
    for (const [f, v] of Object.entries(b.overrides || {})) {
      tp = svc.setTaxOverride(m[1], f, v);
    }
    return tp || svc.getTaxPeriod(m[1]);
  }],
  ['POST', /^\/api\/override\/wage\/(\d{4}-\d{2})\/reset$/, (m) => svc.resetOverrides('wage', m[1])],
  ['POST', /^\/api\/override\/tax\/(\d{4}-\d{2})\/reset$/, (m) => svc.resetOverrides('tax', m[1])],
  ['GET', /^\/api\/override\/fields$/, () => ({
    wage: svc.WAGE_OVERRIDE_FIELDS,
    tax: svc.TAX_OVERRIDE_FIELDS,
  })],

  // 一次性奖金
  ['GET', /^\/api\/bonus$/, () => svc.listBonusSelections()],
  ['POST', /^\/api\/bonus$/, async (m, req) => {
    const b = await readBody(req);
    return svc.selectBonus(Number(b.taxYear), b);
  }],

  // 银行卡
  ['GET', /^\/api\/bank$/, (m, req, url) => svc.listBank({
    from: url.searchParams.get('from') || undefined,
    to: url.searchParams.get('to') || undefined,
    type: url.searchParams.get('type') || undefined,
  })],
  ['POST', /^\/api\/bank$/, async (m, req) => svc.addBank(await readBody(req))],
  ['PUT', /^\/api\/bank\/(\d+)$/, async (m, req) => svc.updateBank(Number(m[1]), await readBody(req))],
  ['DELETE', /^\/api\/bank\/(\d+)$/, (m) => { svc.deleteBank(Number(m[1])); return { ok: true }; }],

  // 核对
  ['GET', /^\/api\/reconcile\/(\d{4})$/, (m) => ({
    year: Number(m[1]),
    rows: svc.getReconcile(Number(m[1])),
  })],

  ['GET', /^\/api\/periods$/, () => svc.listPeriods()],
];

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = decodeURIComponent(url.pathname);

  if (pathname.startsWith('/api/')) {
    for (const [method, re, handler] of routes) {
      const m = re.exec(pathname);
      if (!m) continue;
      if (req.method !== method) continue;
      try {
        return json(res, 200, await handler(m, req, url));
      } catch (e) {
        return json(res, 400, { error: e.message });
      }
    }
    return json(res, 404, { error: `未找到接口: ${req.method} ${pathname}` });
  }

  // 静态文件
  let file = pathname === '/' ? '/index.html' : pathname;
  const full = path.join(PUBLIC_DIR, file);
  if (!full.startsWith(PUBLIC_DIR)) return json(res, 403, { error: 'forbidden' });
  if (!fs.existsSync(full) || fs.statSync(full).isDirectory()) {
    return json(res, 404, { error: 'not found' });
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(full)] || 'application/octet-stream' });
  fs.createReadStream(full).pipe(res);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`工资核算网页版已启动: http://127.0.0.1:${PORT}`);
  console.log(`数据库: ${process.env.DB_FILE || 'data/salary.db'}`);
});
