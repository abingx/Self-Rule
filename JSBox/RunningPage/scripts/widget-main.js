// 小组件主逻辑

const utils = require("./utils");

if (global.CONFIG.SHOW_PLACEHOLDERS) {
  console.log("SHOW_PLACEHOLDERS is enabled but placeholder rendering is not implemented yet.");
}

function getWidgetURL() {
  return `jsbox://run?name=${encodeURIComponent(global.CONFIG.TARGET_SCRIPT)}`;
}

let cachedData = utils.loadCache();

// 统一清洗输入数据，确保后续统计只处理可用的 Run 数据。
// 这里会补充标准化字段（时间戳、公里数、秒数）供统计阶段复用。
function sanitizeData(data) {
  if (!Array.isArray(data)) return [];
  return data
    .filter(item => item && typeof item === "object")
    .map(utils.normalizeRunData)
    .filter(item => item && item.type === "Run");
}

function processAndRender(data) {
  const now = new Date();
  // 先清洗再排序，保证「最近一次跑步」始终可通过 runs[0] 读取。
  let runs = sanitizeData(data);
  runs.sort((a, b) => {
    const timeA = Number.isFinite(a._startTimestamp) ? a._startTimestamp : utils.parseDate(a.start_date_local).getTime();
    const timeB = Number.isFinite(b._startTimestamp) ? b._startTimestamp : utils.parseDate(b.start_date_local).getTime();
    const safeA = isFinite(timeA) ? timeA : -Infinity;
    const safeB = isFinite(timeB) ? timeB : -Infinity;
    return safeB - safeA;
  });

  // 计算统计数据（已包含所有需要的字段：count, distance, duration, heartRate, pace, maxDistance, bestPace）
  const today = utils.summarize(runs, utils.startOfDay(now));
  const week = utils.summarize(runs, utils.startOfWeek(now));
  const month = utils.summarize(runs, utils.startOfMonth(now));
  const year = utils.summarize(runs, utils.startOfYear(now));

  // 通用函数：获取指定时间段的统计数据和运动效果
  function getPeriodData(start, end, defaultEffect = "跑休") {
    const startTs = start.getTime();
    const endTs = end.getTime();
    const periodRuns = runs.filter(r => {
      const ts = Number.isFinite(r._startTimestamp) ? r._startTimestamp : utils.parseDate(r.start_date_local).getTime();
      return !isNaN(ts) && ts >= startTs && ts < endTs;
    });
    
    // summarize 只关心 >= since，传入已切片后的 periodRuns 可得到该时间窗的汇总。
    const stats = utils.summarize(periodRuns, start);
    
    // 如果时间段内没有跑步活动或距离为0，则显示默认效果
    if (periodRuns.length === 0 || parseFloat(stats.distance) === 0) {
      stats.effect = defaultEffect;
    } else {
      const trainingName = periodRuns.length > 0 ? periodRuns[0].name : null;
      stats.effect = utils.getExerciseEffect(trainingName);
    }
    
    return { stats, runs: periodRuns };
  }

  // 为 today 添加运动效果（基于训练名称）
  const { stats: todayWithEffect } = getPeriodData(utils.startOfDay(now), utils.startOfDay(new Date(now.getTime() + 24 * 60 * 60 * 1000)));
  today.effect = todayWithEffect.effect;

  // 计算 Yesterday（昨天）的统计数据
  const yesterdayStart = new Date(now);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const yesterdayStartOfDay = utils.startOfDay(yesterdayStart);
  const yesterdayEndOfDay = new Date(yesterdayStartOfDay);
  yesterdayEndOfDay.setDate(yesterdayEndOfDay.getDate() + 1);

  const { stats: yesterday } = getPeriodData(yesterdayStartOfDay, yesterdayEndOfDay);

  // 计算 Last Week（上周）的统计数据 (上周一到周日)
  const currentWeekStart = utils.startOfWeek(now);
  const lastWeekStart = new Date(currentWeekStart);
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);
  const lastWeekEnd = new Date(lastWeekStart);
  lastWeekEnd.setDate(lastWeekEnd.getDate() + 7);

  const { stats: lastWeek } = getPeriodData(lastWeekStart, lastWeekEnd);

  // 计算 Last Month（上月）的统计数据 (上个月1号到月末)
  const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0); // 本月第0天是上个月最后一天
  lastMonthEnd.setHours(23, 59, 59, 999); // 设置为当天最后一刻

  // 为上月数据单独处理，因为月份结束时间的特殊性
  const lastMonthRuns = runs.filter(r => {
    const ts = Number.isFinite(r._startTimestamp) ? r._startTimestamp : utils.parseDate(r.start_date_local).getTime();
    return !isNaN(ts) && ts >= lastMonthStart.getTime() && ts <= lastMonthEnd.getTime();
  });

  const lastMonth = utils.summarize(lastMonthRuns, lastMonthStart);

  // 计算 Last Year（去年）的统计数据 (上一个完整年度)
  const lastYearStart = new Date(now.getFullYear() - 1, 0, 1);
  const lastYearEnd = new Date(now.getFullYear() - 1, 11, 31); // 上年12月31日
  lastYearEnd.setHours(23, 59, 59, 999); // 设置为当天最后一刻

  // 为去年数据单独处理，因为年份结束时间的特殊性
  const lastYearRuns = runs.filter(r => {
    const ts = Number.isFinite(r._startTimestamp) ? r._startTimestamp : utils.parseDate(r.start_date_local).getTime();
    return !isNaN(ts) && ts >= lastYearStart.getTime() && ts <= lastYearEnd.getTime();
  });

  const lastYear = utils.summarize(lastYearRuns, lastYearStart);

  const latestRunDate = runs.length ? utils.parseDate(runs[0].start_date_local) : null;
  const latestRunStr = latestRunDate && !isNaN(latestRunDate.getTime())
    ? utils.formatDateTime(latestRunDate)
    : "N/A";
  const updateStr = utils.formatDateTime(now);

  const widgetData = {
    today,
    yesterday,
    week,
    lastWeek,
    month,
    lastMonth,
    year,
    lastYear,
    latestRunStr,
    updateStr,
    getWidgetURL
  };

  $widget.setTimeline({
    render: ctx => {
      const family = ctx.family;
      const displaySize = ctx.displaySize;
      const widgetWidth = displaySize.width;
      const widgetHeight = displaySize.height;
      const isDarkMode = ctx.isDarkMode;

      console.log("Widget Family:", family, "Size:", widgetWidth, "x", widgetHeight);

      if (family === 0) {
        return require("./widgets/small")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 1) {
        return require("./widgets/medium")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 2) {
        return require("./widgets/large")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 3) {
        return require("./widgets/xlarge")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 5) {
        return require("./widgets/accessory-circular")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 6) {
        return require("./widgets/accessory-rectangular")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      } else if (family === 7) {
        return require("./widgets/accessory-inline")(widgetWidth, widgetHeight, isDarkMode, widgetData);
      }
    },
    policy: (() => {
      // 白天更新频率更高，夜间降频以减少不必要刷新。
      const currentHour = now.getHours();
      if (currentHour >= 8 && currentHour < 20) {
        // 8:00 到 20:00 之间每小时更新
        return {
          afterDate: new Date(now.getTime() + 1 * 60 * 60 * 1000)
        };
      } else {
        // 其余时间每6小时更新
        return {
          afterDate: new Date(now.getTime() + 6 * 60 * 60 * 1000)
        };
      }
    })()
  });
}

