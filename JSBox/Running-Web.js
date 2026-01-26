/**
 * JSBox 跑步数据 Web 视图
 * 
 * 功能说明:
 * - 从共享目录读取跑步数据缓存
 * - 显示跑步数据的 HTML 表格
 * - 支持按类型过滤和日期排序
 * - 支持点击列头进行升序/降序排序
 * - 支持深色模式切换
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
 * @param {boolean} isDarkMode - 是否深色模式
 * @returns {string} HTML 字符串
 */
function generateTableHTML(activities, isDarkMode) {
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
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    /* ===== 页面主体样式 ===== */
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: #f5f5f5;
      padding: 12px;
      color: #333;
      transition: background-color 0.3s, color 0.3s;
    }
    
    /* ===== 深色模式样式 (通过类名控制) ===== */
    body.dark-mode {
      background-color: #000000;
      color: #e5e5e5;
    }
    
    body.dark-mode .container {
      background: #1c1c1e;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.6);
    }
    
    body.dark-mode .header {
      background: linear-gradient(135deg, #5568d3 0%, #6b4fa0 100%);
    }
    
    body.dark-mode thead {
      background-color: #2c2c2e;
      border-bottom: 2px solid #3a3a3c;
    }
    
    body.dark-mode th {
      color: #a8a8aa;
      border-right: 1px solid #3a3a3c;
    }
    
    body.dark-mode th.sortable {
      background-color: #2a3f5f;
    }
    
    body.dark-mode th.sortable:hover {
      background-color: #3a5278;
    }
    
    body.dark-mode th.sort-desc {
      color: #ff6b6b;
    }
    
    body.dark-mode th.sort-asc {
      color: #51cf66;
    }
    
    body.dark-mode tbody tr {
      border-bottom: 1px solid #3a3a3c;
    }
    
    body.dark-mode tbody tr:hover {
      background-color: #2c2c2e;
    }
    
    body.dark-mode td {
      border-right: 1px solid #3a3a3c;
      color: #e5e5e5;
    }
    
    body.dark-mode .name {
      color: #d1d1d6;
    }
    
    body.dark-mode .distance {
      color: #7b8cff;
    }
    
    body.dark-mode .pace {
      color: #b197fc;
    }
    
    body.dark-mode .bpm {
      color: #ffa94d;
    }
    
    body.dark-mode .time {
      color: #4fc3f7;
    }
    
    body.dark-mode .date {
      color: #a0a0a5;
    }
    
    body.dark-mode .empty {
      color: #6c6c70;
    }
    
    body.dark-mode .stats {
      background-color: #2c2c2e;
      border-top: 1px solid #3a3a3c;
    }
    
    body.dark-mode .stats span {
      color: #a8a8aa;
    }
    
    body.dark-mode .stat-value {
      color: #7b8cff;
    }
    
    /* ===== 主容器样式 ===== */
    .container {
      max-width: 100%;
      margin: 0 auto;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      overflow: hidden;
      transition: background 0.3s, box-shadow 0.3s;
    }
    
    /* ===== 头部区域样式 ===== */
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 16px;
      text-align: center;
      transition: background 0.3s;
    }
    
    .header h1 {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 4px;
    }
    
    .header p {
      font-size: 12px;
      opacity: 0.9;
    }
    
    /* ===== 数据表格样式 ===== */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10px;
    }
    
    thead {
      background-color: #f8f9fa;
      border-bottom: 2px solid #e9ecef;
      transition: background-color 0.3s, border-color 0.3s;
    }
    
    th {
      padding: 6px 4px;
      text-align: left;
      font-weight: 600;
      color: #495057;
      border-right: 1px solid #dee2e6;
      user-select: none;
      position: relative;
      transition: all 0.2s;
    }
    
    th.sortable {
      cursor: pointer;
      background-color: #e3f2fd;
    }
    
    th.sortable:hover {
      background-color: #bbdefb;
    }
    
    th:last-child {
      border-right: none;
    }
    
    th.sort-desc {
      color: #e74c3c;
      font-weight: 700;
    }
    
    th.sort-asc {
      color: #27ae60;
      font-weight: 700;
    }
    
    tbody tr {
      border-bottom: 1px solid #dee2e6;
      transition: background-color 0.2s, border-color 0.3s;
    }
    
    tbody tr:hover {
      background-color: #f8f9fa;
    }
    
    td {
      padding: 6px 4px;
      border-right: 1px solid #dee2e6;
      word-break: break-word;
      white-space: nowrap;
      transition: border-color 0.3s, color 0.3s;
    }
    
    td:last-child {
      border-right: none;
    }
    
    /* ===== 列数据样式 ===== */
    .name {
      font-weight: 500;
      color: #495057;
      max-width: 95px;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
      transition: color 0.3s;
    }
    
    .distance {
      font-weight: 600;
      color: #667eea;
      text-align: right;
      font-size: 9px;
      transition: color 0.3s;
    }
    
    .pace {
      text-align: center;
      color: #764ba2;
      font-size: 9px;
      transition: color 0.3s;
    }
    
    .bpm {
      text-align: center;
      color: #e74c3c;
      font-size: 9px;
      transition: color 0.3s;
    }
    
    .time {
      text-align: center;
      color: #27ae60;
      font-size: 9px;
      transition: color 0.3s;
    }
    
    .date {
      text-align: center;
      color: #7f8c8d;
      font-size: 9px;
      transition: color 0.3s;
    }
    
    /* ===== 空状态样式 ===== */
    .empty {
      text-align: center;
      padding: 40px;
      color: #95a5a6;
      font-size: 16px;
      transition: color 0.3s;
    }
    
    /* ===== 统计区域样式 ===== */
    .stats {
      background-color: #f8f9fa;
      padding: 8px 12px;
      display: flex;
      justify-content: space-around;
      border-top: 1px solid #dee2e6;
      font-size: 12px;
      transition: background-color 0.3s, border-color 0.3s;
    }
    
    .stats span {
      font-size: 13px;
      color: #495057;
      transition: color 0.3s;
    }
    
    .stat-item {
      text-align: center;
    }
    
    .stat-value {
      font-weight: 600;
      color: #667eea;
      display: block;
      font-size: 16px;
      transition: color 0.3s;
    }
  </style>
