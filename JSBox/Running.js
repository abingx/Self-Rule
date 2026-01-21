/**
 * JSBox 跑步数据小组件 - 多尺寸自适应版本
 * 
 * 功能说明:
 * - 支持多种小组件尺寸 (Small, Medium, Large, xLarge, Accessory)
 * - 显示今天/周/月/年的跑步统计数据
 * - 自动从远程 JSON 数据源获取跑步记录
 * - 根据深色/浅色主题自动调整显示样式
 * 
 * 数据来源: running_page 项目的活动数据 API
 */

// ===== 全局配置 =====
/**
 * 控制占位符的显示/隐藏
 * true: 显示占位符 (用于排版调试)
 * false: 隐藏占位符 (生产环境，占位符颜色与背景相同)
 */
const SHOW_PLACEHOLDERS = false;

// ===== 常量定义 =====
/** 远程数据 URL，包含所有跑步活动的 JSON 格式数据 */
const DATA_URL = "https://raw.githubusercontent.com/abingx/running_page/master/src/static/activities.json";

/**
 * 排版占位符说明:
 * ^ 用于水平对齐的空格占位符
 * `_`_`_`_`_`_`_`_`_` 用于创建分隔线的占位符
 * 排版确定后可替换为实际空格
 * 
 * 通过 SHOW_PLACEHOLDERS 全局变量控制显示/隐藏
 */

/**
 * 占位符生成函数
 * 根据 SHOW_PLACEHOLDERS 变量决定返回占位符还是空字符串
 * 不影响排版布局，因为占位符保留宽度
 */
function getPlaceholder(count = 1) {
  if (SHOW_PLACEHOLDERS) {
    return "^".repeat(count);  // 显示时返回占位符
  } else {
    return " ".repeat(count);  // 隐藏时返回等长空格（保持排版）
  }
}

/**
 * 分隔线生成函数
 * 根据 SHOW_PLACEHOLDERS 变量决定返回分隔线还是空白行
 */
function getSeparator() {
  if (SHOW_PLACEHOLDERS) {
    return "`_`_`_`_`_`_`_`_`_`";  // 显示时返回分隔线
  } else {
    return "              ";  // 隐藏时返回等长空白
  }
}

/**
 * ===== 统一边距配置 =====
 * 为不同尺寸的小组件定义一致的内边距和间距
 * 确保各尺寸小组件的排版风格统一
 */
const WIDGET_SPACING = {
  // Small 尺寸 (2x2 小方块) 的边距和间距配置
  small: {
    paddingTop: 0,        // 上边距
    paddingRight: 12,     // 右边距
    paddingBottom: 0,     // 下边距
    paddingLeft: 12,      // 左边距
    dataSpacing: 6        // 数据行与行之间的间距
  },
  // Medium 尺寸 (2x3 矩形) 的边距和间距配置
  medium: {
    paddingTop: 0,        // 上边距
    paddingRight: 12,     // 右边距
    paddingBottom: 0,     // 下边距
    paddingLeft: 12,      // 左边距
    dataSpacing: 6        // 数据行与行之间的间距
  },
  // Large 尺寸 (4x4 大方块) 的边距和间距配置
  large: {
    paddingTop: 0,        // 上边距
    paddingRight: 12,     // 右边距
    paddingBottom: 0,     // 下边距
    paddingLeft: 12,      // 左边距
    dataSpacing: 10       // 数据行与行之间的间距
  }
};


/**
 * ===== 统一字体配置 =====
 * 为不同尺寸的小组件定义一致的字体、字号设置
 * 确保可读性和视觉一致性
 */
const WIDGET_FONTS = {
  // Small 尺寸字体配置
  small: {
    fontFamily: "Menlo",           // 正文字体 (等宽字体，便于对齐)
    titleFontFamily: "Menlo-Bold", // 标题字体 (加粗等宽字体)
    titleFontSize: 18,             // 标题字号
    gridFontSize: 12,              // 数据网格字号
    footerFontSize: 6,             // 页脚/时间戳字号
    titleTopSeparatorFontSize: 13, // 标题上方分隔线字号
    topSeparatorFontSize: 13,       // 标题和数据区之间的分隔线字号
    bottomSeparatorFontSize: 8,    // 数据区和时间戳区之间的分隔线字号
    footerBottomSeparatorFontSize: 4  // 时间戳下方分隔线字号
  },
  // Medium 尺寸字体配置
  medium: {
    fontFamily: "Menlo",           // 正文字体
    titleFontFamily: "Menlo-Bold", // 标题字体
    titleFontSize: 22,             // 标题字号 (比 Small 更大)
    gridFontSize: 14,              // 数据网格字号 (比 Small 更大)
    footerFontSize: 8,            // 页脚/时间戳字号
    titleTopSeparatorFontSize: 12,  // 标题上方分隔线字号
    topSeparatorFontSize: 6,       // 标题和数据区之间的分隔线字号
    bottomSeparatorFontSize: 8,    // 数据区和时间戳区之间的分隔线字号
    footerBottomSeparatorFontSize: 8  // 时间戳下方分隔线字号
  },
  // Large 尺寸字体配置
  large: {
    fontFamily: "Menlo",           // 正文字体
    titleFontFamily: "Menlo-Bold", // 标题字体
    titleFontSize: 22,             // 标题字号
    gridFontSize: 14,              // 数据网格字号
    footerFontSize: 8,            // 页脚/时间戳字号
    titleTopSeparatorFontSize: 30, // 标题上方分隔线字号
    topSeparatorFontSize: 20,      // 标题和数据区之间的分隔线字号
    bottomSeparatorFontSize: 30,   // 数据区和时间戳区之间的分隔线字号
    footerBottomSeparatorFontSize: 20  // 时间戳下方分隔线字号
  }
};


