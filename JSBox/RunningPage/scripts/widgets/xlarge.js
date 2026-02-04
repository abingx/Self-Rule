// XLarge Widget (iPad)

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

module.exports = renderXLargeWidget;