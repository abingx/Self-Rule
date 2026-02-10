// Large Widget
// 此模块定义了 JSBox 中的跑步统计大尺寸小组件

/**
 * 渲染大型跑步统计组件
 * @param {number} width - 组件宽度
 * @param {number} height - 组件高度
 * @param {boolean} isDarkMode - 设备是否处于深色模式
 * @param {Object} widgetData - 包含跑步统计数据的数据对象
 * @returns {Object} 组件配置对象
 */
function renderLargeWidget(width, height, isDarkMode, widgetData) {
  // 解构组件数据以提取跑步统计数据
  const { today, yesterday, week, lastWeek, month, lastMonth, year, lastYear, latestRunStr, updateStr, getWidgetURL } = widgetData;

  // 根据深色模式设置定义渐变背景色
  const bgColors = isDarkMode
    ? [$color("#5568d3"), $color("#6b4fa0"), $color("#d946ef")]
    : [$color("#667eea"), $color("#764ba2"), $color("#f093fb")];

  // 根据深色模式设置定义文本颜色
  const textTitle = isDarkMode ? $color("#e9ecef") : $color("#ffffff");
  const textLabel = isDarkMode ? $color("#adb5bd") : $color("#ffffff");
  const textValue = isDarkMode ? $color("#ffffff") : $color("#ffffff");
  const textTime = isDarkMode ? $color("#e9ecef") : $color("#ffffff");
  const boxBg = isDarkMode ? [$color("#ffffff")] : [$color("#ffffff")];

  /**
   * 创建单个时期详细数据区（左侧大卡片）
   * @param {string} label - 标签文字（Today/Yesterday）
   * @param {Object} data - 数据对象
   */
  function createDetailCard(label, data) {
    return {
      type: "vstack",
      props: {
        spacing: 0,
        frame: {
          width: (width - 10 * 2 - 10) * 0.4,
          height: ((height - 4 * 2) * 0.72) / 2,
        },
        background: {
          type: "gradient",
          props: {
            colors: boxBg,
            opacity: 0.1,
            cornerRadius: 10,
          },
        },
      },
      views: [
        // 第一排 - 标签
        {
          type: "text",
          props: {
            text: label,
            font: $font("Helvetica-Bold", 10),
            color: textLabel,
            frame: {
              width: (width - 10 * 2 - 10) * 0.4,
              height: ((height - 4 * 2) * 0.72 * 0.15) / 2,
            },
          },
        },
        // 第二排 - 距离显示
        {
          type: "hstack",
          props: {
            spacing: 0,
            frame: {
              width: (width - 10 * 2 - 10) * 0.4,
              height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
            },
            //alignment: $widget.alignment.bottom,
          },
          views: [
            {
              type: "text",
              props: {
                text: Number(data.distance || 0).toFixed(2),
                font: $font("Helvetica-Bold", 28),
                color: textValue,
                frame: {
                  width: (width - 10 * 2 - 10) * 0.4 * 0.54,
                  height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                  alignment: $widget.alignment.center,
                },
                lineLimit: 1,
                minimumScaleFactor: 0.5,
              },
            },
          ],
        },
        // 第三排 - 运动效果标签
        {
          type: "text",
          props: {
            text: data.effect,
            font: $font("Helvetica-Bold", 8),
            color: textValue,
            frame: {
              width: (width - 10 * 2 - 10) * 0.4,
              height: ((height - 4 * 2) * 0.72 * 0.15) / 2,
              alignment: $widget.alignment.center,
            },
          },
        },
        // 第四行 - 详细数据标签
        {
          type: "hstack",
          props: {
            spacing: 0,
            frame: {
              width: (width - 10 * 2 - 10) * 0.4,
              height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
            },
          },
          views: [
            {
              type: "text",
              props: {
                text: "BPM",
                font: $font("Helvetica", 8),
                color: textLabel,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
            {
              type: "text",
              props: {
                text: "Time",
                font: $font("Helvetica", 8),
                color: textLabel,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
            {
              type: "text",
              props: {
                text: "Pace",
                font: $font("Helvetica", 8),
                color: textLabel,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
          ],
        },
        // 第五行 - 详细数据数值
        {
          type: "hstack",
          props: {
            spacing: 0,
            frame: {
              width: (width - 10 * 2 - 10) * 0.4,
              height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
            },
          },
          views: [
            {
              type: "text",
              props: {
                text: data.heartRate ? data.heartRate.toString() : "-",
                font: $font("Helvetica", 8),
                color: textValue,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
            {
              type: "text",
              props: {
                text: data.duration || "-",
                font: $font("Helvetica", 8),
                color: textValue,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
            {
              type: "text",
              props: {
                text: data.pace || "-",
                font: $font("Helvetica", 8),
                color: textValue,
                frame: {
                  width: ((width - 10 * 2 - 10) * 0.4) / 3,
                  height: (((height - 4 * 2) * 0.72 * 0.35) / 2) / 2,
                },
              }
            },
          ],
        },
      ],
    };
  }

  /**
   * 创建统计列（右侧三列之一）
   * @param {string} label - 标签文字（WEEK/MONTH/YEAR/LAST WEEK/LAST MONTH/LAST YEAR）
   * @param {Object} data - 数据对象
   */
  function createStatsColumn(label, data) {
    return {
      type: "vstack",
      props: {
        spacing: 0,
        frame: {
          width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
          height: ((height - 4 * 2) * 0.72) / 2,
        },
        background: {
          type: "gradient",
          props: {
            colors: boxBg,
            opacity: 0.3,
            cornerRadius: 10,
          },
        },
      },
      views: [
        {
          type: "text",
          props: {
            text: label,
            font: $font("Helvetica-Bold", 10),
            color: textLabel,
            frame: {
              width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
              height: ((height - 4 * 2) * 0.72 * 0.15) / 2,
            },
          },
        },
        {
          type: "text",
          props: {
            text: " ",
            font: $font("Helvetica-Bold", 10),
            color: textLabel,
            frame: {
              width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
              height: ((height - 4 * 2) * 0.72 * 0.05) / 2,
            },
          },
        },
        {
          type: "hstack",
          props: {
            spacing: 3,
            frame: {
              width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
              height: ((height - 4 * 2) * 0.72 * 0.8) / 2,
            },
          },
          views: [
            // 左列标签
            {
              type: "vstack",
              props: {
                spacing: 0,
                frame: {
                  width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                  height: ((height - 4 * 2) * 0.72 * 0.8) / 2,
                },
              },
              views: [
                {
                  type: "text",
                  props: {
                    text: "DST",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: "RUN",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: "BPM",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: "PAC",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: "MAX",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: "PR",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
              ],
            },
            // 右列数值
            {
              type: "vstack",
              props: {
                spacing: 0,
                frame: {
                  width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                  height: ((height - 4 * 2) * 0.72 * 0.8) / 2,
                },
              },
              views: [
                {
                  type: "text",
                  props: {
                    text: Number(data.distance || 0).toFixed(2),
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: (data.count || 0).toString(),
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: data.heartRate ? data.heartRate.toString() : "-",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: data.pace || "-",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: data.maxDistance ? Number(data.maxDistance).toFixed(2) : "-",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
                {
                  type: "text",
                  props: {
                    text: data.bestPace || "-",
                    font: $font("Helvetica-Bold", 6),
                    color: textValue,
                    frame: {
                      width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                      height: (((height - 4 * 2) * 0.72 * 0.8) / 6) / 2,
                    },
                  },
                },
              ],
            },
          ],
        },
      ],
    };
  }

  return {
    type: "vstack",
    props: {
      spacing: 0,
      frame: {
        width: width,
        height: height,
      },
      background: {
        type: "gradient",
        props: {
          colors: bgColors,
        },
      },
      widgetURL: getWidgetURL(),
    },
    views: [
      // 标题区
      {
        type: "hstack",
        props: {
          spacing: 0,
          frame: {
            width: width - 10 * 2,
            height: ((height - 4 * 2) * 0.21) / 2,
          },
        },
        views: [
          {
            type: "text",
            props: {
              text: "Running",
              font: $font("Helvetica-Bold", 15),
              color: textTitle,
              frame: {
                width: (width - (10 + 6) * 2) * 0.7,
                height: ((height - 4 * 2) * 0.21) / 2,
                alignment: $widget.alignment.leading,
              },
            },
          },
          {
            type: "text",
            props: {
              text: "🏃‍♂️",
              font: $font("Helvetica-Bold", 15),
              color: textTitle,
              frame: {
                width: (width - (10 + 6) * 2) * 0.3,
                height: ((height - 4 * 2) * 0.21) / 2,
                alignment: $widget.alignment.trailing,
              },
            },
          },
        ],
      },
      // This Turn 标签
      {
        type: "hstack",
        props: {
          frame: {
            width: width - 10 * 2,
            height: ((height - 4 * 2) * 0.28) / 2 / 2,
          },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "This Turn",
              font: $font("Helvetica-Oblique", 12),
              color: textLabel,
              frame: {
                width: width - 10 * 2,
                height: ((height - 4 * 2) * 0.28) / 2 / 2,
                alignment: $widget.alignment.center,
              },
            },
          },
        ],
      },
      // This Turn 数据区
      {
        type: "hstack",
        props: {
          spacing: 0,
          frame: {
            width: width - 10 * 2,
            height: ((height - 4 * 2) * 0.72) / 2,
          },
        },
        views: [
          // 左数据区 - Today详细信息
          createDetailCard("Today", today),
          // 中空白
          {
            type: "text",
            props: {
              text: " ",
              frame: {
                width: 10,
                height: ((height - 4 * 2) * 0.72) / 2,
              },
            },
          },
          // 右数据区 - Week/Month/Year三列统计
          {
            type: "hstack",
            props: {
              spacing: 10,
              frame: {
                width: (width - 10 * 2 - 10) * 0.6,
                height: ((height - 4 * 2) * 0.72) / 2,
              },
            },
            views: [
              createStatsColumn("WEEK", week),
              createStatsColumn("MONTH", month),
              createStatsColumn("YEAR", year),
            ],
          },
        ],
      },
      // Last Turn 标签
      {
        type: "hstack",
        props: {
          frame: {
            width: width - 10 * 2,
            height: ((height - 4 * 2) * 0.28) / 2 / 2,
          },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "Last Turn",
              font: $font("Helvetica-Oblique", 12),
              color: textLabel,
              frame: {
                width: width - 10 * 2,
                height: ((height - 4 * 2) * 0.28) / 2 / 2,
                alignment: $widget.alignment.center,
              },
            },
          },
        ],
      },
      // Last Turn 数据区
      {
        type: "hstack",
        props: {
          spacing: 0,
          frame: {
            width: width - 10 * 2,
            height: ((height - 4 * 2) * 0.72) / 2,
          },
        },
        views: [
          // 左数据区 - Yesterday详细信息
          createDetailCard("Yesterday", yesterday),
          // 中空白
          {
            type: "text",
            props: {
              text: " ",
              frame: {
                width: 10,
                height: ((height - 4 * 2) * 0.72) / 2,
              },
            },
          },
          // 右数据区 - Last Week/Last Month/Last Year三列统计
          {
            type: "hstack",
            props: {
              spacing: 10,
              frame: {
                width: (width - 10 * 2 - 10) * 0.6,
                height: ((height - 4 * 2) * 0.72) / 2,
              },
            },
            views: [
              createStatsColumn("WEEK", lastWeek),
              createStatsColumn("MONTH", lastMonth),
              createStatsColumn("YEAR", lastYear),
            ],
          },
        ],
      },
      // 时间戳区
      {
        type: "hstack",
        props: {
          frame: {
            width: width - 10 * 2 - 10,
            height: ((height - 4 * 2) * 0.07) / 2,
          },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "Latest:" + latestRunStr,
              font: $font("Menlo", 6),
              color: textTime,
              frame: {
                width: (width - 10 * 2 - 10) / 2,
                height: ((height - 4 * 2) * 0.07) / 2,
                alignment: $widget.alignment.leading,
              },
            },
          },
          {
            type: "text",
            props: {
              text: "Update:" + updateStr,
              font: $font("Menlo", 6),
              color: textTime,
              frame: {
                width: (width - 10 * 2 - 10) / 2,
                height: ((height - 4 * 2) * 0.07) / 2,
                alignment: $widget.alignment.trailing,
              },
            },
          },
        ],
      },
    ],
  };
}

// 导出函数以便在其他模块中使用
module.exports = renderLargeWidget;
