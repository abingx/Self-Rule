// Accessory Rectangular Widget

function renderAccessoryRectangular(rectW, rectH, today, isDarkMode) {
  return {
    type: "vstack",
    props: {
      alignment: $widget.alignment.leading,
      spacing: 2,
      padding: $insets(4, 8, 4, 8)
    },
    views: [
      {
        type: "text",
        props: {
          text: `${today.count} runs`,
          font: $font("Menlo-Bold", 12),
          color: isDarkMode ? $color("#FFFFFF") : $color("#000000")
        }
      },
      {
        type: "text",
        props: {
          text: `${today.distance} km`,
          font: $font("Menlo", 10),
          color: isDarkMode ? $color("#CCCCCC") : $color("#666666")
        }
      }
    ]
  };
}

module.exports = renderAccessoryRectangular;