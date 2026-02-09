// Medium Widget
// 此模块定义了 JSBox 中的跑步统计中等尺寸小组件

const utils = require("../utils");

/**
 * 渲染中型跑步统计组件
 * @param {number} width - 组件宽度
 * @param {number} height - 组件高度
 * @param {boolean} isDarkMode - 设备是否处于深色模式
 * @param {Object} widgetData - 包含跑步统计数据的数据对象
 * @returns {Object} 组件配置对象
 */
function renderMediumWidget(width, height, isDarkMode, widgetData) {
  // 解构组件数据以提取跑步统计数据
  const { today, week, month, year, latestRunStr, updateStr, getWidgetURL } = widgetData;

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
          spacing: 0,
          frame: {
            width: width - 10 * 2,
            height: (height - 4 * 2) * 0.72,
          },
          //border:  { color:  $color("#dfd930"), width: 1, },
        },
        views: [
          // 左数据区 - Today详细信息
          {
            type: "vstack",
            props: {
              spacing: 0,
              frame: {
                width: (width - 10 * 2 - 10) * 0.4,
                height: (height - 4 * 2) * 0.72,
              },
              background: {
                type: "gradient",
                props: {
                  colors: boxBg,
                  opacity: 0.1,
                  cornerRadius: 10,
                },
              },
              //border:  { color:  $color("#30df4a"), width: 1, },
            },
            views: [
              // 第一排 - Today标签
              {
                type: "text",
                props: {
                  text: "Today",
                  font: $font("Helvetica-Bold", 10),
                  color: textLabel,
                  frame: {
                    width: (width - 10 * 2 - 10) * 0.4,
                    height: (height - 4 * 2) * 0.72 * 0.15,
                  },
                  //border: { color: $color("#ff0202"), width: 1, },
                },
              },
              // 第二排 - 距离显示
              {
                type: "hstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: (width - 10 * 2 - 10) * 0.4,
                    height: (height - 4 * 2) * 0.72 * 0.35,
                  },
                  alignment: $widget.alignment.bottom,
                  //border: { color: $color("#6c7c87"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: " ",
                      font: $font("Helvetica-Bold", 14),
                      color: textValue,
                      frame: {
                        width: (width - 10 * 2 - 10) * 0.4 * 0.23,
                        height: (height - 4 * 2) * 0.72 * 0.35,
                        alignment: $widget.alignment.center,
                      },
                      //border: { color: $color("#ee8700"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: Number(today.distance || 0).toFixed(2),
                      font: $font("Helvetica-Bold", 28),
                      color: textValue,
                      frame: {
                        width: (width - 10 * 2 - 10) * 0.4 * 0.54,
                        height: (height - 4 * 2) * 0.72 * 0.35,
                        alignment: $widget.alignment.center,
                      },
                      minimumScaleFactor: 0.5,
                      //border: { color: $color("#baee00"), width: 1, },
                    },
                  },
                  {
                    type: "text",
                    props: {
                      text: "km",
                      font: $font("Helvetica-Bold", 14),
                      color: textValue,
                      frame: {
                        width: (width - 10 * 2 - 10) * 0.4 * 0.23,
                        height: (height - 4 * 2) * 0.72 * 0.35,
                        alignment: $widget.alignment.center,
                      },
                      //border: { color: $color("#ee8700"), width: 1, },
                    },
                  },
                ],
              },
              // 第三排 - 运动效果标签（待数据补充）
              {
                type: "text",
                props: {
                  text: today.effect || "有氧效果",
                  font: $font("Helvetica-Bold", 6),
                  color: textValue,
                  frame: {
                    width: (width - 10 * 2 - 10) * 0.4,
                    height: (height - 4 * 2) * 0.72 * 0.15,
                    alignment: $widget.alignment.center,
                  },
                  //border: { color: $color("#ee8700"), width: 1, },
                },
              },
              // 第四行 - 详细数据标签
              {
                type: "hstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: (width - 10 * 2 - 10) * 0.4,
                    height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                  },
                  //border: { color: $color("#5f3f3f"), width: 1, },
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
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
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
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
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
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
                    }
                  },
                ],
              },
              // 第五行 - 详细数据数值（待数据补充）
              {
                type: "hstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: (width - 10 * 2 - 10) * 0.4,
                    height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                  },
                  //border: { color: $color("#5f3f3f"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: today.heartRate ? today.heartRate.toString() : "-",
                      font: $font("Helvetica", 8),
                      color: textValue,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.4) / 3,
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
                    }
                  },
                  {
                    type: "text",
                    props: {
                      text: today.duration || "-",
                      font: $font("Helvetica", 8),
                      color: textValue,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.4) / 3,
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
                    }
                  },
                  {
                    type: "text",
                    props: {
                      text: today.pace || "-",
                      font: $font("Helvetica", 8),
                      color: textValue,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.4) / 3,
                        height: ((height - 4 * 2) * 0.72 * 0.35) / 2,
                      },
                      //border: { color: $color("#5f3f3f"), width: 1, },
                    }
                  },
                ],
              },
            ],
          },
          // 中空白
          {
            type: "text",
            props: {
              text: " ",
              frame: {
                width: 10,
                height: (height - 4 * 2) * 0.72,
              },
              //border: { color: $color("#baee00"), width: 1, },
            },
          },
          // 右数据区 - Week/Month/Year三列详细统计
          {
            type: "hstack",
            props: {
              spacing: 10,
              frame: {
                width: (width - 10 * 2 - 10) * 0.6,
                height: (height - 4 * 2) * 0.72,
              },
              //border:  { color:  $color("#304adf"), width: 1, },
            },
            views: [
              // 第一列 WEEK
              {
                type: "vstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                    height: (height - 4 * 2) * 0.72,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 10,
                    },
                  },
                  //border: { color: $color("#30df4a"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "WEEK",
                      font: $font("Helvetica-Bold", 10),
                      color: textLabel,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.15,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
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
                        height: (height - 4 * 2) * 0.72 * 0.05,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
                    },
                  },
                  {
                    type: "hstack",
                    props: {
                      spacing: 3,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.8,
                      },
                      //border:  { color:  $color("#30df4a"), width: 1, },
                    },
                    views:[
                      // 左列标签
                      {
                        type: "vstack",
                        props: {
                          spacing: 0,
                          frame: {
                            width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: "DST",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: Number(week.distance || 0).toFixed(2),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: (week.count || 0).toString(),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: week.heartRate ? week.heartRate.toString() : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: week.pace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: week.maxDistance ? Number(week.maxDistance).toFixed(2) : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: week.bestPace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              // 第二列 MONTH（结构同Week）
              {
                type: "vstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                    height: (height - 4 * 2) * 0.72,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 10,
                    },
                  },
                  //border: { color: $color("#30df4a"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "MONTH",
                      font: $font("Helvetica-Bold", 10),
                      color: textLabel,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.15,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
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
                        height: (height - 4 * 2) * 0.72 * 0.05,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
                    },
                  },
                  {
                    type: "hstack",
                    props: {
                      spacing: 3,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.8,
                      },
                      //border:  { color:  $color("#30df4a"), width: 1, },
                    },
                    views:[
                      {
                        type: "vstack",
                        props: {
                          spacing: 0,
                          frame: {
                            width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: "DST",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                        ],
                      },
                      {
                        type: "vstack",
                        props: {
                          spacing: 0,
                          frame: {
                            width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: Number(month.distance || 0).toFixed(2),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: (month.count || 0).toString(),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: month.heartRate ? month.heartRate.toString() : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: month.pace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: month.maxDistance ? Number(month.maxDistance).toFixed(2) : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: month.bestPace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                        ],
                      },
                    ],
                  },
                ],
              },
              // 第三列 YEAR（结构同Week）
              {
                type: "vstack",
                props: {
                  spacing: 0,
                  frame: {
                    width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                    height: (height - 4 * 2) * 0.72,
                  },
                  background: {
                    type: "gradient",
                    props: {
                      colors: boxBg,
                      opacity: 0.3,
                      cornerRadius: 10,
                    },
                  },
                  //border: { color: $color("#30df4a"), width: 1, },
                },
                views: [
                  {
                    type: "text",
                    props: {
                      text: "YEAR",
                      font: $font("Helvetica-Bold", 10),
                      color: textLabel,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.15,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
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
                        height: (height - 4 * 2) * 0.72 * 0.05,
                      },
                      //border: { color: $color("#ff0202"), width: 1, },
                    },
                  },
                  {
                    type: "hstack",
                    props: {
                      spacing: 3,
                      frame: {
                        width: ((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3,
                        height: (height - 4 * 2) * 0.72 * 0.8,
                      },
                      //border:  { color:  $color("#30df4a"), width: 1, },
                    },
                    views:[
                      {
                        type: "vstack",
                        props: {
                          spacing: 0,
                          frame: {
                            width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: "DST",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
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
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                        ],
                      },
                      {
                        type: "vstack",
                        props: {
                          spacing: 0,
                          frame: {
                            width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                            height: (height - 4 * 2) * 0.72 * 0.8,
                          },
                        //border:  { color:  $color("#3f5842"), width: 1, },
                        },
                        views:[
                          {
                            type: "text",
                            props: {
                              text: Number(year.distance || 0).toFixed(2),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: (year.count || 0).toString(),
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: year.heartRate ? year.heartRate.toString() : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: year.pace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: year.maxDistance ? Number(year.maxDistance).toFixed(2) : "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                          {
                            type: "text",
                            props: {
                              text: year.bestPace || "-",
                              font: $font("Helvetica-Bold", 6),
                              color: textValue,
                              frame: {
                                width: (((width - 10 * 2 - 10) * 0.6 - 10 * 2) / 3 - 3) / 2,
                                height: ((height - 4 * 2) * 0.72 * 0.8) / 6,
                              },
                              //border: { color: $color("#ff0202"), width: 1, },
                            },
                          },
                        ],
                      },
                    ],
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
          frame: {
            width: width - 10 * 2 - 10,
            height: (height - 4 * 2) * 0.07,
          },
          spacing: 0,
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

// 导出函数以便在其他模块中使用
module.exports = renderMediumWidget;