/**
 * ===== 统一布局比例配置 =====
 * 定义各尺寸小组件的内部区域高度比例
 * 包括顶部标题区、中部数据区、底部时间戳区
 */
const WIDGET_LAYOUT = {
  // Small 尺寸布局比例
  small: {
    topHeightRatio: 0.25,      // 标题区占总高度的 25%
    middleHeightRatio: 0.55,   // 数据区占总高度的 55%
    bottomHeightRatio: 0.20    // 时间戳区占总高度的 20%
  },
  // Medium 尺寸布局比例
  medium: {
    topHeightRatio: 0.25,      // 标题区占总高度的 25%
    middleHeightRatio: 0.55,   // 数据区占总高度的 55%
    bottomHeightRatio: 0.20    // 时间戳区占总高度的 20%
  },
  // Large 尺寸布局比例
  large: {
    topHeightRatio: 0.15,      // 标题区占总高度的 15% (更紧凑)
    middleHeightRatio: 0.70,   // 数据区占总高度的 70% (更大)
    bottomHeightRatio: 0.15    // 时间戳区占总高度的 15%
  }
};

/**
 * ===== 工具函数 =====
 */

/**
 * 解析 ISO 格式日期字符串为 Date 对象
 * 将日期字符串中的空格替换为 'T'，使其符合 ISO 8601 格式
 * 
 * @param {string} str - ISO 格式的日期字符串，如 "2024-01-15 14:30:00"
 * @returns {Date} 解析后的 Date 对象
 */
function parseDate(str) {
  return new Date(str.replace(" ", "T"));
}

/**
 * 获取指定日期的天开始时间 (00:00:00)
 * 用于统计当天的数据
 * 
 * @param {Date} d - 输入的日期
 * @returns {Date} 该天的 00:00:00 时刻
 */
function startOfDay(d) {
  const date = new Date(d);
  date.setHours(0, 0, 0, 0);
  return date;
}

/**
 * 获取指定日期所在周的周一时间 (00:00:00)
 * 用于统计本周的数据 (周一到周日)
 * 
 * @param {Date} d - 输入的日期
 * @returns {Date} 该周周一的 00:00:00 时刻
 */
function startOfWeek(d) {
  const date = new Date(d);
  const day = date.getDay() || 7; // 周日变为 7
  if (day !== 1) date.setDate(date.getDate() - (day - 1));
  date.setHours(0, 0, 0, 0);
  return date;
}

/**
 * 获取指定日期所在月的月初时间 (00:00:00)
 * 用于统计本月的数据
 * 
 * @param {Date} d - 输入的日期
 * @returns {Date} 该月 1 号的 00:00:00 时刻
 */
function startOfMonth(d) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

/**
 * 获取指定日期所在年的年初时间 (00:00:00)
 * 用于统计本年的数据
 * 
 * @param {Date} d - 输入的日期
 * @returns {Date} 该年 1 月 1 号的 00:00:00 时刻
 */
function startOfYear(d) {
  return new Date(d.getFullYear(), 0, 1);
}

/**
 * 统计指定时间范围内的跑步数据
 * 计算总次数和总距离 (单位: km)
 * 
 * @param {Array} list - 所有跑步记录的数组
 * @param {Date} since - 统计起始时间 (包含)
 * @returns {Object} 包含 count (次数) 和 distance (距离，单位 km) 的对象
 */
function summarize(list, since) {
  // 过滤出指定时间后的跑步记录
  const runs = list.filter(r => parseDate(r.start_date_local) >= since);
  const count = runs.length;
  // 累加距离并转换为 km
  const distance = runs.reduce((sum, r) => sum + r.distance, 0) / 1000;
  return { count, distance: distance.toFixed(2) };
}


/**
 * ===== 主程序入口 =====
 * 从远程 API 获取数据，计算统计数据，并渲染小组件
 */

