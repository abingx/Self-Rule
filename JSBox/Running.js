// 强制中等尺寸
$widget.family = $widgetFamily.medium;
//小组件小尺寸   small：164*164
//小组件中等尺寸 medium：164*342
//小组件大尺寸   large：344*344
//小组件超大尺寸      ：540*360（iPadOS）
//试用后再调整

const size = $widget.displaySize;
const W = size.width;
const H = size.height;

// ===== 布局配置 =====
// 字体设置
const FONT_FAMILY = "Menlo";
const TITLE_FONT_SIZE = 22;      // 标题字体大小
const GRID_FONT_SIZE = 14;       // 网格数据字体大小
const FOOTER_FONT_SIZE = 10;     // 底部时间字体大小

// 高度占比
const TOP_HEIGHT_RATIO = 0.25;    // 上部标题区域
const MIDDLE_HEIGHT_RATIO = 0.55; // 中部数据网格区域
const BOTTOM_HEIGHT_RATIO = 0.20; // 下部时间戳区域

const DATA_URL =
  "https://raw.githubusercontent.com/abingx/running_page/master/src/static/activities.json";

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

function cell(text, align) {
  return {
    type: "text",
    props: {
      text,
      font: $font(FONT_FAMILY, GRID_FONT_SIZE),
      frame: {
        maxWidth: Infinity
      },
      alignment:
        align === "left"
          ? $widget.alignment.leading
          : $widget.alignment.trailing
    }
  };
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

    // 格式化显示（补足空格确保对齐）
    function padLeft(str, width) {
      return str.padStart(width, " ");
    }
    
    function formatLabel(label) {
      return label.padEnd(5, " "); // Today/Week/Month/Year 最长5位
    }
    
    function formatRuns(count) {
      if (count === 0) return "         "; // 9个空格 (3位数字+空格+runs)
      return padLeft(count.toString(), 3) + " runs";
    }
    
    function formatKm(distance) {
      const kmStr = Number(distance).toFixed(2);
      return padLeft(kmStr, 7) + " km"; // 最大4位整数+小数点+2位小数=7位
    }

    const todayLabel = formatLabel("Today");
    const todayRuns = formatRuns(0); // Today 不显示次数
    const todayKm = formatKm(today.distance);
    
    const weekLabel = formatLabel("Week");
    const weekRuns = formatRuns(week.count);
    const weekKm = formatKm(week.distance);
    
    const monthLabel = formatLabel("Month");
    const monthRuns = formatRuns(month.count);
    const monthKm = formatKm(month.distance);
    
    const yearLabel = formatLabel("Year");
    const yearRuns = formatRuns(year.count);
    const yearKm = formatKm(year.distance);

    $widget.setTimeline({
      render: () => ({
        type: "vstack",
        props: {
          spacing: 0
        },
        views: [
          // ===== 上 25% =====
          {
            type: "vstack",
            props: {
              frame: {
                height: H * TOP_HEIGHT_RATIO
              },
              alignment: $widget.horizontalAlignment.center
            },
            views: [
              {
                type: "text",
                props: {
                  text: "Running Summary 2026",
                  font: $font(FONT_FAMILY, TITLE_FONT_SIZE),
                  alignment: $widget.alignment.center
                }
              }
            ]
          },

          // ===== 中 60%（3×4 横向网格）=====
          {
            type: "vgrid",
            props: {
              frame: { height: H * MIDDLE_HEIGHT_RATIO },
              columns: [
                { fixed: W * 0.36 }, // label
                { fixed: W * 0.22 }, // runs
                { fixed: W * 0.42 }  // distance
              ]
            },
            views: [
              cell(todayLabel, "left"),
              cell(todayRuns, "right"),
              cell(todayKm, "right"),

              cell(weekLabel, "left"),
              cell(weekRuns, "right"),
              cell(weekKm, "right"),

              cell(monthLabel, "left"),
              cell(monthRuns, "right"),
              cell(monthKm, "right"),

              cell(yearLabel, "left"),
              cell(yearRuns, "right"),
              cell(yearKm, "right")
            ]
          },

          // ===== 下 15% =====
          {
            type: "vstack",
            props: {
              frame: {
                height: H * BOTTOM_HEIGHT_RATIO
              },
              alignment: $widget.horizontalAlignment.trailing
            },
            views: [
              {
                type: "text",
                props: {
                  text: `Latest: ${latestRunStr}`,
                  font: $font(FONT_FAMILY, FOOTER_FONT_SIZE),
                  alignment: $widget.alignment.trailing
                }
              },
              {
                type: "text",
                props: {
                  text: `Update: ${updateStr}`,
                  font: $font(FONT_FAMILY, FOOTER_FONT_SIZE),
                  alignment: $widget.alignment.trailing
                }
              }
            ]
          }
        ]
      }),
      policy: {
        // 每 6 小时刷新一次
        afterDate: new Date(now.getTime() + 6 * 60 * 60 * 1000)
      }
    });
  }
});