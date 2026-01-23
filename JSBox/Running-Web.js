/**
 * JSBox 跑步数据 Web 视图
 * 
 * 功能说明:
 * - 从共享目录读取跑步数据缓存
 * - 显示跑步数据的 HTML 表格
 * - 支持按类型过滤和日期排序
 */

// ===== 常量定义 =====
/** 共享缓存路径 */
const CACHE_PATH = "shared://activities_cache.json";

/**
 * ===== 工具函数 =====
 */

/**
 * 解析 ISO 格式日期字符串为 Date 对象
 */
function parseDate(str) {
  return new Date(str.replace(" ", "T"));
}

/**
 * 从缓存文件读取数据 (Web 视图专用)
 * 
 * @returns {Array} 跑步数据数组
 */
function loadCacheWeb() {
  try {
    const cache = $file.read(CACHE_PATH);
    if (cache) {
      return JSON.parse(cache.string);
    }
  } catch (e) {
    console.error("缓存文件读取/解析失败:", e);
  }
  return [];
}

/**
 * 计算配速 (分:秒 per km)
 * 
 * @param {number} distance - 距离 (米)
 * @param {string} movingTime - 移动时间 (格式: "HH:MM:SS.ffffff")
 * @returns {string} 配速字符串 (格式: "MM:SS")
 */
function calculatePace(distance, movingTime) {
  if (!distance || distance === 0) return "N/A";
  
  const parts = movingTime.split(":");
  const hours = parseInt(parts[0]) || 0;
  const minutes = parseInt(parts[1]) || 0;
  const seconds = parseInt(parts[2]) || 0;
  
  const totalSeconds = hours * 3600 + minutes * 60 + seconds;
  const distanceKm = distance / 1000;
  const secondsPerKm = totalSeconds / distanceKm;
  const paceMin = Math.floor(secondsPerKm / 60);
  const paceSec = Math.round(secondsPerKm % 60);
  
  return `${paceMin}:${paceSec.toString().padStart(2, "0")}`;
}

/**
 * 格式化日期
 * 
 * @param {string} dateStr - 日期字符串
 * @returns {string} 格式化后的日期
 */
function formatDateWeb(dateStr) {
  const date = new Date(dateStr.replace(" ", "T"));
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * 生成 HTML 表格
 * 
 * @param {Array} activities - 跑步活动数据
 * @returns {string} HTML 字符串
 */
function generateTableHTML(activities) {
  const runs = activities
    .filter(a => a.type === "Run")
    .sort((a, b) => new Date(b.start_date_local) - new Date(a.start_date_local));
  
  let html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #f5f5f5;
      padding: 12px;
      color: #333;
    }
    
    .container {
      max-width: 100%;
      margin: 0 auto;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      overflow: hidden;
    }
    
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 16px;
      text-align: center;
    }
    
    .header h1 {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    
    .header p {
      font-size: 14px;
      opacity: 0.9;
    }
    
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10px;
    }
    
    thead {
      background-color: #f8f9fa;
      border-bottom: 2px solid #e9ecef;
    }
    
    th {
      padding: 6px 4px;
      text-align: left;
      font-weight: 600;
      color: #495057;
      border-right: 1px solid #dee2e6;
    }
    
    th:last-child {
      border-right: none;
    }
    
    tbody tr {
      border-bottom: 1px solid #dee2e6;
      transition: background-color 0.2s;
    }
    
    tbody tr:hover {
      background-color: #f8f9fa;
    }
    
    td {
      padding: 6px 4px;
      border-right: 1px solid #dee2e6;
      word-break: break-word;
      white-space: nowrap;
    }
    
    td:last-child {
      border-right: none;
    }
    
    .name {
      font-weight: 500;
      color: #495057;
      max-width: 95px;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    
    .distance {
      font-weight: 600;
      color: #667eea;
      text-align: right;
      font-size: 9px;
    }
    
    .pace {
      text-align: center;
      color: #764ba2;
      font-family: monospace;
      font-size: 9px;
    }
    
    .bpm {
      text-align: center;
      color: #e74c3c;
      font-size: 9px;
    }
    
    .time {
      text-align: center;
      color: #27ae60;
      font-family: monospace;
      font-size: 9px;
    }
    
    .date {
      text-align: center;
      color: #7f8c8d;
      font-size: 9px;
    }
    
    .empty {
      text-align: center;
      padding: 40px;
      color: #95a5a6;
      font-size: 16px;
    }
    
    .stats {
      background-color: #f8f9fa;
      padding: 8px 12px;
      display: flex;
      justify-content: space-around;
      border-top: 1px solid #dee2e6;
      font-size: 12px;
    }
    
    .stats span {
      font-size: 13px;
      color: #495057;
    }
    
    .stat-item {
      text-align: center;
    }
    
    .stat-value {
      font-weight: 600;
      color: #667eea;
      display: block;
      font-size: 16px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>跑步数据</h1>
    </div>
  `;
  
  if (runs.length === 0) {
    html += '<div class="empty">暂无跑步数据</div>';
  } else {
    html += `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Km</th>
          <th>Pace</th>
          <th>BPM</th>
          <th>Time</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
    `;
    
    runs.forEach(run => {
      const distanceKm = (run.distance / 1000).toFixed(2);
      const pace = calculatePace(run.distance, run.moving_time);
      const heartrate = run.average_heartrate ? Math.round(run.average_heartrate) : "N/A";
      const date = formatDateWeb(run.start_date_local);
      
      html += `
        <tr>
          <td class="name" title="${run.name || 'Running'}">${run.name || 'Running'}</td>
          <td class="distance">${distanceKm}</td>
          <td class="pace">${pace}</td>
          <td class="bpm">${heartrate}</td>
          <td class="time">${run.moving_time.split(".")[0]}</td>
          <td class="date">${date}</td>
        </tr>
      `;
    });
    
    html += `
      </tbody>
    </table>
    `;
  }
  
  html += `
  </div>
</body>
</html>
  `;
  
  return html;
}

/**
 * 渲染 Web 视图 (在 JSBox 主应用中显示)
 * 从共享目录缓存读取数据，生成 HTML 表格
 */
function renderWebView() {
  const activities = loadCacheWeb();
  const html = generateTableHTML(activities);
  
  const encodedHtml = encodeURIComponent(html);
  const dataUrl = `data:text/html;charset=utf-8,${encodedHtml}`;
  
  $ui.render({
    props: {
      title: "跑步数据"
    },
    views: [
      {
        type: "web",
        props: {
          url: dataUrl
        },
        layout: $layout.fill
      }
    ]
  });
}

// 直接渲染 Web 视图
renderWebView();
