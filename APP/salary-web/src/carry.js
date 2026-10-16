/**
 * 带入引擎（需求 2）
 *
 * 已确认规则：
 *  - 触发时机：保存草稿（方案 A）
 *  - 参与带入：wage_item.carry_forward = 1 且 side='regular' 的常规项
 *  - 不参与带入：补发(makeup)、补扣(clawback) —— 它们存在 wage_adjustment 表，天然不参与
 *  - 级联：需要级联到更后月份
 *  - 12 月修改后带入次年 1 月
 *  - 下月已有手工值：CARRY_OVERWRITE_MANUAL 控制（当前为 false = 不覆盖）
 *  - 已确认(confirmed)月份：允许修改，但改动只在当前行生效（不向外传播）
 *  - 带入生成的下月记录若落在未到达月份：只生成不显示
 *  - 从保存行一路带入到"当前月"（CARRY_THROUGH_TO_TODAY）：空库下录入 1 月可一路带到当前月
 */
import { CARRY_OVERWRITE_MANUAL, CARRY_CASCADE, CARRY_ACROSS_YEAR, CARRY_THROUGH_TO_TODAY } from './config.js';
import { addMonths, yearOf, monthOf, round2, todayPeriod } from './period.js';

/** 取/建某月的工资记录 */
function ensureRecord(db, period) {
  let rec = db.prepare(`SELECT * FROM wage_record WHERE period = ?`).get(period);
  if (!rec) {
    db.prepare(`INSERT INTO wage_record (period, status) VALUES (?, 'draft')`).run(period);
    rec = db.prepare(`SELECT * FROM wage_record WHERE period = ?`).get(period);
  }
  return rec;
}

export function getRecord(db, period) {
  return db.prepare(`SELECT * FROM wage_record WHERE period = ?`).get(period);
}

/** 取某月常规项取值 map: itemId -> { amount, source } */
export function getRegularValues(db, recordId) {
  const rows = db
    .prepare(`SELECT item_id, amount, source, carried_from_period FROM wage_item_value WHERE wage_record_id = ?`)
    .all(recordId);
  const map = new Map();
  for (const r of rows) map.set(r.item_id, r);
  return map;
}

/** 是否发生了跨年（用于 12 月 -> 次年 1 月的判定） */
function crossesYear(from, to) {
  return yearOf(to) === yearOf(from) + 1 && monthOf(to) === 1;
}

/**
 * 从 fromPeriod 向下级联带入。
 * @returns {Array} 带入明细日志
 */
export function carryForward(db, fromPeriod) {
  const logs = [];
  const items = db
    .prepare(`SELECT * FROM wage_item WHERE is_active = 1 AND carry_forward = 1 AND side = 'regular' ORDER BY sort_order`)
    .all();

  const fromRec = getRecord(db, fromPeriod);
  if (!fromRec) return logs;

  // 带入延伸的终点：默认到"当前月"为止（空库录入 1 月可一路带到当前月）
  const today = todayPeriod();

  let prevPeriod = fromPeriod;
  let prevRec = fromRec;
  let guard = 0;

  while (guard++ < 36) {
    const nextPeriod = addMonths(prevPeriod, 1);

    // 12 月 -> 次年 1 月：CARRY_ACROSS_YEAR 控制
    if (crossesYear(prevPeriod, nextPeriod) && !CARRY_ACROSS_YEAR) {
      logs.push({ from: prevPeriod, to: nextPeriod, item: '*', action: 'skipped_year_boundary' });
      break;
    }

    // 目标月记录：紧邻下月一定创建；一路延伸时，当前月之前的空缺月份也创建
    let nextRec = getRecord(db, nextPeriod);
    if (!nextRec) {
      const shouldCreate = guard === 1
        || (CARRY_THROUGH_TO_TODAY && CARRY_CASCADE && nextPeriod <= today);
      if (shouldCreate) {
        nextRec = ensureRecord(db, nextPeriod);
        logs.push({ from: prevPeriod, to: nextPeriod, item: '*', action: 'record_created' });
      } else {
        break; // 不延伸时，只保证生成紧邻下一月，避免铺出大量空月份
      }
    }

    // 已确认月份：不覆盖
    if (nextRec.status === 'confirmed') {
      logs.push({ from: prevPeriod, to: nextPeriod, item: '*', action: 'skipped_confirmed' });
      break;
    }

    const prevValues = getRegularValues(db, prevRec.id);
    const nextValues = getRegularValues(db, nextRec.id);

    // 下月已有手工值 -> 不覆盖，并且不再继续向后级联
    const hasManual = items.some((it) => {
      const v = nextValues.get(it.id);
      return v && v.source === 'manual';
    });
    if (hasManual && !CARRY_OVERWRITE_MANUAL) {
      logs.push({ from: prevPeriod, to: nextPeriod, item: '*', action: 'skipped_manual' });
      break;
    }

    let changed = false;
    for (const it of items) {
      const pv = prevValues.get(it.id);
      const newAmount = pv ? round2(pv.amount) : 0;
      const cur = nextValues.get(it.id);

      if (cur && cur.source === 'manual' && !CARRY_OVERWRITE_MANUAL) {
        logs.push({
          from: prevPeriod, to: nextPeriod, item: it.code,
          old: cur.amount, new: newAmount, action: 'skipped_manual',
        });
        continue;
      }
      if (cur && round2(cur.amount) === newAmount && cur.source === 'carried') continue;

      db.prepare(`
        INSERT INTO wage_item_value (wage_record_id, item_id, amount, source, carried_from_period)
        VALUES (?, ?, ?, 'carried', ?)
        ON CONFLICT(wage_record_id, item_id) DO UPDATE SET
          amount = excluded.amount,
          source = 'carried',
          carried_from_period = excluded.carried_from_period
      `).run(nextRec.id, it.id, newAmount, prevPeriod);

      logs.push({
        from: prevPeriod, to: nextPeriod, item: it.code,
        old: cur ? cur.amount : null, new: newAmount, action: 'carried',
      });
      changed = true;
    }

    if (!CARRY_CASCADE) break;
    // 级联终止条件：下月没有任何常规项被改动，说明再往后也不会变
    if (!changed) break;

    prevPeriod = nextPeriod;
    prevRec = nextRec;
  }

  for (const l of logs) {
    db.prepare(`
      INSERT INTO carry_log (from_period, to_period, item_code, old_value, new_value, action)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(l.from, l.to, l.item, l.old ?? null, l.new ?? null, l.action);
  }
  return logs;
}

/** 手工设置某月某常规项的值（标记 source='manual'） */
export function setRegularValue(db, recordId, itemId, amount) {
  db.prepare(`
    INSERT INTO wage_item_value (wage_record_id, item_id, amount, source, carried_from_period)
    VALUES (?, ?, ?, 'manual', NULL)
    ON CONFLICT(wage_record_id, item_id) DO UPDATE SET
      amount = excluded.amount,
      source = 'manual',
      carried_from_period = NULL
  `).run(recordId, itemId, round2(amount));
}

export { ensureRecord };
