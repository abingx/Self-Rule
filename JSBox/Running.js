// JSBox 跑步数据小组件 - 多尺寸自适应版本

const DATA_URL = "https://raw.githubusercontent.com/abingx/running_page/master/src/static/activities.json";

// ===== 工具函数 =====
function parseDate(str) {
  return new Date(str.replace(" ", "T"));
}

function startOfDay(d) {
  const date = new Date(d);
  date.setHours(0, 0, 0, 0);
  return date;
}

function startOfWeek(d) {
  const date = new Date(d);
  const day = date.getDay() || 7;
  if (day !== 1) date.setDate(date.getDate() - (day - 1));
  date.setHours(0, 0, 0, 0);
  return date;
}

function startOfMonth(d) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function startOfYear(d) {
  return new Date(d.getFullYear(), 0, 1);
}

function summarize(list, since) {
  const runs = list.filter(r => parseDate(r.start_date_local) >= since);
  const count = runs.length;
  const distance = runs.reduce((sum, r) => sum + r.distance, 0) / 1000;
  return { count, distance: distance.toFixed(2) };
}

// ===== 主程序 =====
$http.get({
  url: DATA_URL,
  handler: resp => {
    const now = new Date();
    let data = resp.data.filter(r => r.type === "Run");
    
    // 按最新日期排序
    data.sort((a, b) => parseDate(b.start_date_local) - parseDate(a.start_date_local));

    // 统计数据
    const today = summarize(data, startOfDay(now));
    const week = summarize(data, startOfWeek(now));
    const month = summarize(data, startOfMonth(now));
    const year = summarize(data, startOfYear(now));

    // 最新跑步时间
    const latestRunDate = data.length ? parseDate(data[0].start_date_local) : null;
    const latestRunStr = latestRunDate
      ? latestRunDate.toLocaleDateString() + " " + latestRunDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      : "N/A";
    
    // 更新时间
    const updateStr = now.toLocaleDateString() + " " + now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    // 设置时间线
    $widget.setTimeline({
      render: ctx => {
        const family = ctx.family;
        const displaySize = ctx.displaySize;
        const isDarkMode = ctx.isDarkMode;
        const widgetWidth = displaySize.width;
        const widgetHeight = displaySize.height;

        console.log("Widget Family:", family, "Size:", widgetWidth, "x", widgetHeight);

        // 根据不同尺寸返回不同的布局
        if (family === 1) {
          return renderMediumWidget(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode);
        } else if (family === 0) {
          return renderSmallWidget(widgetWidth, widgetHeight, today, week, month, year, latestRunStr, updateStr, isDarkMode);
        } else if (family === 2) {
          return renderLargeWidget(widgetWidth, widgetHeight, family, isDarkMode);
        } else if (family === 3) {
          return renderXLargeWidget(widgetWidth, widgetHeight, family, isDarkMode);
        }
      },
      policy: {
        afterDate: new Date(now.getTime() + 6 * 60 * 60 * 1000)
      }
    });
  }
});

