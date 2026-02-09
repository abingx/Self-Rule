function renderMediumWidget(width, height, isDarkMode) {
  // 使用 Running Data.js 中的标题渐变颜色作为背景
  const bgColors = isDarkMode
    ? [$color("#5568d3"), $color("#6b4fa0"), $color("#d946ef")]
    : [$color("#667eea"), $color("#764ba2"), $color("#f093fb")];
  // 字体颜色：突出重点，使用高对比度
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
      //border:  { color:  $color("#ee00ba"), width: 1, },
    },
    views: [
      // 标题区
      {
        type: "hstack",
        props: {
          spacing: 0,
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
                width: (width - (10 + 6) * 2) * 0.7,
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
                width: (width - (10 + 6) * 2) * 0.3,
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
          // 左数据区
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
                  colors: [$color("#ffffff")],
                  opacity: 0.1,
                  cornerRadius: 10,
                },
              },
              //border:  { color:  $color("#30df4a"), width: 1, },
            },
            views: [
              // 第一排
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
              // 第二排
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
                      text: "89.12",
                      font: $font("Helvetica-Bold", 28),
                      color: textValue,
                      frame: {
                        width: (width - 10 * 2 - 10) * 0.4 * 0.54,
                        height: (height - 4 * 2) * 0.72 * 0.35,
                        alignment: $widget.alignment.center,
                      },
                      lineLimit: 1,
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
              // 第三排
              {
                type: "text",
                props: {
                  text: "无氧效果",
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
              // 第四行
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
              // 第五行
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
                      text: "140",
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
                      text: "2:12:34",
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
                      text: "5'30\"",
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
            ],
          },
          // 中空白
          {
            type: "text",
            props: {
              text: " ",
              //font: $font("Helvetica-Bold", 15),
              frame: {
                width: 10,
                height: (height - 4 * 2) * 0.72,
              },
              //border: { color: $color("#baee00"), width: 1, },
            },
          },
          // 右数据区
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
              // 第一列WEEK
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
                      colors: [$color("#ffffff")],
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              text: "53.12",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "5",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "140",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "5'39\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "31.45",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "4'39\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
              // 第二列MONTH
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
                      colors: [$color("#ffffff")],
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              text: "253.12",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "15",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "145",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "5'30\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "31.45",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "4'21\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
              // 第三列YEAR
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
                      colors: [$color("#ffffff")],
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              color: textLabel,
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
                              text: "2153.12",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "175",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "147",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "5'33\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "42.21",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
                              text: "4'35\"",
                              font: $font("Helvetica-Bold", 6),
                              color: textLabel,
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
              text: "2026/02/03 05:12",
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
              text: "2026/02/03 12:31",
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
      return renderMediumWidget(widgetWidth, widgetHeight, isDarkMode);
    } else if (family === 2) {
      // Large 尺寸
      return {
        type: "text",
        props: {
          text: "Large Widget\n请使用中尺寸",
          alignment: $widget.alignment.center,
        },
      };
    } else {
      // Small 尺寸 (family === 0) 或其他
      return {
        type: "text",
        props: {
          text: "Small Widget\n请使用中尺寸",
          alignment: $widget.alignment.center,
        },
      };
    }
  },
});
