// Small Widget

const utils = require("../utils");

const SPACING = { 
  paddingTop: 0, 
  paddingRight: 12, 
  paddingBottom: 0, 
  paddingLeft: 12, 
  dataSpacing: 6 
};

const FONTS = { 
  fontFamily: "Menlo", 
  titleFontFamily: "Menlo-Bold", 
  titleFontSize: 18, 
  gridFontSize: 12, 
  footerFontSize: 6, 
  titleTopSeparatorFontSize: 13, 
  topSeparatorFontSize: 13, 
  bottomSeparatorFontSize: 8, 
  footerBottomSeparatorFontSize: 4 
};

function renderSmallWidget(widgetWidth, widgetHeight, isDarkMode, widgetData) {
  const { today, week, month, year, latestRunStr, updateStr, getWidgetURL } = widgetData;
  function createCell(text, align) {
    return {
      type: "text",
      props: {
        text,
        font: $font(FONTS.fontFamily, FONTS.gridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing
      }
    };
  }

  function padLeft(str, width) {
    return str.padStart(width, utils.getPlaceholder(1));
  }
  
  function formatLabel(label) {
    return label.padEnd(5, utils.getPlaceholder(1));
  }
  
  function formatCount(count) {
    return padLeft(count.toString(), 3);
  }
  
  function formatDistance(distance) {
    return padLeft(Number(distance).toFixed(2), 7);
  }

  return {
    type: "vstack",
    props: { 
      spacing: 0,
      padding: $insets(SPACING.paddingTop, SPACING.paddingRight, SPACING.paddingBottom, SPACING.paddingLeft),
      widgetURL: getWidgetURL()
    },
    views: [
      {
        type: "text",
        props: {
          text: utils.getSeparator(),
          font: $font(FONTS.fontFamily, FONTS.titleTopSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 0
        },
        views: [{
          type: "text",
          props: {
            text: "Summary",
            font: $font(FONTS.titleFontFamily, FONTS.titleFontSize),
            alignment: $widget.alignment.center
          }
        }]
      },
      
      {
        type: "text",
        props: {
          text: utils.getSeparator(),
          font: $font(FONTS.fontFamily, FONTS.topSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      {
        type: "vgrid",
        props: {
          columns: [
            { fixed: (widgetWidth - SPACING.paddingLeft - SPACING.paddingRight) * 0.36 },
            { fixed: (widgetWidth - SPACING.paddingLeft - SPACING.paddingRight) * 0.22 },
            { fixed: (widgetWidth - SPACING.paddingLeft - SPACING.paddingRight) * 0.42 }
          ],
          spacing: SPACING.dataSpacing
        },
        views: [
          createCell(formatLabel("Today"), "left"), 
          createCell(formatCount(today.count), "right"), 
          createCell(formatDistance(today.distance), "right"),
          
          createCell(formatLabel("Week"), "left"), 
          createCell(formatCount(week.count), "right"), 
          createCell(formatDistance(week.distance), "right"),
          
          createCell(formatLabel("Month"), "left"), 
          createCell(formatCount(month.count), "right"), 
          createCell(formatDistance(month.distance), "right"),
          
          createCell(formatLabel("Year"), "left"), 
          createCell(formatCount(year.count), "right"), 
          createCell(formatDistance(year.distance), "right")
        ]
      },
      
      {
        type: "text",
        props: {
          text: utils.getSeparator(),
          font: $font(FONTS.fontFamily, FONTS.bottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      },
      
      {
        type: "vstack",
        props: {
          alignment: $widget.horizontalAlignment.center,
          spacing: 1
        },
        views: [
          {
            type: "text",
            props: {
              text: `Latest: ${latestRunStr}`,
              font: $font(FONTS.fontFamily, FONTS.footerFontSize),
              alignment: $widget.alignment.center
            }
          },
          {
            type: "text",
            props: {
              text: `Update: ${updateStr}`,
              font: $font(FONTS.fontFamily, FONTS.footerFontSize),
              alignment: $widget.alignment.center
            }
          }
        ]
      },
      
      {
        type: "text",
        props: {
          text: utils.getSeparator(),
          font: $font(FONTS.fontFamily, FONTS.footerBottomSeparatorFontSize),
          alignment: $widget.alignment.center
        }
      }
    ]
  };
}

module.exports = renderSmallWidget;