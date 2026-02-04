// Running Data - Main Entry
// 跑步数据统计小组件

const CONFIG = {
  CACHE_FILE: "shared://activities_cache.json",
  get DATA_URL() {
    return $cache.get("data_url") || "https://raw.githubusercontent.com/abingx/running_page/master/src/static/activities.json";
  },
  get TARGET_SCRIPT() {
    return $cache.get("target_script") || "Running Data.js";
  },
  get SHOW_PLACEHOLDERS() {
    return $cache.get("show_placeholders") || false;
  }
};

// 导出配置供其他模块使用
global.CONFIG = CONFIG;

// 加载主逻辑
require("scripts/widget-main");