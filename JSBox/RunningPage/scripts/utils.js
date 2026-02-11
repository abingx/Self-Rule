// 工具函数模块

function parseDate(str) {
  if (str instanceof Date) return new Date(str);
  if (typeof str === "number") return new Date(str);
  if (typeof str !== "string" || str.trim().length === 0) return new Date(NaN);
  return new Date(str.replace(" ", "T"));
}

// 对单条活动数据做一次预处理，给统计阶段提供可复用字段，避免重复解析。
function normalizeRunData(run) {
  if (!run || typeof run !== "object") return null;

  const startDate = parseDate(run.start_date_local);
  const startTimestamp = startDate.getTime();
  const distanceMeters = Number(run.distance) || 0;
  const distanceKm = distanceMeters / 1000;
  const movingSeconds = parseTimeToSeconds(run.moving_time || run.elapsed_time || 0);

  return {
    ...run,
    _startDate: startDate,
    _startTimestamp: isFinite(startTimestamp) ? startTimestamp : NaN,
    _distanceMeters: distanceMeters,
    _distanceKm: distanceKm,
    _movingSeconds: movingSeconds
  };
}

/**
 * 解析时间字符串为秒数
 * 支持格式: "H:MM:SS" 或 "H:MM:SS.ffffff"
 * @param {string|number} timeStr - 时间字符串或秒数
 * @returns {number} 秒数
 */
function parseTimeToSeconds(timeStr) {
  // 如果已经是数字,直接返回
  if (typeof timeStr === 'number') return timeStr;

  // 如果不是字符串,返回0
  if (typeof timeStr !== 'string') return 0;

  // 解析 "H:MM:SS" 或 "H:MM:SS.ffffff" 格式
  const parts = timeStr.split(':');
  if (parts.length !== 3) return 0;

  const hours = parseInt(parts[0], 10) || 0;
  const minutes = parseInt(parts[1], 10) || 0;
  const seconds = parseFloat(parts[2]) || 0;

  return hours * 3600 + minutes * 60 + seconds;
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
  // since 为时间窗口起点；调用方可先筛选窗口，再复用 summarize 聚合。
  const runs = list.filter(r => {
    if (!r) return false;
    const timestamp = Number.isFinite(r._startTimestamp)
      ? r._startTimestamp
      : parseDate(r.start_date_local).getTime();
    return !isNaN(timestamp) && timestamp >= since.getTime();
  });
  const count = runs.length;
  const distance = runs.reduce((sum, r) => {
    if (typeof r._distanceKm === "number") return sum + r._distanceKm;
    return sum + (Number(r.distance) || 0) / 1000;
  }, 0);

  // 计算总时长（秒）
  const totalTime = runs.reduce((sum, r) => {
    if (typeof r._movingSeconds === "number") return sum + r._movingSeconds;
    const time = r.moving_time || r.elapsed_time || 0;
    return sum + parseTimeToSeconds(time);
  }, 0);
  const duration = formatDuration(totalTime);

  // 计算平均心率（如果有心率数据）
  const runsWithHeartRate = runs.filter(r => r.average_heartrate);
  const heartRate = runsWithHeartRate.length > 0
    ? Math.round(runsWithHeartRate.reduce((sum, r) => sum + r.average_heartrate, 0) / runsWithHeartRate.length)
    : null;

  // 计算平均配速（秒/公里 -> 文本）
  const totalDistance = distance;
  const pace = totalDistance > 0 ? formatPace(totalTime / totalDistance) : null;

  // 找到最大单次距离
  const maxDistance = runs.length > 0
    ? Math.max(...runs.map(r => (typeof r._distanceKm === "number" ? r._distanceKm : (Number(r.distance) || 0) / 1000)))
    : 0;

  // 找到最佳配速（最快的配速，即最小的秒/公里）
  const runsWithPace = runs.filter(r => (typeof r._distanceMeters === "number" ? r._distanceMeters : Number(r.distance) || 0) > 0 && (r.moving_time || r.elapsed_time));
  const bestPace = runsWithPace.length > 0
    ? formatPace(
      Math.min(
        ...runsWithPace.map(r => {
          const seconds = typeof r._movingSeconds === "number"
            ? r._movingSeconds
            : parseTimeToSeconds(r.moving_time || r.elapsed_time);
          const km = typeof r._distanceKm === "number"
            ? r._distanceKm
            : (Number(r.distance) || 0) / 1000;
          return seconds / km;
        })
      )
    )
    : null;

  return {
    count,
    distance: distance.toFixed(2),
    duration,
    heartRate,
    pace,
    maxDistance: maxDistance.toFixed(2),
    bestPace
  };
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

function formatDateTime(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}/${month}/${day} ${hour}:${minute}`;
}

function formatPace(secondsPerKm) {
  if (typeof secondsPerKm !== 'number' || !isFinite(secondsPerKm) || secondsPerKm <= 0) return null;
  const totalSeconds = Math.round(secondsPerKm);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}'${String(seconds).padStart(2, '0')}"`;
}

function formatDuration(seconds) {
  if (typeof seconds !== 'number' || !isFinite(seconds) || seconds <= 0) return null;
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  } else {
    return `${minutes}:${String(secs).padStart(2, '0')}`;
  }
}

function getExerciseEffect(name) {
  // 从 name 中提取训练类型
  if (name && typeof name === 'string') {
    let trainingType = null;

    // 情况1: 如果 name 中包含 " - ",提取后半部分作为训练类型
    // 例如: "成都市 - 基础训练" -> "基础训练"
    if (name.includes(' - ')) {
      const parts = name.split(' - ');
      trainingType = parts[parts.length - 1].trim();
    }
    // 情况2: 如果没有 " - ",但包含空格,取最后一个词
    // 例如: "成都 跑步" -> "跑步"
    else if (name.includes(' ')) {
      const words = name.trim().split(/\s+/);  // 按空格拆分(处理多个空格)
      trainingType = words[words.length - 1];
    }
    // 情况3: 没有空格也没有 "-",整个就是训练类型
    else {
      trainingType = name.trim();
    }

    // 如果提取到的不是空字符串,就使用它
    if (trainingType && trainingType.length > 0) {
      return trainingType;
    }
  }

  // 如果没有从 name 提取到有效训练类型,返回默认值
  return "跑步";
}

module.exports = {
  parseDate,
  normalizeRunData,
  parseTimeToSeconds,
  startOfDay,
  startOfWeek,
  startOfMonth,
  startOfYear,
  summarize,
  saveCache,
  loadCache,
  formatDateTime,
  formatPace,
  formatDuration,
  getExerciseEffect
};
