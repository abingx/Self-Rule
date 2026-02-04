// Medium Widget

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
  titleFontSize: 22, 
  gridFontSize: 14, 
  footerFontSize: 8, 
  titleTopSeparatorFontSize: 12, 
  topSeparatorFontSize: 6, 
  bottomSeparatorFontSize: 8, 
  footerBottomSeparatorFontSize: 8 
};

function renderMediumWidget(mediumW, mediumH, today, week, month, year, latestRunStr, updateStr, isDarkMode, widgetURL) {
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
    return label.padEnd(9, utils.getPlaceholder(1));
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
            { fixed: (mediumW - SPACING.paddingLeft - SPACING.paddingRight) * 0.36 },
            { fixed: (mediumW - SPACING.paddingLeft - SPACING.paddingRight) * 0.22 },
            { fixed: (mediumW - SPACING.paddingLeft - SPACING.paddingRight) * 0.42 }
          ],
          spacing: SPACING.dataSpacing
        },
        views: [
          createCell(formatLabel("Today"), "left"), 
          createCell(formatRuns(today.count), "right"), 
          createCell(formatKm(today.distance), "right"),
          
          createCell(formatLabel("Week"), "left"), 
          createCell(formatRuns(week.count), "right"), 
          createCell(formatKm(week.distance), "right"),
          
          createCell(formatLabel("Month"), "left"), 
          createCell(formatRuns(month.count), "right"), 
          createCell(formatKm(month.distance), "right"),
          
          createCell(formatLabel("Year"), "left"), 
          createCell(formatRuns(year.count), "right"), 
          createCell(formatKm(year.distance), "right")
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

module.exports = renderMediumWidget;