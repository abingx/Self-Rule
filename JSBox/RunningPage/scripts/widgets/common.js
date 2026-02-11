// 组件主题配置：集中管理颜色，保证 small/medium/large 风格一致。
function getTheme(isDarkMode) {
  return {
    bgColors: isDarkMode
      ? [$color("#5568d3"), $color("#6b4fa0"), $color("#d946ef")]
      : [$color("#667eea"), $color("#764ba2"), $color("#f093fb")],
    textTitle: isDarkMode ? $color("#e9ecef") : $color("#ffffff"),
    textLabel: isDarkMode ? $color("#adb5bd") : $color("#ffffff"),
    textValue: $color("#ffffff"),
    textTime: isDarkMode ? $color("#e9ecef") : $color("#ffffff"),
    boxBg: [$color("#ffffff")]
  };
}

// 将距离统一格式化为两位小数，避免各组件重复写 Number(...).toFixed(2)。
function formatDistanceKm(value) {
  return Number(value || 0).toFixed(2);
}

module.exports = {
  getTheme,
  formatDistanceKm
};
