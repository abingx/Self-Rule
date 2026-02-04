function renderSmallWidget(width, height) {
  return {
    type: "vstack",
    props: {
      padding: 0,
      spacing: 0,
      frame: {
        width: width,
        height: height,
      },
      background: {
        type: "gradient",
        props: {
          colors: [$color("#7788ea"), $color("#bac3fa")],
        },
      },
      border:  { color:  $color("#ee00ba"), width: 1, },
    },
    views: [
      // 标题区
      {
        type: "hstack",
        props: {
          padding: 0,
          spacing: 2,
          frame: {
            width: width - 10 * 2,
            height: (height - 4 * 2) * 0.21,
          },
          border:  { color:  $color("#dfd930"), width: 1, },
        },
        views: [
          {
            type: "text",
            props: {
              text: "Running",
              font: $font("Helvetica-Bold", 15),
              color: $color("#FFFFFF"),
              frame: {
                width: (width - (10+6) * 2) * 0.7 - 2 / 2,
                height: (height - 4 * 2) * 0.21,
                alignment: $widget.alignment.leading,
              },
              border:  { color:  $color("#baee00"), width: 1, },
            },
          },
          {
            type: "text",
            props: {
              text: "🏃‍♂️",
              font: $font("Helvetica-Bold", 15),
              color: $color("#FFFFFF"),
              frame: {
                width: (width - (10+6) * 2) * 0.3 - 2 / 2,
                height: (height - 4 * 2) * 0.21,
                alignment: $widget.alignment.trailing,
              },
              border:  { color:  $color("#ee8700"), width: 1, },
            },
          },
        ],
      },
      // 主数据区
      {
        type: "vstack",
        props: {
          padding: 0,
          spacing: 0,
          frame: {
            width: width - 10 * 2,
            height: (height - 4 * 2) * 0.33,
          },
          border:  { color:  $color("#744c6b"), width: 1, },
        },
        views: [
          {
            type: "text",
            props: {
              text: "Today",
              font: $font("Helvetica-Bold", 10),
              color: $color("#F0F2FF"),
              frame: {
                width: width - (10 + 6) * 2,
                height: (height - 4 * 2) * 0.33 * 0.38,
              },
              border:  { color:  $color("#ff0202"), width: 1, },
            },
          },
          {
            type: "hstack",
            props: {
              padding: 0,
              spacing: 6,
              frame: {
                width: width - (10 + 6) * 2,
                height: (height - 4 * 2) * 0.33 * 0.62,
              },
              alignment: $widget.alignment.bottom,
              border:  { color:  $color("#6c7c87"), width: 1, },
            },
            views: [
              {
                type: "text",
                props: {
                  text: "19.12",
                  font: $font("Helvetica-Bold", 30),
                  color: $color("#ffffff"),
                  frame: {
                    width: (width - (10 + 6) * 2) * 0.7 - 3, //补齐数字和km之间间距
                    height:
                      (height - 4 * 2) *
                      0.33 *
                      0.62,
                    alignment: $widget.alignment.trailing,
                  },
                  border:  { color:  $color("#baee00"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "km",
                  font: $font("Helvetica-Bold", 14),
                  color: $color("#FFFFFF"),
                  frame: {
                    width: (width - 10 * 2) * 0.3- 3, //补齐数字和km之间间距
                    height:
                      (height - 4 * 2) *
                      0.33 *
                      0.62,
                    alignment: $widget.alignment.leading,
                  },
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
        ],
      },
      // 分数据区
      {
        type: "hstack",
        props: {
          frame: {
            width: width - 4 * 2,
            height: (height - 4 * 2) * 0.39,
          },
          spacing: 6,
          border:  { color:  $color("#fcd8f4"), width: 1, },
        },
        views: [
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - 4 * 2 - 6 * 4) / 3,
                height:
                  (height - 4 * 2) *
                  0.39 *
                  0.7,
              },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#8B9AF5")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
              border:  { color:  $color("#059171"), width: 1, },
            },
            views: [
              {
                type: "text",
                props: {
                  text: "WEEK",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#E8EBFF"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "3",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "52.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - 4 * 2 - 6 * 4) / 3,
                height:
                  (height - 4 * 2) *
                  0.39 *
                  0.7,
              },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#8B9AF5")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
              border:  { color:  $color("#059171"), width: 1, },
            },
            views: [
              {
                type: "text",
                props: {
                  text: "MONTH",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#E8EBFF"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "22",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "152.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - 4 * 2 - 6 * 4) / 3,
                height:
                  (height - 4 * 2) *
                  0.39 *
                  0.7,
              },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#8B9AF5")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
              border:  { color:  $color("#059171"), width: 1, },
            },
            views: [
              {
                type: "text",
                props: {
                  text: "YEAR",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#E8EBFF"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "123",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "2152.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
        ],
      },
      // 时间戳区
      {
        type: "hstack",
        props: {
          frame: {
            width: width - 4 * 2 - 12,
            height: (height - 4 * 2) * 0.07,
          },
          spacing: 0,
          border:  { color:  $color("#35854e"), width: 1, },
        },
        views: [
          {
            type: "text",
            props: {
              text: "Latest:2026/02/03 05:12",
              font: $font("Helvetica", 6),
              color: $color("#DEE3FF"),
              frame: {
                width: (width - 4 * 2 - 16) / 2,
                height: (height - 4 * 2) * 0.07,
                alignment: $widget.alignment.leading,
              },
              border:  { color:  $color("green"), width: 1, },
            },
          },
          {
            type: "text",
            props: {
              text: "Update:2026/02/03 12:31",
              font: $font("Helvetica", 6),
              color: $color("#DEE3FF"),
              border:  { color:  $color("green"), width: 1, },
              frame: {
                width: (width - 4 * 2 - 16) / 2,
                height: (height - 4 * 2) * 0.07,
                alignment: $widget.alignment.trailing,
              },
            },
          },
        ],
      },
    ],
  };
}

// 设置时间线
$widget.setTimeline({
  render: (ctx) => {
    const family = ctx.family; // 小组件尺寸类型
    const displaySize = ctx.displaySize; // 显示尺寸 (宽度和高度)
    const isDarkMode = ctx.isDarkMode; // 是否为深色模式
    const widgetWidth = displaySize.width; // 小组件宽度
    const widgetHeight = displaySize.height; // 小组件高度

    console.log(
      "Widget Family:",
      family,
      "Size:",
      widgetWidth,
      "x",
      widgetHeight,
    );

    if (family === 1) {
      // Medium 尺寸
      return {
        type: "text",
        props: {
          text: "Medium Widget\n请使用小尺寸",
          alignment: $widget.alignment.center,
        },
      };
    } else if (family === 2) {
      // Large 尺寸
      return {
        type: "text",
        props: {
          text: "Large Widget\n请使用小尺寸",
          alignment: $widget.alignment.center,
        },
      };
    } else {
      // Small 尺寸 (family === 0) 或其他
      return renderSmallWidget(widgetWidth, widgetHeight);
    }
  },
});
