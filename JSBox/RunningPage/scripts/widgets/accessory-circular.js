// Accessory Circular Widget

function renderAccessoryCircular(widgetWidth, widgetHeight, isDarkMode, widgetData) {
  const { today } = widgetData;
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.center,
      spacing: 4,
      padding: 8
    },
    views: [
      {
        type: "text",
        props: {
          text: today.count.toString(),
          font: $font("Menlo-Bold", 20),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000"),
          alignment: $widget.alignment.center
        }
      },
      {
        type: "text",
        props: {
          text: "runs",
          font: $font("Menlo", 10),
          color: isDarkMode ? $color("#CCCCCC") : $color("#666666"),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}

module.exports = renderAccessoryCircular;
