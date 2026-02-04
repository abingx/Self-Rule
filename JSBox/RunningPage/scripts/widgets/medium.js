// Small Widget

const utils = require("../utils");

function renderMediumWidget(width, height, isDarkMode, widgetData) {
  const { today, week, month, year, latestRunStr, updateStr, getWidgetURL } = widgetData;
  // 背景色
  const bgColors = isDarkMode
    ? [$color("#5568d3"), $color("#6b4fa0"), $color("#d946ef")]
    : [$color("#667eea"), $color("#764ba2"), $color("#f093fb")];
  // 文字色
  const textTitle = isDarkMode ? $color("#e9ecef") : $color("#ffffff");
  const textLabel = isDarkMode ? $color("#adb5bd") : $color("#ffffff");
  const textValue = isDarkMode ? $color("#ffffff") : $color("#ffffff");
  const textTime = isDarkMode ? $color("#e9ecef") : $color("#ffffff");
  const boxBg = isDarkMode ? [$color("#ffffff")] : [$color("#ffffff")];

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
      //border:  { color:  $color("#ee00ba"), width: 1, },
    },
    views: [
      // 标题区
      {
        type: "hstack",
        props: {
          spacing: 2,
          frame: {
            width: width - 10 * 2,
            height: (height - 4 * 2) * 0.21,
          },
          //border:  { color:  $color("#dfd930"), width: 1, },
        },
        views: [
          {
            type: "text",
            props: {
              text: "Running",
              font: $font("Helvetica-Bold", 15),
              color: textTitle,
              frame: {
                width: (width - (10 + 6) * 2) * 0.7 - 2 / 2,
                height: (height - 4 * 2) * 0.21,
                alignment: $widget.alignment.leading,
              },
              //border:  { color:  $color("#baee00"), width: 1, },
            },
          },
          {
            type: "text",
            props: {
              text: "🏃‍♂️",
              font: $font("Helvetica-Bold", 15),
              color: textTitle,
              frame: {
                width: (width - (10 + 6) * 2) * 0.3 - 2 / 2,
                height: (height - 4 * 2) * 0.21,
                alignment: $widget.alignment.trailing,
              },
              //border:  { color:  $color("#ee8700"), width: 1, },
            },
          },
        ],
      },
      // 数据区
      {
        type: "hstack",
        props: {
          spacing: 10,
          frame: {
            width: width - 10 * 2,
            height: (height - 4 * 2) * 0.72,
          },
          //border:  { color:  $color("#fcd8f4"), width: 1, },
        },
        views: [
          {
            type: "vstack",
            props: {
              spacing: 10,
              frame: {
                width: (width - 10 * 2 - 10 * 1) * 0.4,
                height: (height - 4 * 2) * 0.72,
              },
              background: {
                type: "gradient",
                props: {
                  colors: boxBg,
                  opacity: 0.3,
                  cornerRadius: 6,
                },
              },
              //border:  { color:  $color("#059171"), width: 1, },
            },
            views: [
              {
                type: "text",
                props: {
                  text: "TODAY",
                  font: $font("Helvetica-Bold", 15),
                  color: textLabel,
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: today.count.toString(),
                  font: $font("Helvetica-Bold", 15),
                  color: textValue,
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
              {
                type: "text",
                props: {
                  text: Number(today.distance).toFixed(2),
                  font: $font("Helvetica-Bold", 15),
                  color: textValue,
                  //border:  { color:  $color("#ee8700"), width: 1, },
                },
              },
            ],
          },
          {
            type: "vstack",
            props: {
              spacing: 3,
              frame: {
                width: (width - 10 * 2 - 10 * 1) * 0.6,
                height: (height - 4 * 2) * 0.72,
              },
              //border:  { color:  $color("#059171"), width: 1, },
            },
            views: [
              {
                type: "hstack",
                props: {
                  spacing: 20,
                  frame: {
                    width: (width - 10 * 2 - 10 * 1) * 0.6,
                    height: ((height - 4 * 2) * 0.72 - 3 * 2)/ 3,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 6,
                    },
                  },
                  //border:  { color:  $color("#e8f3f0"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "WEEK",
                      font: $font("Helvetica-Bold", 15),
                      color: textLabel,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: week.count.toString(),
                      font: $font("Helvetica-Bold", 15),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: Number(week.distance).toFixed(2),
                      font: $font("Helvetica-Bold", 15),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                ],
              },
              {
                type: "hstack",
                props: {
                  spacing: 20,
                  frame: {
                    width: (width - 10 * 2 - 10 * 1) * 0.6,
                    height: ((height - 4 * 2) * 0.72 - 3 * 2)/ 3,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 6,
                    },
                  },
                  //border:  { color:  $color("#059171"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "MONTH",
                      font: $font("Helvetica-Bold", 15),
                      color: textLabel,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: month.count.toString(),
                      font: $font("Helvetica-Bold", 15),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: Number(month.distance).toFixed(2),
                      font: $font("Helvetica-Bold", 8),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                ],
              },
              {
                type: "hstack",
                props: {
                  spacing: 20,
                  frame: {
                    width: (width - 10 * 2 - 10 * 1) * 0.6,
                    height: ((height - 4 * 2) * 0.72 - 3 * 2)/ 3,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 6,
                    },
                  },
                  //border:  { color:  $color("#059171"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "YEAR",
                      font: $font("Helvetica-Bold", 15),
                      color: textLabel,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: year.count.toString(),
                      font: $font("Helvetica-Bold", 15),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: Number(year.distance).toFixed(2),
                      font: $font("Helvetica-Bold", 15),
                      color: textValue,
                      //border:  { color:  $color("#ee8700"), width: 1, },
                    },
                  },
                ],
              },
            ],
          },
        ],
      },
      // 时间戳区
      {
        type: "hstack",
        props: {
          spacing: 0,
          frame: {
            width: width - 10 * 2 - 10,
            height: (height - 4 * 2) * 0.07,
          },
          //border:  { color:  $color("#35854e"), width: 1, },
        },
        views: [
          {
            type: "text",
            props: {
              text: latestRunStr,
              font: $font("Menlo", 6),
              color: textTime,
              frame: {
                width: (width - 10 * 2 - 10) / 2,
                height: (height - 4 * 2) * 0.07,
                alignment: $widget.alignment.leading,
              },
              //border:  { color:  $color("green"), width: 1, },
            },
          },
          {
            type: "text",
            props: {
              text: updateStr,
              font: $font("Menlo", 6),
              color: textTime,
              frame: {
                width: (width - 10 * 2 - 10) / 2,
                height: (height - 4 * 2) * 0.07,
                alignment: $widget.alignment.trailing,
              },
              //border:  { color:  $color("green"), width: 1, },
            },
          },
        ],
      },
    ],
  };
}

module.exports = renderMediumWidget;