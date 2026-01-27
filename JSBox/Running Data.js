/**
 * JSBox 跑步数据 Web 视图 - iOS 移动端优化版
 * 
 * 功能说明:
 * - 从共享目录读取跑步数据缓存
 * - 显示跑步数据的 HTML 表格（针对 iOS 优化）
 * - 支持按类型过滤和日期排序
 * - 支持点击列头进行升序/降序排序
 * - 支持深色模式切换
 * - 优化移动端字体和布局
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
 * 格式化日期 - 移动端简洁版
 * 
 * @param {string} dateStr - 日期字符串
 * @returns {string} 格式化后的日期 (格式: yy/mm/dd hh:mm)
 */
function formatDateWeb(dateStr) {
  const date = new Date(dateStr.replace(" ", "T"));
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}/${month}/${day} ${hours}:${minutes}`;
}

/**
 * 生成 HTML 表格 - iOS 移动端优化版
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <style>
    /* ===== CSS 变量定义 ===== */
    :root {
      /* 亮色模式 */
      --primary-gradient: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 50%, #FFA06B 100%);
      --secondary-gradient: linear-gradient(135deg, #4ECDC4 0%, #44A08D 100%);
      --header-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
      --accent-color: #FF6B6B;
      --success-color: #51CF66;
      --warning-color: #FFD93D;
      --info-color: #4ECDC4;
      --text-primary: #2C3E50;
      --text-secondary: #7F8C8D;
      --bg-primary: #FFFFFF;
      --bg-secondary: #F8F9FA;
      --bg-gradient: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
      --border-color: #E9ECEF;
      --shadow-color: rgba(0, 0, 0, 0.08);
      --hover-bg: rgba(102, 126, 234, 0.05);
      --card-bg: rgba(255, 255, 255, 0.95);
    }
    
    /* 深色模式变量 */
    .dark-mode {
      --primary-gradient: linear-gradient(135deg, #FF6B6B 0%, #FF5252 100%);
      --secondary-gradient: linear-gradient(135deg, #4ECDC4 0%, #3BA99C 100%);
      --header-gradient: linear-gradient(135deg, #5568d3 0%, #6b4fa0 50%, #d946ef 100%);
      --accent-color: #FF8787;
      --success-color: #69DB7C;
      --warning-color: #FFE066;
      --info-color: #66D9EF;
      --text-primary: #E9ECEF;
      --text-secondary: #ADB5BD;
      --bg-primary: #1A1B1E;
      --bg-secondary: #25262B;
      --bg-gradient: linear-gradient(135deg, rgba(85, 104, 211, 0.1) 0%, rgba(107, 79, 160, 0.1) 100%);
      --border-color: #373A40;
      --shadow-color: rgba(0, 0, 0, 0.4);
      --hover-bg: rgba(85, 104, 211, 0.15);
      --card-bg: rgba(26, 27, 30, 0.95);
    }
    
    /* ===== 全局样式重置 ===== */
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      -webkit-tap-highlight-color: transparent;
    }
    
    /* ===== 页面主体样式 ===== */
    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
      background: var(--bg-gradient);
      padding: 0;
      color: var(--text-primary);
      min-height: 100vh;
      position: relative;
      overflow-x: hidden;
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* 背景装饰层 */
    body::before {
      content: '';
      position: fixed;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: 
        radial-gradient(circle at 20% 80%, rgba(255, 107, 107, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 80% 20%, rgba(78, 205, 196, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(118, 75, 162, 0.05) 0%, transparent 50%);
      pointer-events: none;
      z-index: 0;
      animation: float 20s ease-in-out infinite;
    }
    
    @keyframes float {
      0%, 100% { transform: translate(0, 0) rotate(0deg); }
      33% { transform: translate(30px, -30px) rotate(5deg); }
      66% { transform: translate(-20px, 20px) rotate(-5deg); }
    }
    
    /* ===== 主容器样式 ===== */
    .container {
      position: relative;
      z-index: 1;
      max-width: 100%;
      margin: 0;
      background: var(--card-bg);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      overflow: hidden;
      animation: slideUp 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(30px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    /* ===== 头部区域样式 ===== */
    .header {
      background: var(--header-gradient);
      color: white;
      padding: 20px 16px 16px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }
    
    .header::before {
      content: '';
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: linear-gradient(
        45deg,
        transparent 30%,
        rgba(255, 255, 255, 0.1) 50%,
        transparent 70%
      );
      animation: shine 3s infinite;
    }
    
    @keyframes shine {
      0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
      100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
    }
    
    .header-content {
      position: relative;
      z-index: 1;
    }
    
    .header h1 {
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 6px;
      letter-spacing: -0.3px;
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      animation: fadeIn 0.8s ease-out 0.2s both;
    }
    
    .header p {
      font-size: 11px;
      opacity: 0.9;
      font-weight: 500;
      animation: fadeIn 0.8s ease-out 0.4s both;
    }
    
    .header .highlight {
      font-family: "SF Mono", "Monaco", "Courier New", monospace;
      color: #FFE66D;
      font-weight: 600;
      text-shadow: 0 0 20px rgba(255, 230, 109, 0.5);
    }
    
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    /* ===== 统计卡片样式 ===== */
    .stats {
      background: var(--bg-secondary);
      padding: 12px 10px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      border-bottom: 1px solid var(--border-color);
    }
    
    .stat-card {
      background: var(--bg-primary);
      padding: 10px 6px;
      border-radius: 10px;
      text-align: center;
      border: 1px solid var(--border-color);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      animation: scaleIn 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
    }
    
    .stat-card:nth-child(1) { animation-delay: 0.1s; }
    .stat-card:nth-child(2) { animation-delay: 0.2s; }
    .stat-card:nth-child(3) { animation-delay: 0.3s; }
    
    @keyframes scaleIn {
      from {
        opacity: 0;
        transform: scale(0.9);
      }
      to {
        opacity: 1;
        transform: scale(1);
      }
    }
    
    .stat-card:active {
      transform: scale(0.95);
    }
    
    .stat-label {
      font-size: 9px;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.3px;
      margin-bottom: 4px;
      font-weight: 600;
    }
    
    .stat-value {
      font-size: 17px;
      font-weight: 700;
      background: var(--primary-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      line-height: 1.2;
    }
    
    /* ===== 表格容器 ===== */
    .table-container {
      overflow-x: auto;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
    }
    
    /* 自定义滚动条 - iOS Safari */
    .table-container::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    
    .table-container::-webkit-scrollbar-track {
      background: transparent;
    }
    
    .table-container::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: 3px;
    }
    
    /* ===== 数据表格样式 ===== */
    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 11px;
    }
    
    thead {
      position: sticky;
      top: 0;
      z-index: 10;
      background: var(--bg-secondary);
      backdrop-filter: blur(10px);
      box-shadow: 0 1px 4px var(--shadow-color);
    }
    
    th {
      padding: 10px 4px;
      text-align: center;
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 2px solid var(--border-color);
      border-right: 1px solid var(--border-color);
      user-select: none;
      position: relative;
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      white-space: nowrap;
      line-height: 1.2;
    }
    
    th:first-child {
      text-align: left;
      padding-left: 8px;
    }
    
    th:last-child {
      border-right: none;
      padding-right: 8px;
    }
    
    th.sortable {
      cursor: pointer;
      background: linear-gradient(to bottom, var(--bg-secondary) 0%, var(--bg-primary) 100%);
    }
    
    th.sortable:active {
      background: var(--hover-bg);
      transform: scale(0.95);
    }
    
    th.sortable::after {
      content: '⇅';
      position: absolute;
      right: 2px;
      top: 50%;
      transform: translateY(-50%);
      opacity: 0.3;
      font-size: 10px;
      transition: all 0.3s;
    }
    
    th.sort-desc::after {
      content: '↓';
      opacity: 1;
      color: var(--accent-color);
    }
    
    th.sort-asc::after {
      content: '↑';
      opacity: 1;
      color: var(--success-color);
    }
    
    /* ===== 表格行样式 ===== */
    tbody tr {
      border-bottom: 1px solid var(--border-color);
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      animation: fadeInRow 0.4s ease-out both;
    }
    
    @keyframes fadeInRow {
      from {
        opacity: 0;
        transform: translateX(-10px);
      }
      to {
        opacity: 1;
        transform: translateX(0);
      }
    }
    
    tbody tr:active {
      background: var(--hover-bg);
    }
    
    td {
      padding: 8px 4px;
      border-right: 1px solid var(--border-color);
      transition: all 0.3s;
      text-align: center;
      line-height: 1.3;
    }
    
    td:first-child {
      text-align: left;
      padding-left: 8px;
    }
    
    td:last-child {
      border-right: none;
      padding-right: 8px;
    }
    
    /* ===== 列数据样式 ===== */
    .name {
      font-weight: 600;
      color: var(--text-primary);
      font-size: 10px;
      max-width: 100px;
      word-wrap: break-word;
      white-space: normal;
      line-height: 1.3;
    }
    
    .distance {
      font-weight: 700;
      background: var(--primary-gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      font-size: 11px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      text-align: right;
    }
    
    .pace {
      font-weight: 600;
      color: var(--info-color);
      font-size: 10px;
      font-family: "SF Mono", monospace;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      min-width: 40px;
    }
    
    .bpm {
      font-weight: 600;
      font-size: 10px;
      font-variant-numeric: tabular-nums;
    }
    
    .bpm-value {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 10px;
      background: linear-gradient(135deg, rgba(255, 107, 107, 0.15) 0%, rgba(255, 82, 82, 0.15) 100%);
      color: var(--accent-color);
      font-size: 10px;
      line-height: 1.2;
    }
    
    .time {
      font-weight: 600;
      color: var(--success-color);
      font-size: 10px;
      font-family: "SF Mono", monospace;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    
    .date {
      color: var(--text-secondary);
      font-size: 9px;
      font-variant-numeric: tabular-nums;
      line-height: 1.2;
      white-space: nowrap;
    }
    
    /* ===== 空状态样式 ===== */
    .empty {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-secondary);
      font-size: 14px;
    }
    
    .empty-icon {
      font-size: 40px;
      margin-bottom: 12px;
      opacity: 0.5;
    }
  </style>
</head>
<body${isDarkMode ? ' class="dark-mode"' : ''}>
  <div class="container">
    <div class="header">
      <div class="header-content">
        <h1>🏃‍♂️ Running Dashboard</h1>
        <p>Powered by <span class="highlight">RunningPage</span></p>
      </div>
    </div>
  `;
  
  if (runs.length === 0) {
    html += `
    <div class="empty">
      <div class="empty-icon">🏃</div>
      <p>暂无跑步数据</p>
    </div>
    `;
  } else {
    // 计算统计数据
    const totalDistance = runs.reduce((sum, run) => sum + run.distance, 0);
    const totalRuns = runs.length;
    const avgDistance = totalDistance / totalRuns / 1000;
    
    html += `
    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Total</div>
        <div class="stat-value">${totalRuns}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Km</div>
        <div class="stat-value">${(totalDistance / 1000).toFixed(1)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Km</div>
        <div class="stat-value">${avgDistance.toFixed(2)}</div>
      </div>
    </div>
    
    <div class="table-container">
      <table id="runTable">
        <thead>
          <tr>
            <th>Name</th>
            <th data-sort="distance" class="sortable">KM</th>
            <th data-sort="pace" class="sortable">Pace</th>
            <th data-sort="bpm" class="sortable">BPM</th>
            <th data-sort="time" class="sortable">Time</th>
            <th data-sort="date" class="sortable sort-desc">Date</th>
          </tr>
        </thead>
        <tbody id="tableBody">
    `;
    
    runs.forEach((run, index) => {
      const distanceKm = (run.distance / 1000).toFixed(2);
      const pace = calculatePace(run.distance, run.moving_time);
      const heartrate = run.average_heartrate ? Math.round(run.average_heartrate) : "N/A";
      const date = formatDateWeb(run.start_date_local);
      const movingTime = run.moving_time.split(".")[0];
      
      html += `
        <tr data-distance="${run.distance}" 
            data-pace="${pace !== 'N/A' ? pace : '999:99'}" 
            data-bpm="${heartrate !== 'N/A' ? heartrate : '0'}"
            data-time="${run.moving_time}"
            data-date="${run.start_date_local}"
            data-name="${(run.name || 'Running').toLowerCase()}"
            style="animation-delay: ${index * 0.02}s">
          <td class="name" title="${run.name || 'Running'}">${run.name || 'Running'}</td>
          <td class="distance">${distanceKm}</td>
          <td class="pace">${pace}</td>
          <td class="bpm">${heartrate !== 'N/A' ? `<span class="bpm-value">${heartrate}</span>` : 'N/A'}</td>
          <td class="time">${movingTime}</td>
          <td class="date">${date}</td>
        </tr>
      `;
    });
    
    html += `
        </tbody>
      </table>
    </div>
    
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
        
        // 清空并重新插入排序后的行，添加动画延迟
        tbody.innerHTML = '';
        rows.forEach((row, index) => {
          row.style.animationDelay = (index * 0.015) + 's';
          tbody.appendChild(row);
        });
      }
      
      // 将配速转换为秒数
      function paceToSeconds(pace) {
        if (pace === '999:99') return 999999;
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
      title: "Running Dashboard",
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