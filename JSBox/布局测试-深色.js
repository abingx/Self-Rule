const WIDGET_SPACING = {
  small: {
    Padding: 4, // 边距
    Spacing: 0, // 行距
  },
};

const WIDGET_LAYOUT = {
  small: {
    titleHeightRatio: 0.21, // 标题区占总高度的 25%
    firstHeightRatio: 0.33, // 主数据区占总高度的 55%
    secondHeightRatio: 0.39, // 分数据区占总高度的 55%
    dateHeightRatio: 0.07, // 时间戳区占总高度的 20%
  },
};

function renderSmallWidget(width, height) {
  const layout = WIDGET_LAYOUT.small;
  const spacing = WIDGET_SPACING.small;
  return {
    type: "vstack",
    props: {
      frame: {
        width: width,
        height: height,
      },
      //border:  { color:  $color("#ee00ba"), width: 1, },
      background: {
        type: "gradient",
        props: {
          colors: [$color("#677CE6", "#6C6ED3"), $color("#776ECB", "#6D4A9D")],
        },
      },
      spacing: spacing.Spacing,
    },
    views: [
      // 标题区
      {
        type: "hstack",
        props: {
          frame: {
            width: width - spacing.Padding * 2 - 12,
            height: (width - spacing.Padding * 2) * layout.titleHeightRatio,
          },
          //border:  { color:  $color("#6c7c87"), width: 1, },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "Running",
              font: $font("Helvetica-Bold", 15),
              color: $color("#d7d7d7"),
              //border:  { color:  $color("#baee00"), width: 1, },
              frame: {
                width: (width - spacing.Padding * 2 - 12) * 0.7,
                height: (width - spacing.Padding * 2) * layout.titleHeightRatio,
                alignment: $widget.alignment.leading,
              },
            },
          },
          {
            type: "text",
            props: {
              text: "🏃‍♂️",
              font: $font("Helvetica-Bold", 15),
              color: $color("#d7d7d7"),
              //border:  { color:  $color("#ee8700"), width: 1, },
              frame: {
                width: (width - spacing.Padding * 2 - 12) * 0.3,
                height: (width - spacing.Padding * 2) * layout.titleHeightRatio,
                alignment: $widget.alignment.trailing,
              },
            },
          },
        ],
      },
      // 主数据区
      {
        type: "vstack",
        props: {
          frame: {
            width: width - spacing.Padding * 2,
            height: (height - spacing.Padding * 2) * layout.firstHeightRatio,
          },
          //border:  { color:  $color("#744c6b"), width: 1, },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "Today",
              font: $font("Helvetica-Bold", 10),
              color: $color("#d7d7d7"),
              //border:  { color:  $color("#ff0202"), width: 1, },
              frame: {
                width: width - spacing.Padding * 2,
                height:
                  (height - spacing.Padding * 2) *
                  layout.firstHeightRatio *
                  0.38,
              },
              spacing: 0,
            },
          },
          {
            type: "hstack",
            props: {
              frame: {
                width: width - spacing.Padding * 2,
                height:
                  (height - spacing.Padding * 2) *
                  layout.firstHeightRatio *
                  0.62,
              },
              //border:  { color:  $color("#6c7c87"), width: 1, },
              spacing: 6,
              alignment: $widget.alignment.bottom,
            },
            views: [
              {
                type: "text",
                props: {
                  text: "19.12",
                  font: $font("Helvetica-Bold", 30),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#baee00"), width: 1, },
                  frame: {
                    width: (width - spacing.Padding * 2) * 0.7 - 12,
                    height:
                      (height - spacing.Padding * 2) *
                      layout.firstHeightRatio *
                      0.62,
                    alignment: $widget.alignment.trailing,
                  },
                },
              },
              {
                type: "text",
                props: {
                  text: "km",
                  font: $font("Helvetica-Bold", 14),
                  color: $color("#d7d7d7"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                  frame: {
                    width: (width - spacing.Padding * 2) * 0.3 - 12,
                    height:
                      (height - spacing.Padding * 2) *
                      layout.firstHeightRatio *
                      0.62,
                    alignment: $widget.alignment.leading,
                  },
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
            width: width - spacing.Padding * 2,
            height: (height - spacing.Padding * 2) * layout.secondHeightRatio,
          },
          //border:  { color:  $color("#fcd8f4"), width: 1, },
          spacing: 6,
        },
        views: [
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - spacing.Padding * 2 - 6 * 4) / 3,
                height:
                  (height - spacing.Padding * 2) *
                  layout.secondHeightRatio *
                  0.7,
              },
              //border:  { color:  $color("#059171"), width: 1, },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#ffffff")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
            },
            views: [
              {
                type: "text",
                props: {
                  text: "WEEK",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#d7d7d7"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "3",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "52.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - spacing.Padding * 2 - 6 * 4) / 3,
                height:
                  (height - spacing.Padding * 2) *
                  layout.secondHeightRatio *
                  0.7,
              },
              //border:  { color:  $color("#059171"), width: 1, },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#ffffff")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
            },
            views: [
              {
                type: "text",
                props: {
                  text: "MONTH",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#d7d7d7"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "22",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "152.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
          {
            type: "vstack",
            props: {
              frame: {
                width: (width - spacing.Padding * 2 - 6 * 4) / 3,
                height:
                  (height - spacing.Padding * 2) *
                  layout.secondHeightRatio *
                  0.7,
              },
              //border:  { color:  $color("#059171"), width: 1, },
              background: {
                type: "gradient",
                props: {
                  colors: [$color("#ffffff")],
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              spacing: 3,
            },
            views: [
              {
                type: "text",
                props: {
                  text: "YEAR",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#d7d7d7"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "123",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: "2152.23",
                  font: $font("Helvetica-Bold", 8),
                  color: $color("#ffffff"),
                  //border:  { color:  $color("#ee8700"), width: 1, },
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
            width: width - spacing.Padding * 2 - 12,
            height: (height - spacing.Padding * 2) * layout.dateHeightRatio,
          },
          //border:  { color:  $color("#35854e"), width: 1, },
          spacing: 0,
        },
        views: [
          {
            type: "text",
            props: {
              text: "Latest:2026/02/03 05:12",
              font: $font("Helvetica", 6),
              color: $color("#ffffff"),
              //border:  { color:  $color("green"), width: 1, },
              frame: {
                width: (width - spacing.Padding * 2 - 16) / 2,
                height: (height - spacing.Padding * 2) * layout.dateHeightRatio,
                alignment: $widget.alignment.leading,
              },
            },
          },
          {
            type: "text",
            props: {
              text: "Update:2026/02/03 12:31",
              font: $font("Helvetica", 6),
              color: $color("#ffffff"),
              //border:  { color:  $color("green"), width: 1, },
              frame: {
                width: (width - spacing.Padding * 2 - 16) / 2,
                height: (height - spacing.Padding * 2) * layout.dateHeightRatio,
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