// 发起 HTTP GET 请求获取跑步数据
$http.get({
  url: DATA_URL,
  handler: resp => {
    // 获取当前时间
    const now = new Date();
    
    // 过滤出所有 "Run" 类型的活动 (排除其他类型如散步等)
    let data = resp.data.filter(r => r.type === "Run");
    
    // 按最新日期倒序排序 (最新的跑步记录在最前)
    data.sort((a, b) => parseDate(b.start_date_local) - parseDate(a.start_date_local));

    // ===== 计算当前时期的统计数据 =====
    const today = summarize(data, startOfDay(now));      // 今天的跑步统计
    const week = summarize(data, startOfWeek(now));      // 本周的跑步统计
    const month = summarize(data, startOfMonth(now));    // 本月的跑步统计
    const year = summarize(data, startOfYear(now));      // 本年的跑步统计
    
    // ===== 计算前一时期的统计数据 =====
    
    // 昨天的跑步数据 (仅统计昨天一天，而不是从昨天开始的累积)
    const yesterdayStart = new Date(now);
    yesterdayStart.setDate(yesterdayStart.getDate() - 1);
    const yesterdayEnd = new Date(yesterdayStart);
    yesterdayEnd.setDate(yesterdayEnd.getDate() + 1);
    const yesterdayData = {
      count: data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= startOfDay(yesterdayStart) && d < startOfDay(yesterdayEnd);
      }).length,
      distance: (data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= startOfDay(yesterdayStart) && d < startOfDay(yesterdayEnd);
      }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
    };
    
    // 上周的跑步数据
    const lastWeekStart = new Date(startOfWeek(now));
    lastWeekStart.setDate(lastWeekStart.getDate() - 7);
    const lastWeekEnd = new Date(startOfWeek(now));
    const lastWeekData = {
      count: data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastWeekStart && d < lastWeekEnd;
      }).length,
      distance: (data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastWeekStart && d < lastWeekEnd;
      }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
    };
    
    // 上月的跑步数据
    const lastMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastMonthData = {
      count: data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastMonthStart && d < lastMonthEnd;
      }).length,
      distance: (data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastMonthStart && d < lastMonthEnd;
      }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
    };
    
    // 去年的跑步数据
    const lastYearStart = new Date(now.getFullYear() - 1, 0, 1);
    const lastYearEnd = new Date(now.getFullYear(), 0, 1);
    const lastYearData = {
      count: data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastYearStart && d < lastYearEnd;
      }).length,
      distance: (data.filter(r => {
        const d = parseDate(r.start_date_local);
        return d >= lastYearStart && d < lastYearEnd;
      }).reduce((sum, r) => sum + r.distance, 0) / 1000).toFixed(2)
    };

    // ===== 计算时间戳显示内容 =====
    
    // 最新跑步时间 (如果有记录则显示，否则显示 "N/A")
    const latestRunDate = data.length ? parseDate(data[0].start_date_local) : null;
    const latestRunStr = latestRunDate
      ? latestRunDate.toLocaleDateString() + " " + latestRunDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      : "N/A";
    
    // 数据更新时间 (小组件刷新时间)
    const updateStr = now.toLocaleDateString() + " " + now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    // ===== 设置小组件渲染 =====
    // 使用时间线 API，根据不同的小组件尺寸选择对应的渲染函数
    $widget.setTimeline({
      render: ctx => {
        const family = ctx.family;           // 小组件尺寸类型
        const displaySize = ctx.displaySize; // 显示尺寸 (宽度和高度)
        const isDarkMode = ctx.isDarkMode;   // 是否为深色模式
        const widgetWidth = displaySize.width;   // 小组件宽度
        const widgetHeight = displaySize.height; // 小组件高度

        console.log("Widget Family:", family, "Size:", widgetWidth, "x", widgetHeight);

        // 根据小组件家族类型 (family) 返回相应的渲染结果
        // family 0 = Small (2x2), 1 = Medium (2x3), 2 = Large (4x4), 3 = xLarge (4x5 等)
        // family 5 = accessoryCircular (1x1), 6 = accessoryRectangular (1x2), 7 = accessoryInline (一行)
        if (family === 1) {
          return renderMediumWidget(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode);
        } else if (family === 0) {
          return renderSmallWidget(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode);
        } else if (family === 2) {
          return renderLargeWidget(widgetWidth, widgetHeight, today, yesterdayData, week, lastWeekData, month, lastMonthData, year, lastYearData, latestRunStr, updateStr, isDarkMode);
        } else if (family === 3) {
          return renderXLargeWidget(widgetWidth, widgetHeight, family, isDarkMode);
        } else if (family === 5) {
          // accessoryCircular (1x1 圆形锁屏小组件)
          return renderAccessoryCircular(widgetWidth, widgetHeight, today, isDarkMode);
        } else if (family === 6) {
          // accessoryRectangular (1x2 长方形锁屏小组件)
          return renderAccessoryRectangular(widgetWidth, widgetHeight, today, isDarkMode);
        } else if (family === 7) {
          // accessoryInline (在日期后面的一行信息)
          return renderAccessoryInline(widgetWidth, widgetHeight, today, isDarkMode);
        }
      },
      policy: {
        // 设置时间线更新策略：6 小时后自动刷新
        afterDate: new Date(now.getTime() + 6 * 60 * 60 * 1000)
      }
    });
  }
});


