// Small Widget
// 此模块定义了 JSBox 中的跑步统计小尺寸小组件

const utils = require("../utils");

/**
 * 渲染小型跑步统计组件
 * @param {number} width - 组件宽度
 * @param {number} height - 组件高度
 * @param {boolean} isDarkMode - 设备是否处于深色模式
 * @param {Object} widgetData - 包含跑步统计数据的数据对象
 * @returns {Object} 组件配置对象
 */
function renderSmallWidget(width, height, isDarkMode, widgetData) {
  // 解构组件数据以提取跑步统计数据
  const { today, week, month, year, latestRunStr, updateStr, getWidgetURL } = widgetData;

  // 根据深色模式设置定义渐变背景色
  const bgColors = isDarkMode
    ? [$color("#5568d3"), $color("#6b4fa0"), $color("#d946ef")]  // 深色模式渐变色
    : [$color("#667eea"), $color("#764ba2"), $color("#f093fb")]; // 浅色模式渐变色

  // 根据深色模式设置定义文本颜色
  const textTitle = isDarkMode ? $color("#e9ecef") : $color("#ffffff"); // 标题文字颜色
  const textLabel = isDarkMode ? $color("#adb5bd") : $color("#ffffff"); // 标签文字颜色
  const textValue = isDarkMode ? $color("#ffffff") : $color("#ffffff"); // 数值文字颜色
  const textTime = isDarkMode ? $color("#e9ecef") : $color("#ffffff");  // 时间戳文字颜色
  const boxBg = isDarkMode ? [$color("#ffffff")] : [$color("#ffffff")]; // 数据框背景色

  // 返回组件配置对象
  return {
    type: "vstack", // 垂直堆叠布局
    props: {
      spacing: 0, // 元素之间间距
      frame: {
        width: width,  // 设置组件宽度
        height: height, // 设置组件高度
      },
      background: {
        type: "gradient", // 应用渐变背景
        props: {
          colors: bgColors, // 使用定义的渐变色
        },
      },
      widgetURL: getWidgetURL(), // 设置点击组件时打开的URL
      //border:  { color:  $color("#ee00ba"), width: 1, }, // 可选边框，用于调试
    },
    views: [
      // 头部区域 - 显示标题和跑步图标
      {
        type: "hstack", // 水平堆叠布局
        props: {
          spacing: 0, // 标题和图标之间的间距
          frame: {
            width: width - 10 * 2, // 宽度考虑内边距
            height: (height - 4 * 2) * 0.21, // 高度占总组件高度的百分比
          },
          //border:  { color:  $color("#dfd930"), width: 1, }, // 可选边框，用于调试
        },
        views: [
          // "Running" 文字标签
          {
            type: "text",
            props: {
              text: "Running", // 主标题文字
              font: $font("Helvetica-Bold", 15), // 粗体字体，大小15
              color: textTitle, // 根据深色模式使用适当的文字颜色
              frame: {
                width: (width - 10 * 2 - 6 * 2 ) * 0.7, // 计算70%可用空间的宽度
                height: (height - 4 * 2) * 0.21, // 与父容器相同高度
                alignment: $widget.alignment.leading, // 文字左对齐
              },
              //border:  { color:  $color("#baee00"), width: 1, }, // 可选边框，用于调试
            },
          },
          // 跑步表情符号图标
          {
            type: "text",
            props: {
              text: "🏃‍♂️", // 跑步人表情符号
              font: $font("Helvetica-Bold", 15), // 粗体字体，大小15
              color: textTitle, // 根据深色模式使用适当的文字颜色
              frame: {
                width: (width - 10 * 2 - 6 * 2 ) * 0.3, // 计算30%可用空间的宽度
                height: (height - 4 * 2) * 0.21, // 与父容器相同高度
                alignment: $widget.alignment.trailing, // 文字右对齐
              },
              //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
            },
          },
        ],
      },
      // 主数据区域 - 显示今日跑步距离
      {
        type: "vstack", // 垂直堆叠布局
        props: {
          spacing: 0, // 元素之间无间距
          frame: {
            width: width - 10 * 2, // 宽度考虑内边距
            height: (height - 4 * 2) * 0.33, // 高度占总组件高度的百分比
          },
          //border:  { color:  $color("#744c6b"), width: 1, }, // 可选边框，用于调试
        },
        views: [
          // "Today" 标签
          {
            type: "text",
            props: {
              text: "Today", // 标签文字
              font: $font("Helvetica-Bold", 10), // 粗体字体，大小10
              color: textLabel, // 根据深色模式使用适当的标签颜色
              frame: {
                width: width - 10 * 2, // 容器的全宽
                height: (height - 4 * 2) * 0.33 * 0.38, // 容器高度的38%
              },
              //border:  { color:  $color("#ff0202"), width: 1, }, // 可选边框，用于调试
            },
          },
          // 今日距离数值
          {
            type: "hstack", // 水平堆叠布局显示距离
            props: {
              spacing: 0, // 元素之间无间距
              frame: {
                width: width - 10 * 2, // 容器的全宽
                height: (height - 4 * 2) * 0.33 * 0.62, // 容器高度的62%
              },
              alignment: $widget.alignment.bottom, // 内容底部对齐
              //border:  { color:  $color("#6c7c87"), width: 1, }, // 可选边框，用于调试
            },
            views: [
              // 左侧空白元素
              {
                type: "text",
                props: {
                  text: " ", // 空白字符
                  font: $font("Helvetica-Bold", 14), // 字体大小用于间距计算
                  color: textValue, // 文字颜色（不会显示）
                  frame: {
                    width: (width - 10 * 2) * 0.23, // 容器宽度的23%
                    height: (height - 4 * 2) * 0.33 * 0.62, // 父容器的全高
                    alignment: $widget.alignment.center, // 居中对齐
                  },
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 距离数值（主要数字）
              {
                type: "text",
                props: {
                  text: Number(today.distance).toFixed(2), // 将距离格式化为两位小数
                  font: $font("Helvetica-Bold", 28), // 大号粗体字体显示主要数值
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  frame: {
                    width: (width - 10 * 2) * 0.54, // 容器宽度的54%
                    height: (height - 4 * 2) * 0.33, // 父容器的全高
                    alignment: $widget.alignment.center, // 居中对齐
                  },
                  lineLimit: 1,
                  minimumScaleFactor: 0.5, // 如需要允许文字缩小
                  //border:  { color:  $color("#baee00"), width: 1, }, // 可选边框，用于调试
                },
              },
              // "km" 单位标签
              {
                type: "text",
                props: {
                  text: "km", // 计量单位
                  font: $font("Helvetica-Bold", 14), // 中等字体大小
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  frame: {
                    width: (width - 10 * 2) * 0.23, // 容器宽度的23%
                    height: (height - 4 * 2) * 0.33 * 0.62, // 父容器的全高
                    alignment: $widget.alignment.center, // 居中对齐
                  },
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
            ],
          },
        ],
      },
      // 次要数据区域 - 显示周、月、年统计数据
      {
        type: "hstack", // 水平堆叠布局用于三个数据框
        props: {
          spacing: 6, // 数据框之间的间距
          frame: {
            width: width - 10 * 2, // 宽度考虑内边距
            height: (height - 4 * 2) * 0.39, // 高度占总组件高度的百分比
          },
          //border:  { color:  $color("#fcd8f4"), width: 1, }, // 可选边框，用于调试
        },
        views: [
          // 周统计数据框
          {
            type: "vstack", // 周数据垂直堆叠布局
            props: {
              spacing: 3, // 文字元素之间的间距
              frame: {
                width: (width - 10 * 2 - 6 * 2) / 3, // 将剩余宽度除以3得到相等的框
                height: (height - 4 * 2) * 0.39 * 0.7, // 容器高度的70%
              },
              background: {
                type: "gradient", // 半透明背景
                props: {
                  colors: boxBg, // 背景颜色
                  opacity: 0.3, // 30%不透明度以达到微妙效果
                  cornerRadius: 6, // 圆角
                },
              },
              //border:  { color:  $color("#059171"), width: 1, }, // 可选边框，用于调试
            },
            views: [
              // "WEEK" 标签
              {
                type: "text",
                props: {
                  text: "WEEK", // 时间段标签
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textLabel, // 根据深色模式使用适当的标签颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 周跑步次数
              {
                type: "text",
                props: {
                  text: week.count.toString(), // 将跑步次数转换为字符串
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 周距离
              {
                type: "text",
                props: {
                  text: Number(week.distance).toFixed(2), // 将距离格式化为两位小数
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
            ],
          },
          // 月统计数据框
          {
            type: "vstack", // 月数据垂直堆叠布局
            props: {
              spacing: 3, // 文字元素之间的间距
              frame: {
                width: (width - 10 * 2 - 6 * 2) / 3, // 与周框相同的宽度
                height: (height - 4 * 2) * 0.39 * 0.7, // 与周框相同的高度
              },
              background: {
                type: "gradient", // 半透明背景
                props: {
                  colors: boxBg, // 背景颜色
                  opacity: 0.3, // 30%不透明度以达到微妙效果
                  cornerRadius: 6, // 圆角
                },
              },
              //border:  { color:  $color("#059171"), width: 1, }, // 可选边框，用于调试
            },
            views: [
              // "MONTH" 标签
              {
                type: "text",
                props: {
                  text: "MONTH", // 时间段标签
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textLabel, // 根据深色模式使用适当的标签颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 月跑步次数
              {
                type: "text",
                props: {
                  text: month.count.toString(), // 将跑步次数转换为字符串
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 月距离
              {
                type: "text",
                props: {
                  text: Number(month.distance).toFixed(2), // 将距离格式化为两位小数
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
            ],
          },
          // 年统计数据框
          {
            type: "vstack", // 年数据垂直堆叠布局
            props: {
              spacing: 3, // 文字元素之间的间距
              frame: {
                width: (width - 10 * 2 - 6 * 2) / 3, // 与其他框相同的宽度
                height: (height - 4 * 2) * 0.39 * 0.7, // 与其他框相同的高度
              },
              background: {
                type: "gradient", // 半透明背景
                props: {
                  colors: boxBg, // 背景颜色
                  opacity: 0.3, // 30%不透明度以达到微妙效果
                  cornerRadius: 6, // 圆角
                },
              },
              //border:  { color:  $color("#059171"), width: 1, }, // 可选边框，用于调试
            },
            views: [
              // "YEAR" 标签
              {
                type: "text",
                props: {
                  text: "YEAR", // 时间段标签
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textLabel, // 根据深色模式使用适当的标签颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 年跑步次数
              {
                type: "text",
                props: {
                  text: year.count.toString(), // 将跑步次数转换为字符串
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
              // 年距离
              {
                type: "text",
                props: {
                  text: Number(year.distance).toFixed(2), // 将距离格式化为两位小数
                  font: $font("Helvetica-Bold", 8), // 小号粗体字体
                  color: textValue, // 根据深色模式使用适当的文字颜色
                  //border:  { color:  $color("#ee8700"), width: 1, }, // 可选边框，用于调试
                },
              },
            ],
          },
        ],
      },
      // 时间戳区域 - 显示最新跑步和更新时间
      {
        type: "hstack", // 水平堆叠布局用于时间戳
        props: {
          spacing: 0, // 时间戳元素之间无间距
          frame: {
            width: width - 10 * 2 - 10, // 宽度考虑内边距
            height: (height - 4 * 2) * 0.07, // 小高度用于时间戳
          },
          //border:  { color:  $color("#35854e"), width: 1, }, // 可选边框，用于调试
        },
        views: [
          // 最新跑步时间
          {
            type: "text",
            props: {
              text: latestRunStr, // 最新跑步时间格式化字符串
              font: $font("Menlo", 6), // 等宽字体，小字号
              color: textTime, // 根据深色模式使用适当的时间戳颜色
              frame: {
                width: (width - 10 * 2 - 10) / 2, // 可用宽度的一半
                height: (height - 4 * 2) * 0.07, // 与父容器相同高度
                alignment: $widget.alignment.leading, // 左对齐
              },
              //border:  { color:  $color("green"), width: 1, }, // 可选边框，用于调试
            },
          },
          // 最后更新时间
          {
            type: "text",
            props: {
              text: updateStr, // 更新时间格式化字符串
              font: $font("Menlo", 6), // 等宽字体，小字号
              color: textTime, // 根据深色模式使用适当的时间戳颜色
              frame: {
                width: (width - 10 * 2 - 10) / 2, // 可用宽度的一半
                height: (height - 4 * 2) * 0.07, // 与父容器相同高度
                alignment: $widget.alignment.trailing, // 右对齐
              },
              //border:  { color:  $color("green"), width: 1, }, // 可选边框，用于调试
            },
          },
        ],
      },
    ],
  };
}

// 导出函数以便在其他模块中使用
module.exports = renderSmallWidget;