// 使用缓存数据先渲染
if (cachedData && cachedData.length > 0) {
  console.log("使用缓存数据渲染小组件");
  processAndRender(cachedData);
} else {
  console.log("无缓存数据，使用空数据渲染小组件");
  processAndRender([]);
}

// 获取远程数据并更新
$http.get({
  url: global.CONFIG.DATA_URL,
  handler: resp => {
    if (Array.isArray(resp.data) && resp.data.length > 0) {
      // 比较远程数据与缓存数据
      const hasChanges = !cachedData || !compareData(cachedData, resp.data);
      
      if (hasChanges) {
        utils.saveCache(resp.data);
        cachedData = resp.data;
        console.log("远程数据获取成功且有更新,已更新缓存");
        processAndRender(resp.data);
      } else {
        console.log("远程数据获取成功但无变化,跳过更新");
      }
    } else {
      console.log("远程数据获取失败或为空,保持使用缓存数据");
    }
  }
});

// 比较两个数据数组是否相同
function compareData(oldData, newData) {
  if (!oldData || !newData) {
    return false;
  }
  
  if (oldData.length !== newData.length) {
    return false;
  }

  const normalize = arr =>
    arr
      .filter(item => item && typeof item === "object")
      // 只比较会影响展示的关键字段，忽略顺序和无关字段。
      .map(item => ({
        id: item.id,
        start_date_local: item.start_date_local,
        distance: item.distance,
        moving_time: item.moving_time,
        type: item.type
      }))
      .sort((a, b) => {
        const idA = String(a.id ?? "");
        const idB = String(b.id ?? "");
        if (idA !== idB) return idA.localeCompare(idB);
        return String(a.start_date_local ?? "").localeCompare(String(b.start_date_local ?? ""));
      });

  const oldNormalized = normalize(oldData);
  const newNormalized = normalize(newData);

  // 比较关键字段（忽略原始数组顺序）
  for (let i = 0; i < oldNormalized.length; i++) {
    const oldItem = oldNormalized[i];
    const newItem = newNormalized[i];

    if (oldItem.id !== newItem.id ||
        oldItem.start_date_local !== newItem.start_date_local ||
        oldItem.distance !== newItem.distance ||
        oldItem.moving_time !== newItem.moving_time ||
        oldItem.type !== newItem.type) {
      return false;
    }
  }
  
  return true;
}