/**
 * ===== Small 尺寸渲染函数 =====
 * 用于 2x2 的小尺寸小组件
 * 显示紧凑的 Summary 标题、Today/Week/Month/Year 数据、Latest/Update 时间戳
 * 布局与 Medium 类似，但字号更小
 * 
 * @param {number} smallW - 小组件宽度
 * @param {number} smallH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {Object} week - 本周的统计数据
 * @param {Object} month - 本月的统计数据
 * @param {Object} year - 本年的统计数据
 * @param {string} latestRunStr - 最新跑步时间戳字符串
 * @param {string} updateStr - 数据更新时间戳字符串
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderSmallWidget(smallW, smallH, today, week, month, year, latestRunStr, updateStr, isDarkMode) {
  // 使用统一配置
  const fonts = WIDGET_FONTS.small;
  const layout = WIDGET_LAYOUT.small;
  const spacing = WIDGET_SPACING.small;

  /**
   * 创建数据单元格 (文本视图)
   * 用于生成表格中的每一个数据单元
   * 
   * @param {string} text - 单元格内容
   * @param {string} align - 对齐方式 ("left" 或 "right")
   * @returns {Object} 文本视图对象
   */
  function createSmallCell(text, align) {
    return {
      type: "text",
      props: {
        text,
        font: $font(fonts.fontFamily, fonts.gridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing
      }
    };
  }

  /**
   * 左边填充字符串 (使用占位符)
   * 确保数字右对齐
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} str - 输入字符串
   * @param {number} width - 目标宽度
   * @returns {string} 填充后的字符串
   */
  function padLeft(str, width) {
    return str.padStart(width, getPlaceholder(1));
  }
  
  /**
   * 格式化标签 (右边填充)
   * 标签后面填充占位符
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} label - 标签名称
   * @returns {string} 格式化后的标签
   */
  function formatLabel(label) {
    return label.padEnd(5, getPlaceholder(1));
  }
  
  /**
   * 格式化跑步次数显示 (右对齐)
   * 
   * @param {number} count - 跑步次数
   * @returns {string} 格式化的跑步次数字符串
   */
  function formatCount(count) {
    return padLeft(count.toString(), 3);
  }
  
  /**
   * 格式化距离显示 (单位: km，右对齐)
   * 距离显示为两位小数
   * 
   * @param {string} distance - 距离值 (单位 km)
   * @returns {string} 格式化的距离字符串
   */
  function formatDistance(distance) {
    return padLeft(Number(distance).toFixed(2), 7);
  }

  // ===== 数据格式化 =====
  const smallTodayLabel = formatLabel("Today");
  const smallTodayCount = formatCount(today.count);
  const smallTodayDistance = formatDistance(today.distance);
  
  const smallWeekLabel = formatLabel("Week");
  const smallWeekCount = formatCount(week.count);
  const smallWeekDistance = formatDistance(week.distance);
  
  const smallMonthLabel = formatLabel("Month");
  const smallMonthCount = formatCount(month.count);
  const smallMonthDistance = formatDistance(month.distance);
  
  const smallYearLabel = formatLabel("Year");
  const smallYearCount = formatCount(year.count);
  const smallYearDistance = formatDistance(year.distance);

  // ===== 返回小组件布局结构 =====
  return {
    type: "vstack",           // 竖直堆栈布局
    props: { 
      spacing: 0,
      padding: $insets(spacing.paddingTop, spacing.paddingRight, spacing.paddingBottom, spacing.paddingLeft)
    },
    views: [
      // ===== 标题上方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.titleTopSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 上部标题区 =====
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 0
        },
        views: [{
          type: "text",
          props: {
            text: "Summary",  // 小组件标题
            font: $font(fonts.titleFontFamily, fonts.titleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      
      // ===== 标题和数据之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.topSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 中部数据网格区 =====
      // 使用 vgrid 创建表格布局：3 列分别为 标签、次数、距离
      {
        type: "vgrid",
        props: {
          columns: [
            { fixed: (smallW - spacing.paddingLeft - spacing.paddingRight) * 0.36 },  // 标签列宽度 36%
            { fixed: (smallW - spacing.paddingLeft - spacing.paddingRight) * 0.22 },  // 次数列宽度 22%
            { fixed: (smallW - spacing.paddingLeft - spacing.paddingRight) * 0.42 }   // 距离列宽度 42%
          ],
          spacing: spacing.dataSpacing
        },
        views: [
          // Today 行
          createSmallCell(smallTodayLabel, "left"), createSmallCell(smallTodayCount, "right"), createSmallCell(smallTodayDistance, "right"),
          // Week 行
          createSmallCell(smallWeekLabel, "left"), createSmallCell(smallWeekCount, "right"), createSmallCell(smallWeekDistance, "right"),
          // Month 行
          createSmallCell(smallMonthLabel, "left"), createSmallCell(smallMonthCount, "right"), createSmallCell(smallMonthDistance, "right"),
          // Year 行
          createSmallCell(smallYearLabel, "left"), createSmallCell(smallYearCount, "right"), createSmallCell(smallYearDistance, "right")
        ]
      },
      
      // ===== 数据和时间戳之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.bottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 下部时间戳区 =====
      // 显示最新跑步时间和数据更新时间
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 1
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          }
        ]
      },
      
      // ===== 时间戳下方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.footerBottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}


/**
 * ===== Medium 尺寸渲染函数 =====
 * 用于 2x3 的中等尺寸小组件
 * 显示 Summary 标题、Today/Week/Month/Year 的次数和距离数据、Latest/Update 时间戳
 * 
 * @param {number} mediumW - 小组件宽度
 * @param {number} mediumH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {Object} week - 本周的统计数据
 * @param {Object} month - 本月的统计数据
 * @param {Object} year - 本年的统计数据
 * @param {string} latestRunStr - 最新跑步时间戳字符串
 * @param {string} updateStr - 数据更新时间戳字符串
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderMediumWidget(mediumW, mediumH, today, week, month, year, latestRunStr, updateStr, isDarkMode) {
  // 使用统一配置
  const fonts = WIDGET_FONTS.medium;
  const layout = WIDGET_LAYOUT.medium;
  const spacing = WIDGET_SPACING.medium;

  /**
   * 创建数据单元格 (文本视图)
   * 用于生成表格中的每一个数据单元
   * 
   * @param {string} text - 单元格内容
   * @param {string} align - 对齐方式 ("left" 或 "right")
   * @returns {Object} 文本视图对象
   */
  function createMediumCell(text, align) {
    return {
      type: "text",
      props: {
        text,
        font: $font(fonts.fontFamily, fonts.gridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing
      }
    };
  }

  /**
   * 左边填充字符串 (使用占位符)
   * 确保数字右对齐
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} str - 输入字符串
   * @param {number} width - 目标宽度
   * @returns {string} 填充后的字符串
   */
  function padLeft(str, width) {
    return str.padStart(width, getPlaceholder(1));
  }
  
  /**
   * 格式化标签 (右边填充)
   * 标签后面填充占位符
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} label - 标签名称
   * @returns {string} 格式化后的标签
   */
  function formatLabel(label) {
    return label.padEnd(9, getPlaceholder(1));
  }
  
  /**
   * 格式化跑步次数显示
   * 自动处理单复数形式 (run/runs)
   * 
   * @param {number} count - 跑步次数
   * @returns {string} 格式化的跑步次数字符串
   */
  function formatRuns(count) {
    if (count === 0) {
      return padLeft("0", 3) + " run" + getPlaceholder(1);
    } else if (count === 1) {
      return padLeft("1", 3) + " run" + getPlaceholder(1);
    } else {
      return padLeft(count.toString(), 3) + " runs";
    }
  }
  
  /**
   * 格式化距离显示 (单位: km)
   * 距离显示为两位小数，右对齐
   * 
   * @param {string} distance - 距离值 (单位 km)
   * @returns {string} 格式化的距离字符串
   */
  function formatKm(distance) {
    const kmStr = Number(distance).toFixed(2);
    return padLeft(kmStr, 8) + " km";
  }

  // ===== 数据格式化 =====
  const mediumTodayLabel = formatLabel("Today");
  const mediumTodayRuns = formatRuns(today.count);
  const mediumTodayKm = formatKm(today.distance);
  
  const mediumWeekLabel = formatLabel("Week");
  const mediumWeekRuns = formatRuns(week.count);
  const mediumWeekKm = formatKm(week.distance);
  
  const mediumMonthLabel = formatLabel("Month");
  const mediumMonthRuns = formatRuns(month.count);
  const mediumMonthKm = formatKm(month.distance);
  
  const mediumYearLabel = formatLabel("Year");
  const mediumYearRuns = formatRuns(year.count);
  const mediumYearKm = formatKm(year.distance);

  // ===== 返回小组件布局结构 =====
  return {
    type: "vstack",           // 竖直堆栈布局
    props: { 
      spacing: 0,
      padding: $insets(spacing.paddingTop, spacing.paddingRight, spacing.paddingBottom, spacing.paddingLeft)
    },
    views: [
      // ===== 标题上方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.titleTopSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 上部标题区 =====
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 0
        },
        views: [{
          type: "text",
          props: {
            text: "Summary",  // 小组件标题
            font: $font(fonts.titleFontFamily, fonts.titleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      
      // ===== 标题和数据之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.topSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 中部数据网格区 =====
      // 使用 vgrid 创建表格布局：3 列分别为 标签、次数、距离
      {
        type: "vgrid",
        props: {
          columns: [
            { fixed: (mediumW - spacing.paddingLeft - spacing.paddingRight) * 0.36 }, // 标签列宽度 36%
            { fixed: (mediumW - spacing.paddingLeft - spacing.paddingRight) * 0.22 }, // 次数列宽度 22%
            { fixed: (mediumW - spacing.paddingLeft - spacing.paddingRight) * 0.42 }  // 距离列宽度 42%
          ],
          spacing: spacing.dataSpacing
        },
        views: [
          // Today 行
          createMediumCell(mediumTodayLabel, "left"), createMediumCell(mediumTodayRuns, "right"), createMediumCell(mediumTodayKm, "right"),
          // Week 行
          createMediumCell(mediumWeekLabel, "left"), createMediumCell(mediumWeekRuns, "right"), createMediumCell(mediumWeekKm, "right"),
          // Month 行
          createMediumCell(mediumMonthLabel, "left"), createMediumCell(mediumMonthRuns, "right"), createMediumCell(mediumMonthKm, "right"),
          // Year 行
          createMediumCell(mediumYearLabel, "left"), createMediumCell(mediumYearRuns, "right"), createMediumCell(mediumYearKm, "right")
        ]
      },
      
      // ===== 数据和时间戳之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.bottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 下部时间戳区 =====
      // 显示最新跑步时间和数据更新时间
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 1
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          }
        ]
      },
      
      // ===== 时间戳下方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.footerBottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}


/**
 * ===== Large 尺寸渲染函数 =====
 * 用于 4x4 的大尺寸小组件
 * 显示完整的统计数据：当前时期 + 上一时期的对比
 * 包括 Today/Yesterday, Week/LastWeek, Month/LastMonth, Year/LastYear
 * 采用颜色区分：当前时期为黑/白，上一时期为绿色
 * 
 * @param {number} largeW - 小组件宽度
 * @param {number} largeH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {Object} yesterday - 昨天的统计数据
 * @param {Object} week - 本周的统计数据
 * @param {Object} lastWeek - 上周的统计数据
 * @param {Object} month - 本月的统计数据
 * @param {Object} lastMonth - 上月的统计数据
 * @param {Object} year - 本年的统计数据
 * @param {Object} lastYear - 去年的统计数据
 * @param {string} latestRunStr - 最新跑步时间戳字符串
 * @param {string} updateStr - 数据更新时间戳字符串
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderLargeWidget(largeW, largeH, today, yesterday, week, lastWeek, month, lastMonth, year, lastYear, latestRunStr, updateStr, isDarkMode) {
  // 使用统一配置
  const fonts = WIDGET_FONTS.large;
  const layout = WIDGET_LAYOUT.large;
  const spacing = WIDGET_SPACING.large;

  /**
   * 创建数据单元格 (文本视图)
   * 支持不同的颜色类型来区分数据类别
   * 
   * @param {string} text - 单元格内容
   * @param {string} align - 对齐方式 ("left" 或 "right")
   * @param {string} colorType - 颜色类型 ("current", "yesterday", "lastWeek" 等)
   * @returns {Object} 文本视图对象
   */
  function createLargeCell(text, align, colorType = "default") {
    let color = $color("#999999"); // 默认灰色
    
    // 根据颜色类型设置不同颜色
    switch (colorType) {
      case "current": // 当前周期 (Today, Week, Month, Year)
        color = isDarkMode ? $color("#FFFFFF") : $color("#000000");
        break;
      case "yesterday": // 上一个时期使用绿色
        color = isDarkMode ? $color("#81C784") : $color("#4CAF50");
        break;
      case "lastWeek":
        color = isDarkMode ? $color("#81C784") : $color("#4CAF50");
        break;
      case "lastMonth":
        color = isDarkMode ? $color("#81C784") : $color("#4CAF50");
        break;
      case "lastYear":
        color = isDarkMode ? $color("#81C784") : $color("#4CAF50");
        break;
    }
    
    return {
      type: "text",
      props: {
        text,
        font: $font(fonts.fontFamily, fonts.gridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing,
        color: color
      }
    };
  }

  /**
   * 左边填充字符串 (使用占位符)
   * 确保数字右对齐
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} str - 输入字符串
   * @param {number} width - 目标宽度
   * @returns {string} 填充后的字符串
   */
  function padLeft(str, width) {
    return str.padStart(width, getPlaceholder(1));
  }
  
  /**
   * 格式化标签 (右边填充)
   * 标签后面填充占位符
   * 占位符类型由 SHOW_PLACEHOLDERS 控制
   * 
   * @param {string} label - 标签名称
   * @returns {string} 格式化后的标签
   */
  function formatLabel(label) {
    return label.padEnd(10, getPlaceholder(1));
  }
  
  /**
   * 格式化跑步次数显示
   * 自动处理单复数形式 (run/runs)
   * 
   * @param {number} count - 跑步次数
   * @returns {string} 格式化的跑步次数字符串
   */
  function formatRuns(count) {
    if (count === 0) {
      return padLeft("0", 3) + " run" + getPlaceholder(1);
    } else if (count === 1) {
      return padLeft("1", 3) + " run" + getPlaceholder(1);
    } else {
      return padLeft(count.toString(), 3) + " runs";
    }
  }
  
  /**
   * 格式化距离显示 (单位: km)
   * 距离显示为两位小数，右对齐
   * 
   * @param {string} distance - 距离值 (单位 km)
   * @returns {string} 格式化的距离字符串
   */
  function formatKm(distance) {
    const kmStr = Number(distance).toFixed(2);
    return padLeft(kmStr, 8) + " km";
  }

  // ===== 数据格式化 =====
  // 当前时期数据
  const largeTodayLabel = formatLabel("Today");
  const largeTodayRuns = formatRuns(today.count);
  const largeTodayKm = formatKm(today.distance);
  
  // 上一时期数据
  const largeYesterdayLabel = formatLabel("Yesterday");
  const largeYesterdayRuns = formatRuns(yesterday.count);
  const largeYesterdayKm = formatKm(yesterday.distance);
  
  const largeWeekLabel = formatLabel("Week");
  const largeWeekRuns = formatRuns(week.count);
  const largeWeekKm = formatKm(week.distance);
  
  const largeLastWeekLabel = formatLabel("Last Week");
  const largeLastWeekRuns = formatRuns(lastWeek.count);
  const largeLastWeekKm = formatKm(lastWeek.distance);
  
  const largeMonthLabel = formatLabel("Month");
  const largeMonthRuns = formatRuns(month.count);
  const largeMonthKm = formatKm(month.distance);
  
  const largeLastMonthLabel = formatLabel("Last Month");
  const largeLastMonthRuns = formatRuns(lastMonth.count);
  const largeLastMonthKm = formatKm(lastMonth.distance);
  
  const largeYearLabel = formatLabel("Year");
  const largeYearRuns = formatRuns(year.count);
  const largeYearKm = formatKm(year.distance);
  
  const largeLastYearLabel = formatLabel("Last Year");
  const largeLastYearRuns = formatRuns(lastYear.count);
  const largeLastYearKm = formatKm(lastYear.distance);

  // ===== 返回小组件布局结构 =====
  return {
    type: "vstack",           // 竖直堆栈布局
    props: { 
      spacing: 0,
      padding: $insets(spacing.paddingTop, spacing.paddingRight, spacing.paddingBottom, spacing.paddingLeft)
    },
    views: [
      // ===== 标题上方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.titleTopSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },

      // ===== 上部标题区 =====
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 0
        },
        views: [{
          type: "text",
          props: {
            text: "Summary",  // 小组件标题
            font: $font(fonts.titleFontFamily, fonts.titleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      
      // ===== 标题和数据之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.topSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 中部数据网格区 =====
      // 使用 vgrid 创建表格布局：3 列分别为 标签、次数、距离
      // 8 行展示：Today + Yesterday, Week + LastWeek, Month + LastMonth, Year + LastYear
      {
        type: "vgrid",
        props: {
          columns: [
            { fixed: (largeW - spacing.paddingLeft - spacing.paddingRight) * 0.36 }, // 标签列宽度 36%
            { fixed: (largeW - spacing.paddingLeft - spacing.paddingRight) * 0.22 }, // 次数列宽度 22%
            { fixed: (largeW - spacing.paddingLeft - spacing.paddingRight) * 0.42 }  // 距离列宽度 42%
          ],
          spacing: spacing.dataSpacing
        },
        views: [
          // Today 行 (黑/白颜色)
          createLargeCell(largeTodayLabel, "left", "current"), createLargeCell(largeTodayRuns, "right", "current"), createLargeCell(largeTodayKm, "right", "current"),
          // Yesterday 行 (绿色)
          createLargeCell(largeYesterdayLabel, "left", "yesterday"), createLargeCell(largeYesterdayRuns, "right", "yesterday"), createLargeCell(largeYesterdayKm, "right", "yesterday"),
          // Week 行 (黑/白颜色)
          createLargeCell(largeWeekLabel, "left", "current"), createLargeCell(largeWeekRuns, "right", "current"), createLargeCell(largeWeekKm, "right", "current"),
          // Last Week 行 (绿色)
          createLargeCell(largeLastWeekLabel, "left", "lastWeek"), createLargeCell(largeLastWeekRuns, "right", "lastWeek"), createLargeCell(largeLastWeekKm, "right", "lastWeek"),
          // Month 行 (黑/白颜色)
          createLargeCell(largeMonthLabel, "left", "current"), createLargeCell(largeMonthRuns, "right", "current"), createLargeCell(largeMonthKm, "right", "current"),
          // Last Month 行 (绿色)
          createLargeCell(largeLastMonthLabel, "left", "lastMonth"), createLargeCell(largeLastMonthRuns, "right", "lastMonth"), createLargeCell(largeLastMonthKm, "right", "lastMonth"),
          // Year 行 (黑/白颜色)
          createLargeCell(largeYearLabel, "left", "current"), createLargeCell(largeYearRuns, "right", "current"), createLargeCell(largeYearKm, "right", "current"),
          // Last Year 行 (绿色)
          createLargeCell(largeLastYearLabel, "left", "lastYear"), createLargeCell(largeLastYearRuns, "right", "lastYear"), createLargeCell(largeLastYearKm, "right", "lastYear")
        ]
      },
      
      // ===== 数据和时间戳之间的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.bottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      // ===== 下部时间戳区 =====
      // 显示最新跑步时间和数据更新时间
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 1
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(fonts.fontFamily, fonts.footerFontSize),
              alignment: $widget.alignment.center
            }
          }
        ]
      },
      
      // ===== 时间戳下方的分隔线 =====
      {
        type: "text",
        props: {
          text: getSeparator(),
          font: $font(fonts.fontFamily, fonts.footerBottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}


/**
 * ===== xLarge 尺寸渲染函数 =====
 * 用于 4x5 及更大的超大尺寸小组件 (iPad 级别)
 * 当前版本为占位符，显示提示信息
 * 待未来版本中实现完整的超大尺寸布局
 * 
 * @param {number} xlargeW - 小组件宽度
 * @param {number} xlargeH - 小组件高度
 * @param {number} family - 小组件家族类型
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderXLargeWidget(xlargeW, xlargeH, family, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.center,  // 居中对齐
      spacing: 12,
      padding: 25,
      // 背景渐变：深色/浅色模式各异
      background: {
        type: "gradient",
        props: {
          // 渐变色设置：深色模式为暗灰渐变，浅色模式为蓝色渐变
          colors: isDarkMode ? ["#1a1a1a", "#2d2d2d"] : ["#e3f2fd", "#bbdefb"],
          startPoint: $point(0, 0),    // 渐变起点
          endPoint: $point(1, 1)       // 渐变终点
        }
      }
    },
    views: [
      // 标题
      {
        type: "text",
        props: {
          text: "📊 xLarge Widget",
          font: $font("bold", 24),
          color: isDarkMode ? $color("white") : $color("#1976d2")
        }
      },
      // 间距分隔
      {
        type: "spacer",
        props: { minLength: 15 }
      },
      // 尺寸信息
      {
        type: "text",
        props: {
          text: `尺寸: ${xlargeW.toFixed(1)} x ${xlargeH.toFixed(1)}`,
          font: $font(22),
          color: isDarkMode ? $color("#cccccc") : $color("#424242")
        }
      },
      // 设备提示
      {
        type: "text",
        props: {
          text: "iPad 超大尺寸",
          font: $font(18),
          color: isDarkMode ? $color("#999999") : $color("#666666")
        }
      },
      // 布局状态提示
      {
        type: "text",
        props: {
          text: "待布局调整",
          font: $font(16),
          color: isDarkMode ? $color("#999999") : $color("#666666")
        }
      }
    ]
  };
}

/**
 * ===== accessoryCircular 渲染函数 =====
 * 用于 1x1 圆形锁屏小组件 (iOS 16+ 锁屏)
 * 显示今天的跑步次数
 * 紧凑的圆形设计，适合锁屏显示
 * 
 * @param {number} circularW - 小组件宽度
 * @param {number} circularH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderAccessoryCircular(circularW, circularH, today, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.center,  // 居中对齐
      spacing: 4,
      padding: 8
    },
    views: [
      // 跑步次数 (大字号)
      {
        type: "text",
        props: {
          text: today.count.toString(),
          font: $font("Menlo-Bold", 20),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000"),
          alignment: $widget.alignment.center
        }
      },
      // 标签 "runs" (小字号)
      {
        type: "text",
        props: {
          text: "runs",
          font: $font("Menlo", 10),
          color: isDarkMode ? $color("#CCCCCC") : $color("#666666"),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}

/**
 * ===== accessoryRectangular 渲染函数 =====
 * 用于 1x2 长方形锁屏小组件 (iOS 16+ 锁屏)
 * 显示今天的跑步次数和距离
 * 横向布局，更容易展示多个数据
 * 
 * @param {number} rectW - 小组件宽度
 * @param {number} rectH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderAccessoryRectangular(rectW, rectH, today, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.leading,  // 左对齐
      spacing: 2,
      padding: $insets(4, 8, 4, 8)
    },
    views: [
      // 第一行：跑步次数
      {
        type: "text",
        props: {
          text: `${today.count} runs`,  // 次数和 "runs" 标签
          font: $font("Menlo-Bold", 12),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000")
        }
      },
      // 第二行：距离
      {
        type: "text",
        props: {
          text: `${today.distance} km`,  // 距离和单位
          font: $font("Menlo", 10),
          color: isDarkMode ? $color("#CCCCCC") : $color("#666666")
        }
      }
    ]
  };
}

/**
 * ===== accessoryInline 渲染函数 =====
 * 用于内联锁屏小组件 (在日期旁边显示的一行信息)
 * 显示跑步emoji、次数和距离
 * 横向排列，占用最小空间
 * 
 * @param {number} inlineW - 小组件宽度
 * @param {number} inlineH - 小组件高度
 * @param {Object} today - 今天的统计数据
 * @param {boolean} isDarkMode - 是否为深色模式
 * @returns {Object} 小组件布局对象
 */
function renderAccessoryInline(inlineW, inlineH, today, isDarkMode) {
  return {
    type: "hstack",
    props: {
      alignment: $widget.alignment.center,  // 垂直居中
      spacing: 8,
      padding: $insets(2, 6, 2, 6)
    },
    views: [
      // 跑步 emoji 图标
      {
        type: "text",
        props: {
          text: "🏃",
          font: $font(14)
        }
      },
      // 数据信息：次数 | 距离
      {
        type: "text",
        props: {
          text: `${today.count} | ${today.distance}km`,  // 次数、竖线分隔符、距离
          font: $font("Menlo", 11),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000")
        }
      }
    ]
  };
}