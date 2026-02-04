// 工具函数模块

function parseDate(str) {
  return new Date(str.replace(" ", "T"));
}

function startOfDay(d) {
  const date = new Date(d);
  date.setHours(0, 0, 0, 0);
  return date;
}

function startOfWeek(d) {
  const date = new Date(d);
  const day = date.getDay() || 7;
  if (day !== 1) date.setDate(date.getDate() - (day - 1));
  date.setHours(0, 0, 0, 0);
  return date;
}

function startOfMonth(d) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function startOfYear(d) {
  return new Date(d.getFullYear(), 0, 1);
}

function summarize(list, since) {
  const runs = list.filter(r => parseDate(r.start_date_local) >= since);
  const count = runs.length;
  const distance = runs.reduce((sum, r) => sum + r.distance, 0) / 1000;
  return { count, distance: distance.toFixed(2) };
}

function saveCache(data) {
  $file.write({
    data: $data({ string: JSON.stringify(data) }),
    path: global.CONFIG.CACHE_FILE
  });
}

function loadCache() {
  const cache = $file.read(global.CONFIG.CACHE_FILE);
  if (cache) {
    try {
      return JSON.parse(cache.string);
    } catch (e) {
      console.error("缓存文件解析失败:", e);
      return null;
    }
  }
  return null;
}

function getPlaceholder(count = 1) {
  if (global.CONFIG.SHOW_PLACEHOLDERS) {
    return "^".repeat(count);
  } else {
    return " ".repeat(count);
  }
}

function getSeparator() {
  if (global.CONFIG.SHOW_PLACEHOLDERS) {
    return "`_`_`_`_`_`_`_`_`_`";
  } else {
    return "              ";
  }
}

function formatDateTime(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}/${month}/${day} ${hour}:${minute}`;
}

module.exports = {
  parseDate,
  startOfDay,
  startOfWeek,
  startOfMonth,
  startOfYear,
  summarize,
  saveCache,
  loadCache,
  getPlaceholder,
  getSeparator,
  formatDateTime
};