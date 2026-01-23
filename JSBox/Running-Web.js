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
    /* ===== 全局样式重置 ===== */
    /* 重置所有元素的默认边距和内边距，使用 border-box 盒模型 */
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    /* ===== 页面主体样式 ===== */
    /* 设置系统默认字体、背景色、内边距和文字颜色 */
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #f5f5f5;
      padding: 12px;
      color: #333;
    }
    
    /* ===== 主容器样式 ===== */
    /* 限制最大宽度、居中显示、白色背景、圆角阴影 */
    .container {
      max-width: 100%;
      margin: 0 auto;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      overflow: hidden;
    }
    
    /* ===== 头部区域样式 ===== */
    /* 紫色渐变背景、白色文字、内边距、居中 */
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 16px;
      text-align: center;
    }
    
    /* 标题文字大小和粗细 */
    .header h1 {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    
    /* 副标题文字大小和透明度 */
    .header p {
      font-size: 12px;
      opacity: 0.9;
    }
    
    /* ===== 数据表格样式 ===== */
    /* 表格宽度100%、折叠边框、小字号 */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10px;
    }
    
    /* 表头背景色和底部边框 */
    thead {
      background-color: #f8f9fa;
      border-bottom: 2px solid #e9ecef;
    }
    
    /* 表头单元格样式：内边距、左对齐、加粗、深灰文字 */
    th {
      padding: 6px 4px;
      text-align: left;
      font-weight: 600;
      color: #495057;
      border-right: 1px solid #dee2e6;
    }
    
    /* 移除最后一列的右边框 */
    th:last-child {
      border-right: none;
    }
    
    /* 表行样式：底部边框、悬停过渡效果 */
    tbody tr {
      border-bottom: 1px solid #dee2e6;
      transition: background-color 0.2s;
    }
    
    /* 鼠标悬停时行背景变色 */
    tbody tr:hover {
      background-color: #f8f9fa;
    }
    
    /* 表格单元格样式：内边距、右边框、自动换行 */
    td {
      padding: 6px 4px;
      border-right: 1px solid #dee2e6;
      word-break: break-word;
      white-space: nowrap;
    }
    
    /* 移除最后一列的右边框 */
    td:last-child {
      border-right: none;
    }
    
    /* ===== 列数据样式 ===== */
    /* 名称列：中等粗细、限制最大宽度、允许换行 */
    .name {
      font-weight: 500;
      color: #495057;
      max-width: 95px;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    
    /* 距离列：加粗、紫色、右对齐、较小字号 */
    .distance {
      font-weight: 600;
      color: #667eea;
      text-align: right;
      font-size: 9px;
    }
    
    /* 配速列：居中、紫色、等宽字体 */
    .pace {
      text-align: center;
      color: #764ba2;
      font-family: monospace;
      font-size: 9px;
    }
    
    /* 心率列：居中、红色 */
    .bpm {
      text-align: center;
      color: #e74c3c;
      font-size: 9px;
    }
    
    /* 时间列：居中、绿色、等宽字体 */
    .time {
      text-align: center;
      color: #27ae60;
      font-family: monospace;
      font-size: 9px;
    }
    
    /* 日期列：居中、灰色 */
    .date {
      text-align: center;
      color: #7f8c8d;
      font-size: 9px;
    }
    
    /* ===== 空状态样式 ===== */
    /* 无数据时显示样式：居中、大内边距、灰色文字 */
    .empty {
      text-align: center;
      padding: 40px;
      color: #95a5a6;
      font-size: 16px;
    }
    
    /* ===== 统计区域样式 ===== */
    /* 统计信息区域：浅灰背景、弹性布局、均匀分布 */
    .stats {
      background-color: #f8f9fa;
      padding: 8px 12px;
      display: flex;
      justify-content: space-around;
      border-top: 1px solid #dee2e6;
      font-size: 12px;
    }
    
    /* 统计文字样式 */
    .stats span {
      font-size: 13px;
      color: #495057;
    }
    
    /* 单个统计项居中 */
    .stat-item {
      text-align: center;
    }
    
    /* 统计数值样式：加粗、紫色、大字号 */
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
      <p>Powered by <span style="monospace; color: #e6f91e;">RunningPage</span></p>
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
