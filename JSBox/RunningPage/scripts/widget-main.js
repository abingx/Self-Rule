// 小组件主逻辑

const utils = require("./utils");

function getWidgetURL() {
  return `jsbox://run?name=${encodeURIComponent(global.CONFIG.TARGET_SCRIPT)}`;
}

let cachedData = utils.loadCache();

function processAndRender(data) {
  const now = new Date();
  let runs = data.filter(r => r.type === "Run");
  runs.sort((a, b) => utils.parseDate(b.start_date_local) - utils.parseDate(a.start_date_local));

  const today = utils.summarize(runs, utils.startOfDay(now));
  const week = utils.summarize(runs, utils.startOfWeek(now));
  const month = utils.summarize(runs, utils.startOfMonth(now));
  const year = utils.summarize(runs, utils.startOfYear(now));

  // 昨天数据
  const yesterdayStart = new Date(now);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const yesterdayEnd = new Date(yesterdayStart);
  yesterdayEnd.setDate(yesterdayEnd.getDate() + 1);
  const yesterdayData = {
    count: runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= utils.startOfDay(yesterdayStart) && d < utils.startOfDay(yesterdayEnd);
    }).length,
    distance: (runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= utils.startOfDay(yesterdayStart) && d < utils.startOfDay(yesterdayEnd);
    }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
  };

  // 上周数据
  const lastWeekStart = new Date(utils.startOfWeek(now));
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);
  const lastWeekEnd = new Date(utils.startOfWeek(now));
  const lastWeekData = {
    count: runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastWeekStart && d < lastWeekEnd;
    }).length,
    distance: (runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastWeekStart && d < lastWeekEnd;
    }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
  };

  // 上月数据
  const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastMonthData = {
    count: runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastMonthStart && d < lastMonthEnd;
    }).length,
    distance: (runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastMonthStart && d < lastMonthEnd;
    }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
  };

  // 去年数据
  const lastYearStart = new Date(now.getFullYear() - 1, 0, 1);
  const lastYearEnd = new Date(now.getFullYear(), 0, 1);
  const lastYearData = {
    count: runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastYearStart && d < lastYearEnd;
    }).length,
    distance: (runs.filter(r => {
      const d = utils.parseDate(r.start_date_local);
      return d >= lastYearStart && d < lastYearEnd;
    }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
  };

  const latestRunDate = runs.length ? utils.parseDate(runs[0].start_date_local) : null;
  const latestRunStr = latestRunDate ? utils.formatDateTime(latestRunDate) : "N/A";
  
  const updateStr = utils.formatDateTime(now);

  $widget.setTimeline({
    render: ctx => {
      const family = ctx.family;
      const displaySize = ctx.displaySize;
      const isDarkMode = ctx.isDarkMode;
      const widgetWidth = displaySize.width;
      const widgetHeight = displaySize.height;

      console.log("Widget Family:", family, "Size:", widgetWidth, "x", widgetHeight);

      if (family === 1) {
        // Medium
        return require("./widgets/medium")(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode, getWidgetURL);
      } else if (family === 0) {
        // Small
        return require("./widgets/small")(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode, getWidgetURL);
      } else if (family === 2) {
        // Large
        return require("./widgets/large")(widgetWidth, widgetHeight, today, yesterdayData, week, lastWeekData, month, lastMonthData, year, lastYearData, latestRunStr, updateStr, isDarkMode, getWidgetURL);
      } else if (family === 3) {
        // XLarge
        return require("./widgets/xlarge")(widgetWidth, widgetHeight, family, isDarkMode);
      } else if (family === 5) {
        // Accessory Circular
        return require("./widgets/accessory-circular")(widgetWidth, widgetHeight, today, isDarkMode);
      } else if (family === 6) {
        // Accessory Rectangular
        return require("./widgets/accessory-rectangular")(widgetWidth, widgetHeight, today, isDarkMode);
      } else if (family === 7) {
        // Accessory Inline
        return require("./widgets/accessory-inline")(widgetWidth, widgetHeight, today, isDarkMode);
      }
    },
    policy: {
      afterDate: new Date(now.getTime() + 6 * 60 * 60 * 1000)
    }
  });
}

// 使用缓存数据先渲染
if (cachedData && cachedData.length > 0) {
  console.log("使用缓存数据渲染小组件");
  processAndRender(cachedData);
}

// 获取远程数据并更新
$http.get({
  url: global.CONFIG.DATA_URL,
  handler: resp => {
    if (resp.data && resp.data.length > 0) {
      utils.saveCache(resp.data);
      console.log("远程数据获取成功,已更新缓存");
      processAndRender(resp.data);
    } else if (cachedData && cachedData.length > 0) {
      console.log("远程数据为空,使用缓存数据");
    } else {
      console.error("远程数据和缓存都不可用");
    }
  }
});