</head>
<body${isDarkMode ? ' class="dark-mode"' : ''}>
  <div class="container">
    <div class="header">
      <h1>Data View</h1>
      <p>Powered by <span style="font-family: monospace; color: #e6f91e;">RunningPage</span></p>
    </div>
  `;
  
  if (runs.length === 0) {
    html += '<div class="empty">暂无跑步数据</div>';
  } else {
    html += `
    <table id="runTable">
      <thead>
        <tr>
          <th>Name</th>
          <th data-sort="distance" class="sortable">Km</th>
          <th data-sort="pace" class="sortable">Pace</th>
          <th data-sort="bpm" class="sortable">BPM</th>
          <th data-sort="time" class="sortable">Time</th>
          <th data-sort="date" class="sortable sort-desc">Date</th>
        </tr>
      </thead>
      <tbody id="tableBody">
    `;
    
    runs.forEach(run => {
      const distanceKm = (run.distance / 1000).toFixed(2);
      const pace = calculatePace(run.distance, run.moving_time);
      const heartrate = run.average_heartrate ? Math.round(run.average_heartrate) : "N/A";
      const date = formatDateWeb(run.start_date_local);
      
      html += `
        <tr data-distance="${run.distance}" 
            data-pace="${pace !== 'N/A' ? pace : '999:99'}" 
            data-bpm="${heartrate !== 'N/A' ? heartrate : '0'}"
            data-time="${run.moving_time}"
            data-date="${run.start_date_local}"
            data-name="${(run.name || 'Running').toLowerCase()}">
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
    
    <script>
      // 排序状态
      let currentSort = 'date';
      let sortDirection = 'desc';
      
      // 获取所有可排序的表头
      const headers = document.querySelectorAll('th[data-sort]');
      
      // 为每个表头添加点击事件
      headers.forEach(header => {
        header.addEventListener('click', () => {
          const sortKey = header.dataset.sort;
          
          // 如果点击的是当前排序列，切换排序方向
          if (currentSort === sortKey) {
            sortDirection = sortDirection === 'desc' ? 'asc' : 'desc';
          } else {
            // 否则，设置新的排序列，默认降序
            currentSort = sortKey;
            sortDirection = 'desc';
          }
          
          // 更新表头样式
          headers.forEach(h => {
            h.classList.remove('sort-asc', 'sort-desc');
          });
          header.classList.add('sort-' + sortDirection);
          
          // 执行排序
          sortTable(sortKey, sortDirection);
        });
      });
      
      // 排序函数
      function sortTable(key, direction) {
        const tbody = document.getElementById('tableBody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
          let aVal, bVal;
          
          switch(key) {
            case 'name':
              aVal = a.dataset.name;
              bVal = b.dataset.name;
              return direction === 'desc' 
                ? bVal.localeCompare(aVal)
                : aVal.localeCompare(bVal);
              
            case 'distance':
              aVal = parseFloat(a.dataset.distance);
              bVal = parseFloat(b.dataset.distance);
              break;
              
            case 'pace':
              aVal = a.dataset.pace;
              bVal = b.dataset.pace;
              // 将配速转换为秒数进行比较
              const aPaceSeconds = paceToSeconds(aVal);
              const bPaceSeconds = paceToSeconds(bVal);
              return direction === 'desc'
                ? bPaceSeconds - aPaceSeconds
                : aPaceSeconds - bPaceSeconds;
              
            case 'bpm':
              aVal = parseFloat(a.dataset.bpm);
              bVal = parseFloat(b.dataset.bpm);
              break;
              
            case 'time':
              aVal = a.dataset.time;
              bVal = b.dataset.time;
              const aTimeSeconds = timeToSeconds(aVal);
              const bTimeSeconds = timeToSeconds(bVal);
              return direction === 'desc'
                ? bTimeSeconds - aTimeSeconds
                : aTimeSeconds - bTimeSeconds;
              
            case 'date':
              aVal = new Date(a.dataset.date).getTime();
              bVal = new Date(b.dataset.date).getTime();
              break;
          }
          
          return direction === 'desc' ? bVal - aVal : aVal - bVal;
        });
        
        // 清空并重新插入排序后的行
        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
      }
      
      // 将配速转换为秒数
      function paceToSeconds(pace) {
        if (pace === '999:99') return 999999; // N/A 值
        const parts = pace.split(':');
        return parseInt(parts[0]) * 60 + parseInt(parts[1]);
      }
      
      // 将时间转换为秒数
      function timeToSeconds(time) {
        const parts = time.split(':');
        const hours = parseInt(parts[0]) || 0;
        const minutes = parseInt(parts[1]) || 0;
        const seconds = parseFloat(parts[2]) || 0;
        return hours * 3600 + minutes * 60 + seconds;
      }
    </script>
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
  const isDarkMode = $device.isDarkMode;
  const html = generateTableHTML(activities, isDarkMode);
  
  const encodedHtml = encodeURIComponent(html);
  const dataUrl = `data:text/html;charset=utf-8,${encodedHtml}`;
  
  $ui.render({
    props: {
      title: "Data View",
      navBarHidden: true,
      statusBarStyle: isDarkMode ? 1 : 0
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