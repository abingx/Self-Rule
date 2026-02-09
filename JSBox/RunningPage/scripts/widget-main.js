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

  // 计算统计数据（已包含所有需要的字段：count, distance, duration, heartRate, pace, maxDistance, bestPace）
  const today = utils.summarize(runs, utils.startOfDay(now));
  const week = utils.summarize(runs, utils.startOfWeek(now));
  const month = utils.summarize(runs, utils.startOfMonth(now));
  const year = utils.summarize(runs, utils.startOfYear(now));

  // 为 today 添加运动效果（基于平均心率和总时长）
  const todayRuns = runs.filter(r => utils.parseDate(r.start_date_local) >= utils.startOfDay(now));
  const totalMovingTime = todayRuns.reduce((sum, r) => {
    const time = r.moving_time || r.elapsed_time || 0;
    return sum + utils.parseTimeToSeconds(time);
  }, 0);
  const todayTrainingName = todayRuns.length > 0 ? todayRuns[0].name : null;
  
  // 如果今天没有跑步活动或距离为0，则显示"跑休"
  if (todayRuns.length === 0 || parseFloat(today.distance) === 0) {
    today.effect = "跑休";
  } else {
    today.effect = utils.getExerciseEffect(todayTrainingName);
  }

  // 计算 Yesterday（昨天）的统计数据
  const yesterdayStart = new Date(now);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const yesterdayStartOfDay = utils.startOfDay(yesterdayStart);
  const yesterdayEndOfDay = new Date(yesterdayStartOfDay);
  yesterdayEndOfDay.setDate(yesterdayEndOfDay.getDate() + 1);

  // 获取昨天的运行数据（仅在昨天范围内的数据）
  const yesterdayRuns = runs.filter(r => {
    const d = utils.parseDate(r.start_date_local);
    return d >= yesterdayStartOfDay && d < yesterdayEndOfDay;
  });

  // 使用过滤后的数据进行汇总
  const yesterday = utils.summarize(yesterdayRuns, yesterdayStartOfDay);

  // 为 yesterday 添加运动效果
  const yesterdayTotalMovingTime = yesterdayRuns.reduce((sum, r) => {
    const time = r.moving_time || r.elapsed_time || 0;
    return sum + utils.parseTimeToSeconds(time);
  }, 0);
  const yesterdayTrainingName = yesterdayRuns.length > 0 ? yesterdayRuns[0].name : null;

  // 如果昨天没有跑步活动或距离为0，则显示"跑休"
  if (yesterdayRuns.length === 0 || parseFloat(yesterday.distance) === 0) {
    yesterday.effect = "跑休";
  } else {
    yesterday.effect = utils.getExerciseEffect(yesterdayTrainingName);
  }

  // 计算 Last Week（上周）的统计数据 (上周一到周日)
  const currentWeekStart = utils.startOfWeek(now);
  const lastWeekStart = new Date(currentWeekStart);
  lastWeekStart.setDate(lastWeekStart.getDate() - 7);
  const lastWeekEnd = new Date(lastWeekStart);
  lastWeekEnd.setDate(lastWeekEnd.getDate() + 7);
  
  // 获取上周的运行数据（仅在上周范围内的数据）
  const lastWeekRuns = runs.filter(r => {
    const d = utils.parseDate(r.start_date_local);
    return d >= lastWeekStart && d < lastWeekEnd;
  });
  
  // 使用过滤后的数据进行汇总
  const lastWeek = utils.summarize(lastWeekRuns, lastWeekStart);

  // 计算 Last Month（上月）的统计数据 (上个月1号到月末)
  const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0); // 本月第0天是上个月最后一天
  lastMonthEnd.setHours(23, 59, 59, 999); // 设置为当天最后一刻
  
  // 获取上月的运行数据（仅在上月范围内的数据）
  const lastMonthRuns = runs.filter(r => {
    const d = utils.parseDate(r.start_date_local);
    return d >= lastMonthStart && d <= lastMonthEnd;
  });
  
  // 使用过滤后的数据进行汇总
  const lastMonth = utils.summarize(lastMonthRuns, lastMonthStart);

  // 计算 Last Year（去年）的统计数据 (上一个完整年度)
  const lastYearStart = new Date(now.getFullYear() - 1, 0, 1);
  const lastYearEnd = new Date(now.getFullYear() - 1, 11, 31); // 上年12月31日
  lastYearEnd.setHours(23, 59, 59, 999); // 设置为当天最后一刻
  
  // 获取去年的运行数据（仅在去年范围内的数据）
  const lastYearRuns = runs.filter(r => {
    const d = utils.parseDate(r.start_date_local);
    return d >= lastYearStart && d <= lastYearEnd;
  });
  
  // 使用过滤后的数据进行汇总
  const lastYear = utils.summarize(lastYearRuns, lastYearStart);

  const latestRunDate = runs.length ? utils.parseDate(runs[0].start_date_local) : null;
  const latestRunStr = latestRunDate ? utils.formatDateTime(latestRunDate) : "N/A";
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