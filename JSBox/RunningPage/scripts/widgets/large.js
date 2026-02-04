// Large Widget

const utils = require("../utils");

const SPACING = { 
  paddingTop: 0, 
  paddingRight: 12, 
  paddingBottom: 0, 
  paddingLeft: 12, 
  dataSpacing: 10 
};

const FONTS = { 
  fontFamily: "Menlo", 
  titleFontFamily: "Menlo-Bold", 
  titleFontSize: 22, 
  gridFontSize: 14, 
  footerFontSize: 8, 
  titleTopSeparatorFontSize: 30, 
  topSeparatorFontSize: 20, 
  bottomSeparatorFontSize: 30, 
  footerBottomSeparatorFontSize: 20 
};

function renderLargeWidget(largeW, largeH, today, yesterday, week, lastWeek, month, lastMonth, year, lastYear, latestRunStr, updateStr, isDarkMode, widgetURL) {
  function createCell(text, align, colorType = "default") {
    let color = $color("#999999");
    
    switch (colorType) {
      case "current":
        color = isDarkMode ? $color("#FFFFFF") : $color("#000000");
        break;
      case "yesterday":
      case "lastWeek":
      case "lastMonth":
      case "lastYear":
        color = isDarkMode ? $color("#81C784") : $color("#4CAF50");
        break;
    }
    
    return {
      type: "text",
      props: {
        text,
        font: $font(FONTS.fontFamily, FONTS.gridFontSize),
        frame: { maxWidth: Infinity },
        alignment: align === "left" ? $widget.alignment.leading : $widget.alignment.trailing,
        color: color
      }
    };
  }

  function padLeft(str, width) {
    return str.padStart(width, utils.getPlaceholder(1));
  }
  
  function formatLabel(label) {
    return label.padEnd(10, utils.getPlaceholder(1));
  }
  
  function formatRuns(count) {
    if (count === 0) {
      return padLeft("0", 3) + " run" + utils.getPlaceholder(1);
    } else if (count === 1) {
      return padLeft("1", 3) + " run" + utils.getPlaceholder(1);
    } else {
      return padLeft(count.toString(), 3) + " runs";
    }
  }
  
  function formatKm(distance) {
    const kmStr = Number(distance).toFixed(2);
    return padLeft(kmStr, 8) + " km";
  }

  return {
    type: "vstack",
    props: { 
      spacing: 0,
      padding: $insets(SPACING.paddingTop, SPACING.paddingRight, SPACING.paddingBottom, SPACING.paddingLeft),
      link: widgetURL()
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
            { fixed: (largeW - SPACING.paddingLeft - SPACING.paddingRight) * 0.36 },
            { fixed: (largeW - SPACING.paddingLeft - SPACING.paddingRight) * 0.22 },
            { fixed: (largeW - SPACING.paddingLeft - SPACING.paddingRight) * 0.42 }
          ],
          spacing: SPACING.dataSpacing
        },
        views: [
          createCell(formatLabel("Today"), "left", "current"), 
          createCell(formatRuns(today.count), "right", "current"), 
          createCell(formatKm(today.distance), "right", "current"),
          
          createCell(formatLabel("Yesterday"), "left", "yesterday"), 
          createCell(formatRuns(yesterday.count), "right", "yesterday"), 
          createCell(formatKm(yesterday.distance), "right", "yesterday"),
          
          createCell(formatLabel("Week"), "left", "current"), 
          createCell(formatRuns(week.count), "right", "current"), 
          createCell(formatKm(week.distance), "right", "current"),
          
          createCell(formatLabel("Last Week"), "left", "lastWeek"), 
          createCell(formatRuns(lastWeek.count), "right", "lastWeek"), 
          createCell(formatKm(lastWeek.distance), "right", "lastWeek"),
          
          createCell(formatLabel("Month"), "left", "current"), 
          createCell(formatRuns(month.count), "right", "current"), 
          createCell(formatKm(month.distance), "right", "current"),
          
          createCell(formatLabel("Last Month"), "left", "lastMonth"), 
          createCell(formatRuns(lastMonth.count), "right", "lastMonth"), 
          createCell(formatKm(lastMonth.distance), "right", "lastMonth"),
          
          createCell(formatLabel("Year"), "left", "current"), 
          createCell(formatRuns(year.count), "right", "current"), 
          createCell(formatKm(year.distance), "right", "current"),
          
          createCell(formatLabel("Last Year"), "left", "lastYear"), 
          createCell(formatRuns(lastYear.count), "right", "lastYear"), 
          createCell(formatKm(lastYear.distance), "right", "lastYear")
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

module.exports = renderLargeWidget;