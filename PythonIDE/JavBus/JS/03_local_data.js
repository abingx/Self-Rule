// ============================================================
// 03_local_data.js — 本地数据持久化（收藏 / 归档 / 演员等）
// 转写说明：对应 Python 中的 storage.py / db.py
//   - $file.read() / $file.write() → Python: open() / json.load() / json.dump()
//   - $cache.get() / $cache.set() → Python: shelve 或 json 缓存文件
//   - 数据结构：LocalData 是核心 JSON 对象，对应 Python dict
// ============================================================

// ---- 初始化本地数据（应用启动时调用） ----
// Python 转写：
//   def load_local_data(path: str) -> dict:
//       if os.path.exists(path):
//           with open(path) as f: return json.load(f)
//       else: return {empty_structure}
function initial() {
  var current = $addin.current;
  current.author = "Nicked";
  current.website = "https://t.me/nicked";
  current.version = version;

  if ($file.read(LocalDataPath)) {
    // Python: LocalData = json.load(open(LOCAL_DATA_PATH))
    LocalData = JSON.parse($file.read(LocalDataPath).string);
    LocalFavList      = LocalData.favorite.map(i => i.shortCode);
    LocalArcList      = LocalData.archive.map(i => i.shortCode);
    LocalActressList  = LocalData.actress.map(i => i.shortCode);
    LocalDirectorList = LocalData.director.map(i => i.shortCode);
    LocalFilmMakerList= LocalData.filmMaker.map(i => i.shortCode);
    LocalFilmEstabList= LocalData.filmEstab.map(i => i.shortCode);
    if (!LocalData.series) LocalData.series = [];
    LocalSeriesList   = LocalData.series.map(i => i.shortCode);
  } else {
    // Python: 创建空数据结构
    LocalData = {
      favorite: [],
      actress:  [],
      archive:  [],
      director: [],
      filmMaker:[],
      filmEstab:[],
      series:   []
    };
    LocalFavList       = [];
    LocalArcList       = [];
    LocalActressList   = [];
    LocalDirectorList  = [];
    LocalFilmMakerList = [];
    LocalFilmEstabList = [];
    LocalSeriesList    = [];
  }

  mode    = "home";
  keyword = "";

  scriptVersionUpdate();
  // UI 初始化（Python：此处替换为 UI 框架的对应调用）
  $("JavBus").add(searchView(180));
  if ($cache.get("samp") === undefined) readMe();
  getNewRec("Author");
}

// ---- 写入本地缓存文件 ----
// Python 转写：
//   def write_cache():
//       with open(LOCAL_DATA_PATH, "w") as f:
//           json.dump(local_data, f, ensure_ascii=False)
function writeCache() {
  $file.write({
    data: $data({ string: JSON.stringify(LocalData) }),
    path: LocalDataPath
  });
}

// ---- 收藏 / 归档操作 ----
// mode: "add" | "cancel" | "archive" | "del"
// Python 转写：
//   def favorite_button_tapped(mode: str, data: dict):
//       ...
//       write_cache()
function favoriteButtonTapped(mode, data) {
  if (mode == "add") {
    LocalData.favorite.unshift(data);
    LocalFavList.unshift(data.shortCode);
    // UI 更新（Python 层单独处理）
    if (!$context.query.code && $("menu").index == 4 && $("tab").index == 0) {
      $("initialView").data = $("initialView").data.concat({
        link: homepage + data.shortCode,
        code: data.code,
        initialCover: {
          src: data.src,
          source: { url: data.src, header: cookieHeader }
        },
        info: { text: data.info }
      });
      $("input").placeholder = "已收藏 " + LocalFavList.length + " 部影片";
    }
  } else if (mode == "cancel") {
    if (!isInToday()) $ui.pop();
    var idx = LocalFavList.indexOf(data.shortCode);
    LocalFavList.splice(idx, 1);
    LocalData.favorite.splice(idx, 1);
  } else if (mode == "archive") {
    if (!isInToday()) $ui.pop();
    var idx = LocalFavList.indexOf(data.shortCode);
    LocalFavList.splice(idx, 1);
    LocalData.favorite.splice(idx, 1);
    if ($("menu").index == 4) {
      $("initialView").delete(idx);
      $("input").placeholder = "已收藏 " + LocalFavList.length + " 部影片";
    } else if ($("menu").index == 5) {
      $("initialView").data = [{
        link: homepage + data.shortCode,
        code: data.code,
        initialCover: { src: data.src, source: { url: data.src, header: cookieHeader } },
        info: { text: data.info }
      }].concat($("initialView").data);
      $("input").placeholder = "已归档 " + LocalArcList.length + " 部影片";
    }
    LocalData.archive.unshift(data);
    LocalArcList.unshift(data.shortCode);
  } else if (mode == "del") {
    $ui.pop();
    var idx = LocalArcList.indexOf(data.shortCode);
    LocalArcList.splice(idx, 1);
    LocalData.archive.splice(idx, 1);
    if ($("menu").index == 5) {
      $("initialView").delete(idx);
      $("input").placeholder = "已归档 " + LocalArcList.length + " 部影片";
    }
  }
  writeCache();
}

// ---- 演员收藏操作 ----
// Python 转写：类似 favorite_button_tapped，操作 actress/director/series 等列表
function favActressButtonTapped(mode, data) {
  // mode: "add" | "cancel"，根据 $("tab").index 决定操作哪个列表
  // Python：传入 list_type 参数区分（"actress"/"director"/"filmMaker"/"filmEstab"/"series"）
  let position = $("tab").index; // 2=director, 3=series, 4=filmMaker, 5=filmEstab, else=actress
  let listMap = {
    actress:   [LocalActressList,   LocalData.actress],
    director:  [LocalDirectorList,  LocalData.director],
    series:    [LocalSeriesList,    LocalData.series],
    filmMaker: [LocalFilmMakerList, LocalData.filmMaker],
    filmEstab: [LocalFilmEstabList, LocalData.filmEstab]
  };
  // 具体 add/cancel 逻辑与 favoriteButtonTapped 一致，省略 UI 部分
  // 详见原文件 4765-4803 行
  writeCache();
}