// ===== Medium 尺寸渲染函数(原 Running 内容)=====
function renderMediumWidget(mediumW, mediumH, today, week, month, year, latestRunStr, updateStr, isDarkMode) {
  const mediumFontFamily = "Menlo";
  const mediumTitleFontFamily = "Menlo-Bold";
  const mediumTitleFontSize = 22;
  const mediumGridFontSize = 14;
  const mediumFooterFontSize = 10;
  
  const mediumTopHeightRatio = 0.25;
  const mediumMiddleHeightRatio = 0.55;
  const mediumBottomHeightRatio = 0.20;

  function createMediumCell(text, align) {
    return {
      type: "text",
      props: {
        text,
        font: $font(mediumFontFamily, mediumGridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing
      }
    };
  }

  function padLeft(str, width) {
    return str.padStart(width, " ");
  }
  
  function formatLabel(label) {
    return label.padEnd(5, " ");
  }
  
  function formatRuns(count) {
    if (count === 0) return "         ";
    return padLeft(count.toString(), 3) + " runs";
  }
  
  function formatKm(distance) {
    const kmStr = Number(distance).toFixed(2);
    return padLeft(kmStr, 7) + " km";
  }

  const mediumTodayLabel = formatLabel("Today");
  const mediumTodayRuns = formatRuns(0);
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

  return {
    type: "vstack",
    props: { spacing: 0 },
    views: [
      // 上部标题
      {
        type: "vstack",
        props: {
          frame: { height: mediumH * mediumTopHeightRatio },
          alignment: $widget.horizontalAlignment.center
        },
        views: [{
          type: "text",
          props: {
            text: "Summary 2026",
            font: $font(mediumTitleFontFamily, mediumTitleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      // 中部数据网格
      {
        type: "vgrid",
        props: {
          frame: { height: mediumH * mediumMiddleHeightRatio },
          columns: [
            { fixed: mediumW * 0.36 },
            { fixed: mediumW * 0.22 },
            { fixed: mediumW * 0.42 }
          ],
          spacing: 1  // 数据部分行间距
        },
        views: [
          createMediumCell(mediumTodayLabel, "left"), createMediumCell(mediumTodayRuns, "right"), createMediumCell(mediumTodayKm, "right"),
          createMediumCell(mediumWeekLabel, "left"), createMediumCell(mediumWeekRuns, "right"), createMediumCell(mediumWeekKm, "right"),
          createMediumCell(mediumMonthLabel, "left"), createMediumCell(mediumMonthRuns, "right"), createMediumCell(mediumMonthKm, "right"),
          createMediumCell(mediumYearLabel, "left"), createMediumCell(mediumYearRuns, "right"), createMediumCell(mediumYearKm, "right")
        ]
      },
      // 下部时间戳
      {
        type: "vstack",
        props: {
          frame: { height: mediumH * mediumBottomHeightRatio },
          alignment: $widget.horizontalAlignment.trailing
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(mediumFontFamily, mediumFooterFontSize),
              alignment: $widget.alignment.trailing
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(mediumFontFamily, mediumFooterFontSize),
              alignment: $widget.alignment.trailing
            }
          }
        ]
      }
    ]
  };
}

// ===== Small 尺寸渲染函数(2列布局,不显示runs)=====
function renderSmallWidget(smallW, smallH, today, week, month, year, latestRunStr, updateStr, isDarkMode) {
  const smallFontFamily = "Menlo";
  const smallTitleFontFamily = "Menlo-Bold";
  const smallTitleFontSize = 18;
  const smallGridFontSize = 12;
  const smallFooterFontSize = 8;
  
  const smallTopHeightRatio = 0.25;
  const smallMiddleHeightRatio = 0.55;
  const smallBottomHeightRatio = 0.20;

  function createSmallCell(text, align) {
    return {
      type: "text",
      props: {
        text,
        font: $font(smallFontFamily, smallGridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing
      }
    };
  }

  function padLeft(str, width) {
    return str.padStart(width, " ");
  }
  
  function formatLabel(label) {
    return label.padEnd(5, " ");
  }
  
  function formatKm(distance) {
    const kmStr = Number(distance).toFixed(2);
    return padLeft(kmStr, 7) + " km";
  }

  const smallTodayLabel = formatLabel("Today");
  const smallTodayKm = formatKm(today.distance);
  
  const smallWeekLabel = formatLabel("Week");
  const smallWeekKm = formatKm(week.distance);
  
  const smallMonthLabel = formatLabel("Month");
  const smallMonthKm = formatKm(month.distance);
  
  const smallYearLabel = formatLabel("Year");
  const smallYearKm = formatKm(year.distance);

  return {
    type: "vstack",
    props: { spacing: 0 },
    views: [
      // 上部标题
      {
        type: "vstack",
        props: {
          frame: { height: smallH * smallTopHeightRatio },
          alignment: $widget.horizontalAlignment.center
        },
        views: [{
          type: "text",
          props: {
            text: "Summary",
            font: $font(smallTitleFontFamily, smallTitleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      // 中部数据网格(2列:label + distance)
      {
        type: "vgrid",
        props: {
          frame: { height: smallH * smallMiddleHeightRatio },
          columns: [
            { fixed: smallW * 0.40 },
            { fixed: smallW * 0.60 }
          ],
          spacing: 4  // 数据部分行间距
        },
        views: [
          createSmallCell(smallTodayLabel, "left"), createSmallCell(smallTodayKm, "right"),
          createSmallCell(smallWeekLabel, "left"), createSmallCell(smallWeekKm, "right"),
          createSmallCell(smallMonthLabel, "left"), createSmallCell(smallMonthKm, "right"),
          createSmallCell(smallYearLabel, "left"), createSmallCell(smallYearKm, "right")
        ]
      },
      // 下部时间戳
      {
        type: "vstack",
        props: {
          frame: { height: smallH * smallBottomHeightRatio },
          alignment: $widget.horizontalAlignment.trailing
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(smallFontFamily, smallFooterFontSize),
              alignment: $widget.alignment.trailing
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(smallFontFamily, smallFooterFontSize),
              alignment: $widget.alignment.trailing
            }
          }
        ]
      }
    ]
  };
}

// ===== Large 尺寸渲染函数(待调整)=====
function renderLargeWidget(largeW, largeH, family, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.center,
      spacing: 10,
      padding: 20,
      background: {
        type: "gradient",
        props: {
          colors: isDarkMode ? ["#1a1a1a", "#2d2d2d"] : ["#e3f2fd", "#bbdefb"],
          startPoint: $point(0, 0),
          endPoint: $point(1, 1)
        }
      }
    },
    views: [
      {
        type: "text",
        props: {
          text: "📊 Large Widget",
          font: $font("bold", 22),
          color: isDarkMode ? $color("white") : $color("#1976d2")
        }
      },
      {
        type: "spacer",
        props: { minLength: 10 }
      },
      {
        type: "text",
        props: {
          text: `尺寸: ${largeW.toFixed(1)} x ${largeH.toFixed(1)}`,
          font: $font(20),
          color: isDarkMode ? $color("#cccccc") : $color("#424242")
        }
      },
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

// ===== xLarge 尺寸渲染函数(待调整)=====
function renderXLargeWidget(xlargeW, xlargeH, family, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.center,
      spacing: 12,
      padding: 25,
      background: {
        type: "gradient",
        props: {
          colors: isDarkMode ? ["#1a1a1a", "#2d2d2d"] : ["#e3f2fd", "#bbdefb"],
          startPoint: $point(0, 0),
          endPoint: $point(1, 1)
        }
      }
    },
    views: [
      {
        type: "text",
        props: {
          text: "📊 xLarge Widget",
          font: $font("bold", 24),
          color: isDarkMode ? $color("white") : $color("#1976d2")
        }
      },
      {
        type: "spacer",
        props: { minLength: 15 }
      },
      {
        type: "text",
        props: {
          text: `尺寸: ${xlargeW.toFixed(1)} x ${xlargeH.toFixed(1)}`,
          font: $font(22),
          color: isDarkMode ? $color("#cccccc") : $color("#424242")
        }
      },
      {
        type: "text",
        props: {
          text: "iPad 超大尺寸",
          font: $font(18),
          color: isDarkMode ? $color("#999999") : $color("#666666")
        }
      },
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