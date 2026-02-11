// Accessory Inline Widget

function renderAccessoryInline(widgetWidth, widgetHeight, isDarkMode, widgetData) {
  const { today } = widgetData;
  return {
    type: "hstack",
    props: {
      alignment: $widget.alignment.center,
      spacing: 8,
      padding: $insets(2, 6, 2, 6)
    },
    views: [
      {
        type: "text",
        props: {
          text: "🏃",
          font: $font(14)
        }
      },
      {
        type: "text",
        props: {
          text: `${today.count} | ${today.distance}km`,
          font: $font("Menlo", 11),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000")
        }
      }
    ]
  };
}

module.exports = renderAccessoryInline;
