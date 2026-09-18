import atexit
import hashlib
import math
import os
import re
import shutil
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import appui
import database
import shortcuts

try:
    from objc_util import ObjCClass, on_main_thread
except ImportError:
    ObjCClass = None
    on_main_thread = None


def probe_writable(directory):
    """实际试写一次，比 os.access 在沙箱里更可靠。"""
    probe = Path(directory) / ("." + uuid.uuid4().hex + ".probe")
    try:
        with probe.open("xb") as handle:
            handle.write(b"ok")
    except OSError:
        return False
    try:
        probe.unlink()
    except OSError:
        pass
    return True


def resolve_data_dir():
    """数据目录＝当前目录（项目目录本身）。

    宿主会把项目快照到 MiniAppRunSnapshot-*/Root 再执行，所以 __file__ 指向快照，
    不能用来定位项目。JavVault 的 favorites.json / miniapp.json 同样是按 os.getcwd()
    存取的，这里保持一致；当前目录不可写时依次退回 __file__ 目录与宿主数据目录。
    """
    candidates = [Path.cwd()]
    try:
        candidates.append(Path(__file__).resolve().parent)
    except NameError:
        pass
    for directory in candidates:
        if probe_writable(directory):
            return directory, ""
    try:
        fallback = Path(database.database_path("hearth.data")).resolve().parent
    except Exception as exc:
        return Path.cwd(), f"未找到可写目录（{exc}），数据可能无法保存。"
    return fallback, "项目目录不可写，数据已改存宿主数据目录。"


APP_DIR, DATA_NOTE = resolve_data_dir()
DB_PATH = APP_DIR / "database.db"                  # 工作库：首次运行与重置数据库都由内置初始数据生成
BACKUP_PATH = APP_DIR / "backup.db"                # 备份固定用这个文件名，不做其它命名
ROW_FIELDS = {"ingredients", "prep", "operations", "notes"}
FOOD_CATALOG = {
    "肉类": {
        "猪": ["猪五花肉", "猪前腿肉", "猪瘦肉", "猪肥膘", "猪肉末", "猪排骨", "猪蹄", "猪肚", "猪肝",
               "猪肥肠", "猪黄喉", "猪前蹄", "猪后蹄", "猪耳朵", "猪心"],
        "牛": ["牛肉", "牛吊龙", "牛肋条", "牛里脊", "牛胸膘", "牛腱子"],
        "羊": ["羊肉", "羊排", "羊腿"],
        "鸡": ["整鸡", "鸡腿", "鸡翅", "鸡胸肉", "鸡爪"],
        "鸭": ["整鸭", "鸭胗"],
        "兔": ["整兔"],
        "鱼": ["草鱼", "鲤鱼", "乌鱼", "鳝鱼", "带鱼", "鲈鱼", "黄花鱼", "多宝鱼", "耗儿鱼"],
        "加工肉制品": ["腊排骨", "酥肉", "油渣", "火腿肠", "午餐肉"],
    },
    "水产": {
        "虾": ["对虾", "罗氏虾", "斑节虾"],
        "贝类": ["花甲", "鲍鱼", "蛏子"],
    },
    "蛋豆类": {
        "蛋": ["鸡蛋", "鹌鹑蛋", "鸭蛋", "鹅蛋", "咸鸭蛋", "皮蛋"],
        "豆制品": ["豆腐", "豆花", "豆干", "豆皮", "腐竹"],
        "豆类": ["青豆", "豆芽"],
    },
    "蔬菜类": {
        "叶类": ["大白菜", "白菜梗", "生菜", "空心菜", "豌豆尖", "韭黄", "芹菜", "白芹菜", "香菜",
                 "蒜苗", "青蒜叶", "青菜苔"],
        "根茎类": ["土豆", "胡萝卜", "黄萝卜", "莲藕", "莴笋", "竹笋", "罗汉笋", "洋葱", "白洋葱"],
        "果实类": ["番茄", "黄瓜", "茄子", "苦瓜", "秋葵", "冬瓜", "青椒", "红椒", "甜椒", "二荆条",
                  "小米辣", "杭椒", "美人椒", "柠檬", "百香果"],
        "花菜类": ["花菜", "西兰花"],
        "菌菇类": ["口蘑", "杏鲍菇", "平菇", "香菇", "金针菇", "鹿茸菇", "鸡油菌", "木耳"],
    },
    "主食干货": {
        "米面": ["大米"],
        "粉条粉丝": ["粉丝", "粉条", "红薯粉条", "龙口粉丝", "红薯粉块"],
        "干货": ["枸杞", "白芝麻", "葡萄干", "酸菜", "泡青菜"],
    },
    "调味料": {
        "咸鲜调料": ["盐", "生抽", "老抽", "酱油", "红酱油", "蚝油", "味精", "鸡精", "鸡粉", "松茸鲜"],
        "糖类": ["白糖", "红糖", "冰糖", "黄冰糖"],
        "油脂": ["食用油", "猪油", "香油", "芝麻香油", "花生油", "菜籽油", "色拉油", "调和油", "豆油",
                 "红油", "辣椒油", "花椒油", "藤椒油", "山胡椒油"],
        "醋类": ["醋", "陈醋", "香醋", "白醋"],
        "淀粉": ["淀粉", "玉米淀粉", "土豆淀粉", "豌豆淀粉", "红薯粉", "生粉", "水淀粉"],
        "酒类": ["料酒", "黄酒", "啤酒", "白酒", "包谷酒", "米酒", "醪糟"],
        "葱姜蒜": ["葱", "姜", "仔姜", "蒜"],
        "香辛料": ["花椒", "青花椒", "花椒粉", "干辣椒", "辣椒面", "辣椒粉", "刀口辣椒", "丘北辣椒",
                   "糊辣椒面", "八角", "桂皮", "香叶", "小茴香", "草果", "香奈", "孜然粉", "白胡椒粉",
                   "黑胡椒粉"],
        "酱料": ["豆瓣酱", "豆豉", "泡椒", "泡姜", "野山椒", "黄灯笼辣椒酱", "青花椒酱", "火锅底料",
                 "剁椒", "辣鲜露"],
        "其他": ["小苏打"],
    },
}
TWO_LEVEL_TYPES = set()          # 当前目录里每个一级分类都有三级；若将来新增只有两级的分类，加到这里
FOOD_LEVELS = ("一级", "二级", "三级")     # 新增食材弹窗可选的层级
OPTION_TABLES = ("categories", "tags")
DEFAULT_CATEGORIES = ["炒菜", "烧菜", "炖菜", "凉拌菜", "蒸菜", "汤菜", "主食"]
DEFAULT_TAGS = ["川菜", "粤菜", "湘菜", "鲁菜", "家常", "快手"]
SCHEMA_VERSION = 3
PAGER_ROW_H = 56            # 分页条高度（按钮 44 + 上下留白）
PAGER_FONT = "subheadline"   # 分页条统一字体
PAGER_GAP = 4                # 「第 / 页码 / / N 页」之间的等距间距
PAGER_NUMBER_W = 34          # 页码输入框固定宽度：数字居中，左右留白对称
PAGER_NUMBER_H = 32
RECIPE_ROW_H = 72           # 单条清单行的估算高度
LIST_CHROME_H = 172         # 搜索栏 + 筛选区 + 分节标题与内边距
FALLBACK_PAGE_SIZE = 6      # 尚未测量到尺寸时的每页条数
RECIPES_TABLE = ("CREATE TABLE IF NOT EXISTS recipes (id TEXT PRIMARY KEY, title TEXT NOT NULL,"
                 " video_url TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',"
                 " prep TEXT NOT NULL DEFAULT '', operations TEXT NOT NULL DEFAULT '',"
                 " servings INTEGER NOT NULL DEFAULT 2, minutes INTEGER NOT NULL DEFAULT 0,"
                 " rating INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0)")
SCHEMA_STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS tags (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS ingredients (id TEXT PRIMARY KEY, food_type TEXT NOT NULL,"
    " parent TEXT NOT NULL DEFAULT '', variety TEXT NOT NULL DEFAULT '', name TEXT NOT NULL,"
    " aisle TEXT NOT NULL DEFAULT '其他')",
    RECIPES_TABLE,
    "CREATE TABLE IF NOT EXISTS recipe_ingredients (recipe_id TEXT NOT NULL, position INTEGER NOT NULL,"
    " ingredient_id TEXT NOT NULL DEFAULT '', name TEXT NOT NULL, food_type TEXT NOT NULL DEFAULT '',"
    " parent TEXT NOT NULL DEFAULT '', variety TEXT NOT NULL DEFAULT '', quantity REAL,"
    " unit TEXT NOT NULL DEFAULT '', aisle TEXT NOT NULL DEFAULT '其他', PRIMARY KEY (recipe_id, position))",
    "CREATE TABLE IF NOT EXISTS recipe_categories (recipe_id TEXT NOT NULL, category_id TEXT NOT NULL,"
    " PRIMARY KEY (recipe_id, category_id))",
    "CREATE TABLE IF NOT EXISTS recipe_tags (recipe_id TEXT NOT NULL, tag_id TEXT NOT NULL,"
    " PRIMARY KEY (recipe_id, tag_id))",
    "CREATE INDEX IF NOT EXISTS recipe_ingredients_recipe ON recipe_ingredients(recipe_id)",
    "CREATE INDEX IF NOT EXISTS recipes_title ON recipes(title)",
)


def clone_catalog(catalog=None):
    source = FOOD_CATALOG if catalog is None else catalog
    return {food_type: {parent: list(varieties) for parent, varieties in parents.items()}
            for food_type, parents in source.items()}


def catalog_types(catalog):
    return list(catalog)


def catalog_parents(catalog, food_type):
    return list(catalog.get(food_type, {}))


def catalog_varieties(catalog, food_type, parent):
    return list(catalog.get(food_type, {}).get(parent, []))


def has_third_level(food_type):
    return food_type not in TWO_LEVEL_TYPES


def ingredient_name(food_type, parent, variety):
    """食材显示名：目录里的三级名称已是完整名称（如「猪五花肉」）；只有两级的分类用二级名。"""
    if not has_third_level(food_type):
        return parent
    return variety


def resolve_food_selection(food_type, parent, variety):
    """把（一级, 二级, 三级）规整到目录里真实存在的组合，取不到时退到首项或空。"""
    if food_type not in store.catalog:
        food_type = next(iter(store.catalog))
    parents = catalog_parents(store.catalog, food_type)
    if parent not in parents:
        parent = parents[0] if parents else ""
    if not parent or not has_third_level(food_type):
        return food_type, parent, ""
    varieties = catalog_varieties(store.catalog, food_type, parent)
    if variety not in varieties:
        variety = varieties[0] if varieties else ""
    return food_type, parent, variety


class RecipeStore:
    def __init__(self):
        self.loaded = False
        self.fingerprint = None
        self.lock = threading.RLock()
        self.catalog = clone_catalog()
        self.categories = list(DEFAULT_CATEGORIES)
        self.tags = list(DEFAULT_TAGS)

    def fingerprint_now(self):
        restore_backup()
        if not DB_PATH.exists():
            placeholder = DB_PATH.with_name("." + DB_PATH.name + ".icloud")
            if self.loaded or BACKUP_PATH.exists() or placeholder.exists():
                raise ValueError("数据库缺失或未下载，请先在“文件”中恢复或下载 database.db。")
            return None
        for suffix in ("-wal", "-journal"):
            path = Path(str(DB_PATH) + suffix)
            if path.exists() and path.stat().st_size:
                raise ValueError("请先关闭其他数据库编辑工具，再重载数据库。")
        return file_digest(DB_PATH)

    def exchange(self, recipe=None, catalog=None, names=None, remove_id=None):
        with self.lock:
            before = self.fingerprint_now()
            writing = recipe is not None or catalog is not None or names is not None or bool(remove_id)
            if writing and (not self.loaded or self.fingerprint != before):
                raise ValueError("文件已有外部更新，未覆盖数据。请取消编辑、下拉刷新后重试。")
            name = "recipe_work_" + uuid.uuid4().hex
            work = Path(database.database_path(name))
            db = None
            keep_work = False
            try:
                db = database.open(name)
                work = work_path(name)
                if before is not None:
                    db.close()
                    shutil.copyfile(DB_PATH, work)
                    db = database.open(name)
                if db.scalar("PRAGMA quick_check") != "ok":
                    raise ValueError("数据库完整性检查失败，请恢复备份。")
                version = int(db.scalar("PRAGMA user_version") or 0)
                tables = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}
                # 只接受本应用生成的库：空库（尚无表）或版本号一致；其它文件一律不动
                if tables and version != SCHEMA_VERSION:
                    raise ValueError("数据库版本不兼容，请保留原文件，或执行“重置数据库”重新生成。")
                db.execute("PRAGMA journal_mode = DELETE")
                db.execute("PRAGMA synchronous = FULL")
                with db.transaction():
                    create_schema(db)
                    seed_options(db)
                    if names:
                        for table, values in names.items():
                            if table not in OPTION_TABLES:
                                raise ValueError("目录类型无效。")
                            for value in text_list(values):
                                ensure_named_row(db, table, value)
                    if catalog is not None:
                        validate_catalog(catalog)
                        write_ingredients(db, catalog)
                    elif not db.query("SELECT 1 FROM ingredients LIMIT 1"):
                        write_ingredients(db, FOOD_CATALOG)
                    if remove_id:
                        delete_recipe(db, remove_id)
                    if recipe is not None:
                        write_recipe(db, normalize_recipe(recipe))
                db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                loaded_catalog = read_ingredients(db) or clone_catalog()
                self.categories = read_named(db, "categories")
                self.tags = read_named(db, "tags")
                result = read_recipes(db)
                db.close()
                db = None
                if writing or before is None:
                    keep_work = True
                    self.publish(work, before)
                    keep_work = False
                elif self.fingerprint_now() != before:
                    raise ValueError("读取期间数据库发生变化，请重载数据库。")
                else:
                    self.fingerprint = before
                self.loaded = True
                self.catalog = clone_catalog(loaded_catalog)
                return result
            except Exception as exc:
                if keep_work:
                    raise RuntimeError(f"{exc}\n未发布的修改保留在：{work}") from exc
                raise
            finally:
                if db is not None:
                    db.close()
                if not keep_work:
                    for suffix in ("", "-wal", "-shm", "-journal"):
                        remove_temp(Path(str(work) + suffix))

    def publish(self, work, before):
        temp = DB_PATH.with_name("." + uuid.uuid4().hex + ".tmp")
        try:
            with work.open("rb") as source, temp.open("xb") as target:
                shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
            digest = file_digest(temp)
            if self.fingerprint_now() != before:
                raise ValueError("检测到外部修改，保存已取消。")
            if before is not None:
                backup_temp = BACKUP_PATH.with_name("." + uuid.uuid4().hex + ".backup.tmp")
                try:
                    shutil.copyfile(DB_PATH, backup_temp)
                    os.replace(backup_temp, BACKUP_PATH)
                finally:
                    remove_temp(backup_temp)
            if self.fingerprint_now() != before:
                raise ValueError("检测到外部修改，保存已取消。")
            os.replace(temp, DB_PATH)
            self.fingerprint = digest
        finally:
            remove_temp(temp)

    def reset(self):
        """重置数据库：删掉工作库/备份/边车，直接生成全新的 database.db，再重新读取并校验结果。

        不依赖“库文件缺失后再由 exchange 顺带生成”的隐式路径：那种情况下若旧文件没删掉，
        会静默地重新读回旧数据（表现为“提示成功但什么都没变”）。这里逐步校验，删不掉或
        生成后仍能读到菜谱都直接报错。
        """
        with self.lock:
            remove_temp(DB_PATH)
            remove_sidecars(DB_PATH)
            remove_temp(BACKUP_PATH)
            remove_sidecars(BACKUP_PATH)
            if DB_PATH.exists():
                raise ValueError("旧数据库文件删除失败，请先关闭其它数据库工具后重试。")
            build_database(DB_PATH)
            file_digest(DB_PATH)          # 生成结果必须是有效的 SQLite 库
            self.loaded = False
            self.fingerprint = None
            recipes = self.exchange()
            if recipes:
                raise ValueError("生成后仍读到旧菜谱，请重试或手动删除 " + DB_PATH.name + "。")
            return recipes


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError("食材目录格式错误。")
    for food_type, parents in catalog.items():
        if not isinstance(food_type, str) or not food_type.strip():
            raise ValueError("食材一级分类无效。")
        if not isinstance(parents, dict):
            raise ValueError("食材二级分类无效。")
        for parent, varieties in parents.items():
            if not isinstance(parent, str) or not parent.strip():
                raise ValueError("食材二级分类无效。")
            if not isinstance(varieties, list) or not all(
                isinstance(item, str) and item.strip() for item in varieties
            ):
                raise ValueError("食材品种无效。")


def restore_backup():
    """主库缺失但备份仍在时自动恢复，避免卡在“数据库缺失”。"""
    if DB_PATH.exists() or not BACKUP_PATH.exists():
        return
    try:
        copy_database(BACKUP_PATH, DB_PATH)
    except OSError:
        pass


def copy_database(source, target):
    """整库复制：先写临时文件并 fsync，再原子替换，保证副本完整、不留半截文件。"""
    temp = target.with_name("." + uuid.uuid4().hex + ".copy.tmp")
    try:
        with source.open("rb") as src, temp.open("xb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp, target)
    finally:
        remove_temp(temp)


def remove_sidecars(path):
    """清掉 SQLite 边车文件，避免旧日志把已还原的数据再带回来。"""
    for suffix in ("-wal", "-journal", "-shm"):
        remove_temp(Path(str(path) + suffix))


def build_database(target=None):
    """按内置初始数据直接生成一份全新数据库：表结构 + 默认分类/标签/食材，不含任何菜谱。"""
    target = DB_PATH if target is None else target
    name = "hearth_seed_" + uuid.uuid4().hex
    db = database.open(name)
    work = None
    try:
        work = work_path(name)
        db.execute("PRAGMA journal_mode = DELETE")
        db.execute("PRAGMA synchronous = FULL")
        with db.transaction():
            create_schema(db)
            seed_options(db)
            write_ingredients(db, FOOD_CATALOG)
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        db.close()
        db = None
        copy_database(work, target)
        remove_sidecars(target)
    finally:
        if db is not None:
            db.close()
        if work is not None:
            for suffix in ("", "-wal", "-shm", "-journal"):
                remove_temp(Path(str(work) + suffix))
    return target


def work_path(name):
    """宿主库文件的实际路径：database_path 可能省略 .db，按存在性判定。"""
    path = Path(database.database_path(name))
    if path.suffix == ".db":
        return path
    with_suffix = path.with_name(path.name + ".db")
    if with_suffix.exists() or not path.exists():
        return with_suffix
    return path


def aisle_for(food_type):
    return {"肉类": "生鲜", "水产": "水产", "蛋、豆类": "蛋豆", "蔬菜类": "蔬果",
            "主食与干货": "干货", "调味料": "调味"}.get(food_type, "其他")


def ingredient_row_id(food_type, parent, variety):
    digest = hashlib.sha256("|".join([food_type, parent, variety]).encode()).hexdigest()[:16]
    return "ing-" + digest


def named_row_id(table, name):
    return table[:3] + "-" + hashlib.sha256(name.encode()).hexdigest()[:16]


def create_schema(db):
    for statement in SCHEMA_STATEMENTS:
        db.execute(statement)


def add_ingredient_row(db, food_type, parent, variety, name):
    db.execute("INSERT OR REPLACE INTO ingredients(id, food_type, parent, variety, name, aisle)"
               " VALUES (?, ?, ?, ?, ?, ?)",
               [ingredient_row_id(food_type, parent, variety), food_type, parent, variety, name,
                aisle_for(food_type)])


def write_ingredients(db, catalog):
    """把三级食材目录整表写入 ingredients：容器行（一级/二级）+ 品种行。"""
    db.execute("DELETE FROM ingredients")
    for food_type, parents in catalog.items():
        add_ingredient_row(db, food_type, "", "", food_type)
        for parent, varieties in parents.items():
            add_ingredient_row(db, food_type, parent, "", parent)
            for variety in varieties:
                add_ingredient_row(db, food_type, parent, variety,
                                   ingredient_name(food_type, parent, variety))


def read_ingredients(db):
    catalog = {}
    for row in db.query("SELECT food_type, parent, variety FROM ingredients ORDER BY rowid"):
        parents = catalog.setdefault(row["food_type"], {})
        parent = row["parent"]
        if not parent:
            continue
        varieties = parents.setdefault(parent, [])
        variety = row["variety"]
        if variety and variety not in varieties:
            varieties.append(variety)
    return catalog


def ensure_named_row(db, table, name):
    """分类/标签按名称去重后返回主键。"""
    name = name.strip()
    rows = db.query("SELECT id FROM " + table + " WHERE name = ?", [name])
    if rows:
        return rows[0]["id"]
    row_id = named_row_id(table, name)
    db.execute("INSERT INTO " + table + "(id, name) VALUES (?, ?)", [row_id, name])
    return row_id


def read_named(db, table):
    return [row["name"] for row in db.query("SELECT name FROM " + table + " ORDER BY rowid")]


def seed_options(db):
    """分类与标签的初始候选项：按名称去重，已存在则跳过。"""
    for name in DEFAULT_CATEGORIES:
        ensure_named_row(db, "categories", name)
    for name in DEFAULT_TAGS:
        ensure_named_row(db, "tags", name)


def catalog_ref(db, ingredient):
    """菜谱食材指向 ingredients 表的行；自由文本食材没有目录行时返回空串。"""
    food_type = ingredient.get("type", "")
    parent = ingredient.get("parent", "")
    if food_type and parent:
        rows = db.query("SELECT id FROM ingredients WHERE food_type = ? AND parent = ? AND variety = ?",
                        [food_type, parent, ingredient.get("variety", "")])
        if rows:
            return rows[0]["id"]
    rows = db.query("SELECT id FROM ingredients WHERE name = ? ORDER BY rowid LIMIT 1", [ingredient["name"]])
    return rows[0]["id"] if rows else ""


def delete_recipe(db, recipe_id):
    """删除菜谱本体及其关联行（食材用量、分类、标签）。"""
    if not isinstance(recipe_id, str) or not recipe_id.strip():
        raise ValueError("菜谱标识无效。")
    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", [recipe_id])
    db.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", [recipe_id])
    db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", [recipe_id])
    db.execute("DELETE FROM recipes WHERE id = ?", [recipe_id])


def write_recipe(db, recipe):
    recipe_id = recipe["id"]
    ingredients = recipe.get("ingredients", [])
    if not isinstance(ingredients, list):
        raise ValueError("食材格式错误。")
    db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", [recipe_id])
    db.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", [recipe_id])
    db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", [recipe_id])
    db.execute("INSERT OR REPLACE INTO recipes(id, title, video_url, notes, prep, operations,"
               " servings, minutes, rating, favorite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               [recipe_id, recipe["title"], recipe.get("video_url", ""),
                "\n".join(task_text(recipe, "note_rows", lines(recipe.get("notes", "")))),
                "\n".join(task_text(recipe, "prep_steps", [])),
                "\n".join(task_text(recipe, "operation_steps", recipe.get("steps", []))),
                int(recipe.get("servings", 2) or 2), int(recipe.get("minutes", 0) or 0),
                int(recipe.get("rating", 0)), 1 if recipe.get("favorite") else 0])
    for position, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict) or not isinstance(ingredient.get("name"), str):
            raise ValueError("食材格式错误。")
        db.execute("INSERT OR REPLACE INTO recipe_ingredients(recipe_id, position, ingredient_id, name,"
                   " food_type, parent, variety, quantity, unit, aisle) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   [recipe_id, position, catalog_ref(db, ingredient), ingredient["name"],
                    ingredient.get("type", ""), ingredient.get("parent", ""), ingredient.get("variety", ""),
                    ingredient.get("quantity"), ingredient.get("unit", ""), ingredient.get("aisle") or "其他"])
    for name in text_list(recipe.get("categories", [])):
        db.execute("INSERT OR REPLACE INTO recipe_categories(recipe_id, category_id) VALUES (?, ?)",
                   [recipe_id, ensure_named_row(db, "categories", name)])
    for name in text_list(recipe.get("tags", [])):
        db.execute("INSERT OR REPLACE INTO recipe_tags(recipe_id, tag_id) VALUES (?, ?)",
                   [recipe_id, ensure_named_row(db, "tags", name)])


def read_recipes(db):
    result = []
    for row in db.query("SELECT id, title, video_url, notes, prep, operations, servings, minutes,"
                        " rating, favorite FROM recipes ORDER BY title COLLATE NOCASE, id"):
        recipe_id = row["id"]
        categories = [item["name"] for item in db.query(
            "SELECT categories.name AS name FROM recipe_categories JOIN categories"
            " ON categories.id = recipe_categories.category_id WHERE recipe_categories.recipe_id = ?"
            " ORDER BY categories.rowid", [recipe_id])]
        tags = [item["name"] for item in db.query(
            "SELECT tags.name AS name FROM recipe_tags JOIN tags ON tags.id = recipe_tags.tag_id"
            " WHERE recipe_tags.recipe_id = ? ORDER BY tags.rowid", [recipe_id])]
        ingredients = []
        for item in db.query("SELECT ingredient_id, name, food_type, parent, variety, quantity, unit, aisle"
                             " FROM recipe_ingredients WHERE recipe_id = ? ORDER BY position", [recipe_id]):
            ingredient = dict(id=uuid.uuid4().hex, name=item["name"], quantity=item["quantity"],
                              unit=item["unit"], aisle=item["aisle"])
            if item["food_type"]:
                ingredient.update(catalog_id=item["ingredient_id"], type=item["food_type"],
                                  parent=item["parent"], variety=item["variety"])
            ingredients.append(ingredient)
        value = dict(id=recipe_id, title=row["title"],
                     categories=categories, category=categories[0] if categories else "未分类", tags=tags,
                     ingredients=ingredients, prep_steps=make_rows(row["prep"]),
                     operation_steps=make_rows(row["operations"]),
                     steps=lines(row["prep"]) + lines(row["operations"]),
                     notes=row["notes"], note_rows=make_rows(row["notes"]), video_url=row["video_url"],
                     servings=int(row["servings"]), minutes=int(row["minutes"]), rating=int(row["rating"]),
                     favorite=bool(row["favorite"]))
        normalize_recipe(value)
        result.append(value)
    return result


def remove_temp(path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ValueError("文件不是有效的 SQLite 数据库。")
        stream.seek(0)
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def labels(text):
    return list(dict.fromkeys(part.strip() for part in re.split(r"[,，\n]", text) if part.strip()))


def text_list(value):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("菜谱文本列表格式错误。")
    return value


def task_text(recipe, field, fallback):
    if field not in recipe:
        return text_list(fallback)
    rows = recipe[field]
    if not isinstance(rows, list) or not all(isinstance(row, dict) and isinstance(row.get("text"), str) for row in rows):
        raise ValueError("步骤或笔记格式错误。")
    return [row["text"] for row in rows]


def normalize_recipe(recipe):
    result = dict(recipe)
    for field in ("id", "title"):
        if not isinstance(result.get(field), str) or not result[field].strip():
            raise ValueError("菜谱缺少名称或标识。")
    for field in ("notes", "video_url"):
        if not isinstance(result.get(field, ""), str):
            raise ValueError("菜谱文本格式错误。")
    result["categories"] = text_list(recipe.get("categories", [recipe.get("category", "未分类")]))
    result["tags"] = text_list(recipe.get("tags", []))
    ingredients = recipe.get("ingredients", [])
    if not isinstance(ingredients, list):
        raise ValueError("食材格式错误。")
    texts = []
    for item in ingredients:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("食材格式错误。")
        quantity = item.get("quantity")
        if quantity is None:
            texts.append(item["name"])
        else:
            if type(quantity) not in (int, float) or not math.isfinite(quantity) or quantity <= 0:
                raise ValueError("食材用量错误。")
            texts.append(f"{quantity:g} {item.get('unit', '')} {item['name']}".strip())
    result["ingredient_text"] = "\n".join(texts)
    result["prep"] = task_text(recipe, "prep_steps", [])
    result["operations"] = task_text(recipe, "operation_steps", recipe.get("steps", []))
    result["note_texts"] = task_text(recipe, "note_rows", lines(recipe.get("notes", "")))
    rating = recipe.get("rating", 0)
    if type(rating) is not int or not 0 <= rating <= 5:
        raise ValueError("评分必须是 0–5 分。")
    result["rating"] = rating
    return result


store = RecipeStore()
state = appui.State(
    persist=False, tab=0, recipes=[], ready=False, query="", filter_categories=[], filter_tags=[],
    selected_id="", show_detail=False, show_editor=False, editing_id="", draft={},
    error="", editor_error="", screen_status="", checked=[],
    edit_rows={}, edit_checked=[], active_ingredient="",
    food_type="", food_parent="", food_variety="",
    new_food_name="", new_food_level="三级", ingredient_query="",
    category_options=list(DEFAULT_CATEGORIES), tag_options=list(DEFAULT_TAGS),
    new_category="", new_tag="", editor_sheet="",
    show_editor_sheet=False, show_delete_confirm=False, show_error_dialog=False,
    dialog_error_text="", data_note=DATA_NOTE,
    settings_status="", settings_alert="",
    page=1, page_size=FALLBACK_PAGE_SIZE, page_input="", video_error="",
)
_idle_previous = None
_settings_pending = None    # 待弹出的设置页结果弹窗：(kind, message)


def screen_on():
    if ObjCClass is None or on_main_thread is None:
        return

    @on_main_thread
    def apply():
        global _idle_previous
        try:
            application = ObjCClass("UIApplication").sharedApplication()
            if _idle_previous is None:
                _idle_previous = bool(application.idleTimerDisabled())
            application.setIdleTimerDisabled_(True)
        except Exception as exc:
            state.screen_status = "常亮未开启：" + str(exc)

    try:
        if callable(apply):
            apply()
    except Exception as exc:
        state.screen_status = "常亮未开启：" + str(exc)


def screen_restore():
    if ObjCClass is None or on_main_thread is None:
        return

    @on_main_thread
    def restore():
        global _idle_previous
        try:
            if _idle_previous is not None:
                ObjCClass("UIApplication").sharedApplication().setIdleTimerDisabled_(_idle_previous)
                _idle_previous = None
        except Exception as exc:
            state.screen_status = "自动锁定恢复失败：" + str(exc)

    try:
        if callable(restore):
            restore()
    except Exception as exc:
        state.screen_status = "自动锁定恢复失败：" + str(exc)


def set_recipes(recipes, **extra):
    """写入菜谱清单的唯一入口：只接受列表。

    之前各流程直接 batch_update(recipes=...)，一旦写进布尔之类的误值，本轮界面看不出问题，
    但下次启动首屏渲染就崩在 `for item in state.recipes`，只能靠改代码才能恢复。
    这里显式校验，把静默污染变成一条看得见的错误。
    """
    if not isinstance(recipes, list):
        raise ValueError("菜谱数据格式错误：期望列表，实际为 " + type(recipes).__name__ + "。")
    state.batch_update(recipes=recipes, **extra)


def load_recipes():
    try:
        recipes = store.exchange()
        set_recipes(recipes, category_options=list(store.categories),
                    tag_options=list(store.tags), ready=True, error="", page=1)
    except Exception as exc:
        state.batch_update(error=str(exc), ready=True)


def settings_alert_title():
    """设置页弹窗标题：确认型与结果型文案完全不同，便于一眼区分两步。"""
    kind = state.settings_alert
    if kind == "confirm_reset":
        return "重置数据库？"
    if kind == "reset_done":
        return "重置数据库完成"
    if kind == "reset_failed":
        return "重置数据库失败"
    if kind == "confirm_reload":
        return "重载数据库？"
    if kind == "reload_done":
        return "重载数据库完成"
    if kind == "reload_failed":
        return "重载数据库失败"
    return ""


def settings_alert_message():
    kind = state.settings_alert
    if kind == "confirm_reset":
        return "重置数据库将清除所有自定义数据（菜谱、分类、标签、食材），恢复至初始状态，且无法撤销。"
    if kind == "confirm_reload":
        return "重载数据库将丢弃界面上的未保存改动，并从 " + DB_PATH.name + " 重新读取全部数据。"
    return state.settings_status or "已完成。"


def settings_alert_actions():
    """确认型弹窗的按钮。

    两个确认按钮都用 role="destructive"（重载会丢弃未保存改动，同属破坏性操作）：
    系统会为破坏性按钮自带一个取消，所以这里不再手写取消，否则会出现两个取消。
    """
    kind = state.settings_alert
    if kind == "confirm_reset":
        return [appui.Button("确认重置", action=do_reset_database, role="destructive")]
    if kind == "confirm_reload":
        return [appui.Button("确认重载", action=do_reload_database, role="destructive")]
    return [appui.Button("好", action=close_settings_alert)]


def ask_reset_database():
    """点「重置数据库」：先弹确认窗口，不直接重置。"""
    global _settings_pending
    _settings_pending = None
    state.batch_update(settings_alert="confirm_reset", settings_status="")


def ask_reload_database():
    """点「重载数据库」：先弹确认窗口，确认后才真正读取。"""
    global _settings_pending
    _settings_pending = None
    state.batch_update(settings_alert="confirm_reload", settings_status="")


def close_settings_alert():
    """弹窗关闭：复位开关并清掉提示文本，页面不留痕迹；有排队中的结果提示则接着弹出。"""
    global _settings_pending
    state.settings_alert = ""
    if _settings_pending is None:
        state.settings_status = ""
        return
    kind, message = _settings_pending
    _settings_pending = None
    state.batch_update(settings_status=message, settings_alert=kind)


def show_settings_result(kind, message):
    """弹出操作结果；确认弹窗还开着时先记录，等它关闭后再弹（避免同时切换两个弹层）。"""
    global _settings_pending
    state.settings_status = message
    if state.settings_alert:
        _settings_pending = (kind, message)
        state.settings_alert = ""
        return
    state.settings_alert = kind


def do_reload_database():
    """确认后执行重载数据库，结果弹窗提示。"""
    load_recipes()
    if state.error:
        show_settings_result("reload_failed", "重载数据库失败：" + state.error)
        return
    show_settings_result("reload_done", "重载数据库完成：共 %d 道菜谱。" % len(recipe_list()))


def do_reset_database():
    """确认后执行重置数据库：删库并按内置初始数据重新生成，结果弹窗提示。"""
    try:
        recipes = store.reset()
    except Exception as exc:
        state.error = str(exc)
        show_settings_result("reset_failed", "重置数据库失败：" + str(exc))
        return
    set_recipes(recipes, category_options=list(store.categories),
                tag_options=list(store.tags), ready=True, error="",
                query="", filter_categories=[], filter_tags=[], page=1, page_input="",
                       selected_id="", show_detail=False, checked=[], show_editor=False,
                       editing_id="", draft={}, edit_rows={}, edit_checked=[],
                       active_ingredient="", editor_sheet="", show_editor_sheet=False,
                       show_delete_confirm=False, show_error_dialog=False, dialog_error_text="",
                       editor_error="", video_error="")
    show_settings_result("reset_done",
                         "重置数据库完成：菜谱已清空（0 道），分类、标签、食材回到初始值。")


def appeared():
    if not state.ready or not isinstance(state.recipes, list):
        # 字段被污染成非列表（例如被误写成布尔）时，首屏会直接抛异常导致无法启动；
        # 这里先渲染空清单，再由本次重载把字段修正回真正的菜谱列表。
        load_recipes()
    screen_on()


def close_app():
    screen_restore()
    appui.dismiss()


def change_state(field):
    def changed(value):
        setattr(state, field, value)
    return changed


def recipe_list():
    """读取菜谱清单的唯一入口：字段若被误写成非列表，退回空清单而不是让整页渲染崩掉。"""
    items = state.recipes
    return items if isinstance(items, list) else []


def current_recipe():
    return next((item for item in recipe_list() if item["id"] == state.selected_id), None)


def open_detail(recipe_id):
    def perform():
        state.batch_update(selected_id=recipe_id, checked=[], show_detail=True, video_error="")
    return perform


def close_detail():
    state.show_detail = False


def begin_edit(recipe=None):
    recipe = normalize_recipe(recipe) if recipe else {}
    draft = dict(
        title=recipe.get("title", ""),
        categories=", ".join(recipe.get("categories", [])[:1]),
        tags=", ".join(recipe.get("tags", [])), ingredients=recipe.get("ingredient_text", ""),
        prep="\n".join(recipe.get("prep", [])), operations="\n".join(recipe.get("operations", [])),
        notes="\n".join(recipe.get("note_texts", [])), video_url=recipe.get("video_url", ""),
        rating=recipe.get("rating", 0),
    )
    rows = {field: make_rows(draft[field]) for field in ROW_FIELDS}
    for row, ingredient in zip(rows["ingredients"], recipe.get("ingredients", [])):
        row["ingredient"] = dict(ingredient)
    food_type, food_parent, food_variety = resolve_food_selection("", "", "")
    state.batch_update(editing_id=recipe.get("id", ""), draft=draft, editor_error="", show_editor=True,
                       edit_rows=rows, edit_checked=[], active_ingredient="",
                       food_type=food_type, food_parent=food_parent, food_variety=food_variety,
                       ingredient_query="", new_food_name="", new_category="", new_tag="",
                       editor_sheet="", show_editor_sheet=False, show_delete_confirm=False,
                       show_error_dialog=False, dialog_error_text="")


def present_sheet(field):
    """强制重新呈现某个弹层：先请求关闭该槽位，再请求展示。

    原生层可能残留「已经在展示」的内部状态（例如上一次保存时弹层与页面推送同时触发），
    此时只把布尔字段设为 True 不会产生新的呈现请求，表现就是「再点没反应」；
    先 dismiss 一次可把槽位复位，再 present 才能稳定弹出来。旧版无这些 API 时退回赋值。
    """
    dismiss = getattr(appui, "presentation_dismiss", None)
    if callable(dismiss):
        try:
            dismiss(field, state=state)
        except Exception:
            pass
    presenter = getattr(appui, "presentation_present", None)
    if callable(presenter):
        try:
            if presenter(field, state=state):
                return
        except Exception:
            pass
    setattr(state, field, True)


def new_recipe():
    """新增菜谱：清掉残留弹层状态后请求展示。

    能点到「+」说明编辑页没在展示，此时 show_editor 若仍为 True 只能是残留值
    （True→True 不产生新请求），需要用显式 API 强制重新弹出；正常路径不必强制，避免闪烁。
    """
    stale = bool(state.show_editor)
    state.batch_update(show_detail=False, editor_sheet="", show_editor_sheet=False,
                       show_delete_confirm=False, show_error_dialog=False, dialog_error_text="",
                       editor_error="", video_error="")
    begin_edit()
    if stale:
        present_sheet("show_editor")


def edit_recipe():
    recipe = current_recipe()
    if recipe is not None:
        stale = bool(state.show_editor)
        state.batch_update(editor_sheet="", show_editor_sheet=False, show_delete_confirm=False,
                           show_error_dialog=False, dialog_error_text="",
                           editor_error="", video_error="")
        begin_edit(recipe)
        if stale:
            present_sheet("show_editor")


def close_editor():
    """关闭编辑页：同时清掉新增弹窗状态，避免残留弹层影响下一次展示。"""
    state.batch_update(show_editor=False, editor_sheet="", show_editor_sheet=False,
                       show_delete_confirm=False, show_error_dialog=False, dialog_error_text="",
                       editor_error="")


def update_draft(field):
    def changed(value):
        draft = dict(state.draft)
        draft[field] = value
        state.draft = draft
        if field in ROW_FIELDS:
            rows = dict(state.edit_rows)
            rows[field] = make_rows(value)
            state.edit_rows = rows
    return changed


def set_rating(value):
    def perform():
        update_draft("rating")(value)
    return perform


def option_label(kind):
    """分类/标签新增弹窗的标题文本。"""
    return {"categories": "分类", "tags": "标签"}.get(kind, "")


def option_field(kind):
    """分类/标签新增弹窗对应的输入框状态字段。"""
    return {"categories": "new_category", "tags": "new_tag"}.get(kind, "")


def open_editor_sheet(kind):
    """打开编辑页弹层：先写内容（kind 决定标题/表单），再打开开关。

    分开两次赋值，保证弹层创建时已经拿到最新的内容；开关用双向绑定，
    关闭后必定回到 False，再次打开一定是一次真实变化（不会「点几次才响应」）。
    """
    state.batch_update(editor_sheet=kind, new_category="", new_tag="", new_food_name="",
                       ingredient_query="", editor_error="")
    state.show_editor_sheet = True


def open_new_option(kind):
    """打开分类/标签的新增弹窗。"""
    def perform():
        if not option_field(kind):
            return
        open_editor_sheet(kind)
    return perform


def update_named_option(kind, name):
    """写入新的分类/标签并把它设为当前选中；成功返回空串，失败返回错误文本。"""
    if kind not in OPTION_TABLES:
        return "目录类型无效。"
    try:
        recipes = store.exchange(names={kind: [name]})
    except Exception as exc:
        return str(exc)
    draft = dict(state.draft)
    if kind == "categories":
        draft["categories"] = name
    else:
        values = labels(draft.get("tags", ""))
        if name not in values:
            values.append(name)
        draft["tags"] = ", ".join(values)
    set_recipes(recipes, draft=draft, category_options=list(store.categories),
                tag_options=list(store.tags))
    return ""


def add_named_option(kind):
    """分类/标签新增弹窗的提交动作。"""
    def perform():
        field = option_field(kind)
        if not field:
            return
        name = getattr(state, field).strip()
        if not name:
            state.editor_error = "请先填写名称。"
            return
        error = update_named_option(kind, name)
        if error:
            state.editor_error = error
            return
        close_editor_sheet()
    return perform


def toggle_draft_value(field, name):
    def perform():
        values = labels(state.draft.get(field, ""))
        if name in values:
            values.remove(name)
        else:
            values.append(name)
        update_draft(field)(", ".join(values))
    return perform


def choose_category(name):
    """分类单选：点一项即替换当前选择。"""
    def perform():
        update_draft("categories")(name)
    return perform


def clear_draft_value(field):
    """清空草稿里的某一项（分类、标签、评分等）；返回点击时才执行的动作。"""
    def perform():
        update_draft(field)("")
    return perform


def menu_choice(name, action, selected):
    """菜单项：已选带勾；未选时不传 system_image，避免菜单项失灵。"""
    if selected:
        return appui.Button(name, action=action, system_image="checkmark")
    return appui.Button(name, action=action)


def clear_icon(action, label, enabled=True):
    """统一的「一键清空」图标按钮：分类、标签、评分、筛选项共用同一造型。"""
    return (appui.Button(action=action, system_image="xmark.circle.fill").button_style("borderless")
            .foreground_color("secondaryLabel").disabled(not enabled).accessibility_label(label))


def choice_menu_row(title, value, content, clear_action=None, clear_enabled=False):
    """与菜名行同构：左标签 + 右侧原生下拉菜单 + 右侧清空图标。"""
    row = [appui.Text(title), appui.Spacer(), appui.Menu(value or "请选择", content=content)]
    if clear_action is not None:
        row.append(clear_icon(clear_action, "清空" + title, clear_enabled))
    return appui.HStack(row, spacing=6)


def new_option_item(kind):
    """下拉里的新增入口：统一显示为「+新增」，点按弹出输入框。"""
    return appui.Button("+新增", action=open_new_option(kind))


def choice_toggle(name, chosen, action):
    """多选菜单项：带钩开关，点按只切换该项。"""
    return appui.Toggle(name, is_on=chosen, on_change=action)


def editor_choice_rows():
    """分类为单选下拉，标签为多选下拉，两者都是原生菜单。"""
    rows = []
    current = labels(state.draft.get("categories", ""))
    selected = current[0] if current else ""
    items = [menu_choice(name, choose_category(name), name == selected) for name in state.category_options]
    items.append(new_option_item("categories"))
    rows.append(choice_menu_row("分类", selected, items,
                                clear_action=clear_draft_value("categories"), clear_enabled=bool(selected)))
    tags = labels(state.draft.get("tags", ""))
    tag_items = [choice_toggle(name, name in tags, toggle_draft_value("tags", name))
                 for name in state.tag_options]
    tag_items.append(new_option_item("tags"))
    rows.append(choice_menu_row("标签", " · ".join(tags), tag_items,
                                clear_action=clear_draft_value("tags"), clear_enabled=bool(tags)))
    return rows


def close_editor_sheet():
    """关闭编辑页弹层：清掉开关与输入内容，页面不留痕迹。"""
    state.batch_update(show_editor_sheet=False, editor_sheet="", new_category="", new_tag="",
                       new_food_name="", ingredient_query="", editor_error="")


def new_option_form():
    """新增分类/标签：在弹出框里输入名称。"""
    kind = state.editor_sheet
    label = option_label(kind)
    field = option_field(kind)
    current = getattr(state, field) if field else ""
    sections = [appui.Section(label, [
        appui.TextField("名称", text=current, on_change=change_state(field or "new_category"),
                        on_submit=add_named_option(kind)),
    ], footer="填写后点右上角「添加」。")]
    if state.editor_error:
        sections.append(appui.Section([appui.Text(state.editor_error).foreground_color("systemRed")]))
    return appui.NavigationStack(appui.Form(sections)
        .navigation_title("新增" + label)
        .toolbar([toolbar_button("取消", close_editor_sheet, "xmark", leading=True),
                  toolbar_button("添加", add_named_option(kind), "checkmark")]))


def editor_sheet():
    """编辑页共用一个弹层槽位：分类/标签新增、食材搜索、新增食材。"""
    kind = state.editor_sheet
    if kind == "food_search":
        return food_search_form()
    if kind == "food_add":
        return food_add_form()
    return new_option_form()


def make_rows(text):
    return [dict(id=uuid.uuid4().hex, text=line) for line in lines(text)]


def save_recipe():
    try:
        for field, rows in state.edit_rows.items():
            if any(not row["text"].strip() for row in rows):
                raise ValueError("请补全新增行，或删除不需要的空行。")
        if any(row["text"].strip() == "" for row in state.edit_rows.get("ingredients", [])):
            raise ValueError("请选择食材，或删除未选择的食材行。")
        draft = dict(state.draft)
        if not draft["title"].strip():
            raise ValueError("请填写菜名。")
        video = draft["video_url"].strip()
        parsed = urlparse(video)
        if video and (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password):
            raise ValueError("视频须为不含登录凭据的 HTTP/HTTPS 网址。")
        previous = next((item for item in recipe_list() if item["id"] == state.editing_id), None)
        if state.editing_id and previous is None:
            raise ValueError("原菜谱已不存在，请重载数据库。")
        recipe = dict(previous or dict(id=uuid.uuid4().hex, kind="recipe", favorite=False, servings=2, minutes=0))
        categories = labels(draft["categories"])
        prep = state.edit_rows.get("prep", [])
        operations = state.edit_rows.get("operations", [])
        notes = state.edit_rows.get("notes", [])
        editor_ingredients = state.edit_rows.get("ingredients", [])
        if previous and draft["ingredients"] == normalize_recipe(previous)["ingredient_text"]:
            ingredients = previous.get("ingredients", [])
        elif all("ingredient" in row for row in editor_ingredients if row["text"].strip()):
            ingredients = [dict(row["ingredient"]) for row in editor_ingredients if row["text"].strip()]
        else:
            ingredients = [dict(id=uuid.uuid4().hex, name=line, quantity=None, unit="", aisle="其他")
                           for line in lines(draft["ingredients"])]
        recipe.update(title=draft["title"].strip(),
                      categories=categories, category=categories[0] if categories else "未分类",
                      tags=labels(draft["tags"]), ingredients=ingredients, prep_steps=prep,
                      operation_steps=operations, steps=[row["text"] for row in prep + operations],
                      notes="\n".join(row["text"] for row in notes), note_rows=notes,
                      video_url=video, rating=int(draft["rating"]))
        recipes = store.exchange(recipe)
        set_recipes(recipes, category_options=list(store.categories),
                    tag_options=list(store.tags), show_editor=False, editor_sheet="",
                    show_editor_sheet=False, show_delete_confirm=False,
                    show_error_dialog=False, dialog_error_text="",
                    editor_error="", error="")
        # 先让编辑页完成关闭，再切到展示页；同一次更新里既收弹层又推页面，原生层容易残留
        state.batch_update(selected_id=recipe["id"], checked=[], show_detail=True)
    except Exception as exc:
        show_editor_error(failure_reason(exc))


def failure_reason(exc):
    """异常原因文本；消息为空时退回异常类型，避免弹窗只剩一句笼统提示。"""
    reason = str(exc).strip()
    if reason:
        return reason
    return exc.__class__.__name__ + "（无详细信息）"


def dialog_error_message():
    """保存失败弹窗的说明：原因与开关同批写入（见 show_editor_error）。"""
    return state.dialog_error_text or "请检查填写内容后重试。"


def show_editor_error(message):
    """弹出保存失败提示：原因与开关放在同一次更新里。

    两者必须同批：单独给呈现字段赋值只走协调器快路径、不重建页面内容，
    弹窗会带着上一次的旧内容（甚至兜底文案）弹出。
    """
    text = message or "请检查填写内容后重试。"
    state.batch_update(dialog_error_text=text, show_error_dialog=True)


def close_editor_error():
    """关闭保存失败弹窗：清掉开关与文案。"""
    state.batch_update(show_error_dialog=False, dialog_error_text="")


def ask_delete_recipe():
    """点「删除菜谱」：只切换确认开关（纯呈现字段，走协调器快路径，不重建页面内容，
    列表不会回滚到顶部）。弹窗文案取自当前草稿菜名，与这个开关无关，
    所以不需要重建也能拿到正确内容。"""
    state.show_delete_confirm = True


def close_delete_dialog():
    """取消删除：恢复开关；编辑页若被顺带收掉则重新请求展示。"""
    state.show_delete_confirm = False
    if state.editing_id and not state.show_editor:
        present_sheet("show_editor")


def confirm_delete_recipe():
    """确认删除当前菜谱：写入数据库后退出编辑，回到清单页。"""
    state.show_delete_confirm = False
    recipe_id = state.editing_id
    if not recipe_id:
        return
    try:
        recipes = store.exchange(remove_id=recipe_id)
    except Exception as exc:
        show_editor_error("删除失败：" + failure_reason(exc))
        return
    set_recipes(recipes, category_options=list(store.categories),
                tag_options=list(store.tags), show_editor=False, show_detail=False,
                editing_id="", draft={}, edit_rows={}, edit_checked=[], checked=[],
                active_ingredient="", editor_sheet="", show_editor_sheet=False,
                show_delete_confirm=False, show_error_dialog=False, dialog_error_text="",
                selected_id="", editor_error="", error="", page=1, page_input="")


def delete_message():
    """二次确认文案：第一行菜名，第二行提示（对话框有 message 时不显示 title，所以菜名放进 message）。"""
    title = state.draft.get("title", "").strip() or "未命名菜谱"
    return f"「{title}」\n将被永久删除，无法撤销。"


def toggle_task(key):
    def perform():
        checked = list(state.checked)
        if key in checked:
            checked.remove(key)
        else:
            checked.append(key)
        state.checked = checked
    return perform


def caption(text):
    return appui.Text(text).font("caption").foreground_color("secondaryLabel")


def toolbar_button(title, action, symbol, leading=False, role=None):
    return appui.ToolbarItem(
        placement="navigation_bar_leading" if leading else "navigation_bar_trailing", role=role,
        content=appui.Button(title, action=action, system_image=symbol),
    )


def record_key(item):
    return item["id"]


def recipe_meta(recipe):
    """清单副标题：同类之间用「·」，分类与标签之间用「|」。"""
    parts = [" · ".join(recipe["categories"]), " · ".join(recipe["tags"])]
    return " | ".join(part for part in parts if part)


def recipe_row(recipe):
    stars = [appui.Image(system_name="star.fill" if index < recipe["rating"] else "star")
             .foreground_color("systemOrange") for index in range(5)]
    right = appui.VStack([
        caption(recipe_meta(recipe)).line_limit(1),
        appui.HStack(stars, spacing=2).font("caption2").accessibility_label(f"{recipe['rating']} 分"),
    ], alignment="trailing", spacing=4)
    label = appui.HStack([
        appui.Text(recipe["title"]).font("headline").foreground_color("label").line_limit(1),
        appui.Spacer(),
        right,
        appui.Image(system_name="chevron.right").foreground_color("secondaryLabel"),
    ], spacing=8).padding(vertical=6)
    return appui.Button(label, action=open_detail(recipe["id"])).button_style("plain")


def toggle_filter(field, name):
    def perform():
        values = list(getattr(state, field))
        if name in values:
            values.remove(name)
        else:
            values.append(name)
        setattr(state, field, values)
        state.page = 1
    return perform


def clear_filter(field):
    def perform():
        setattr(state, field, [])
        state.page = 1
    return perform


def filter_rows(title, field, options, separator=" · "):
    """和新增页的分类/标签一致的原生下拉（可连续多选），只是不带「+新增」；清空只用右侧图标。"""
    selected = [name for name in getattr(state, field) if name in options]
    content = [choice_toggle(name, name in selected, toggle_filter(field, name)) for name in options]
    if not content:
        content.append(appui.Button("暂无可选项").disabled(True))
    row = appui.HStack([
        appui.Text(title), appui.Spacer(),
        appui.Menu(separator.join(selected) if selected else "请选择", content=content),
        clear_icon(clear_filter(field), "清空" + title, bool(selected)),
    ], spacing=6)
    return [row]


def visible_recipes():
    """搜索与筛选之后的清单：列表与分页条共用同一份结果。"""
    result = []
    query = state.query.strip().casefold()
    for item in recipe_list():
        recipe = normalize_recipe(item)
        haystack = " ".join([recipe["title"], recipe["ingredient_text"],
                             " ".join(recipe["categories"] + recipe["tags"])]).casefold()
        if query and query not in haystack:
            continue
        if state.filter_categories and not set(state.filter_categories) & set(recipe["categories"]):
            continue
        if state.filter_tags and not set(state.filter_tags) & set(recipe["tags"]):
            continue
        result.append(recipe)
    return result


def page_count(total):
    return max(1, math.ceil(total / max(1, state.page_size)))


def change_query(value):
    state.batch_update(query=value, page=1)


def page_field_text(page):
    return state.page_input or str(page)


def set_page_input(value):
    state.page_input = value


def goto_page(value):
    state.batch_update(page=max(1, value), page_input="")


def go_prev():
    goto_page(state.page - 1)


def go_next():
    goto_page(min(page_count(len(visible_recipes())), state.page + 1))


def submit_page_input():
    try:
        value = int(state.page_input.strip())
    except ValueError:
        value = state.page
    goto_page(min(max(1, value), page_count(len(visible_recipes()))))


def compute_page_size(height):
    """可用高度里能放下几条清单：保守取整，保证整页不滚动。"""
    return max(1, int((height - PAGER_ROW_H - LIST_CHROME_H) // RECIPE_ROW_H))


_HOME_GEOMETRY = {"w": 0.0, "h": 0.0}   # 最近一次生效的可用尺寸


def remember_home_geometry(geometry, height=None):
    """GeometryReader 回调：兼容 dict / "宽,高" 字符串 / 两个浮点三种形态。

    宽度不变而高度变小，是键盘或弹出层挤压容器所致：保持已生效的每页条数不动，
    避免弹出菜单/键盘时重算尺寸、重排清单。
    """
    width, measured = 0.0, 0.0
    if isinstance(geometry, dict):
        width = float(geometry.get("width", 0.0) or 0.0)
        measured = float(geometry.get("height", 0.0) or 0.0)
    elif isinstance(geometry, str):
        parts = geometry.replace("x", ",").split(",")
        if len(parts) == 2:
            width, measured = float(parts[0]), float(parts[1])
    else:
        width = float(geometry or 0.0)
        measured = float(height or 0.0)
    if measured <= 0:
        return
    last = _HOME_GEOMETRY
    if last["h"] > 0 and abs(width - last["w"]) < 1 and measured < last["h"] - 1:
        return
    last["w"], last["h"] = width, measured
    size = compute_page_size(measured)
    if size == state.page_size:
        return
    pages = max(1, math.ceil(len(visible_recipes()) / size))
    state.batch_update(page_size=size, page=max(1, min(state.page, pages)))


def pager_row():
    """分页条：上一页 / 第 N 页（页码可输入跳转）/ 下一页；三段等距、三元素同字体同间距。"""
    pages = page_count(len(visible_recipes()))
    page = max(1, min(state.page, pages))
    prev_btn = (appui.Button(content=appui.Label("上一页", system_image="chevron.left"), action=go_prev)
                .button_style("bordered").font(PAGER_FONT).frame(min_height=44).disabled(page <= 1))
    next_btn = (appui.Button(content=appui.Label("下一页", system_image="chevron.right"), action=go_next)
                .button_style("bordered").font(PAGER_FONT).frame(min_height=44).disabled(page >= pages))
    # 固定尺寸 + 居中对齐：数字两边留白恒定，不再随内容宽度跳动
    field = (appui.TextField("", text=page_field_text(page), on_change=set_page_input,
                             keyboard_type="number", submit_label="go")
             .text_field_style("plain").multiline_text_alignment("center")
             .on_submit(submit_page_input).font(PAGER_FONT)
             .frame(width=PAGER_NUMBER_W, height=PAGER_NUMBER_H, alignment="center"))
    center = appui.HStack([appui.Text("第").font(PAGER_FONT), field,
                           appui.Text("页").font(PAGER_FONT)],
                          alignment="center", spacing=PAGER_GAP)
    return appui.HStack([prev_btn, appui.Spacer(min_length=12), center,
                         appui.Spacer(min_length=12), next_btn],
                        alignment="center", spacing=8).padding(vertical=6)


def recipes_page():
    all_recipes = [normalize_recipe(item) for item in recipe_list()]
    categories = sorted({name for recipe in all_recipes for name in recipe["categories"]})
    tags = sorted({name for recipe in all_recipes for name in recipe["tags"]})
    visible = visible_recipes()
    size = max(1, state.page_size)
    pages = page_count(len(visible))
    page = max(1, min(state.page, pages))
    current = visible[(page - 1) * size: page * size]
    sections = [appui.Section(filter_rows("分类", "filter_categories", categories)
                              + filter_rows("标签", "filter_tags", tags))]
    if state.error:
        sections.append(appui.Section("数据库", [appui.Text(state.error).foreground_color("systemRed"),
                                                 appui.Button("重载数据库", action=load_recipes)]))
    if state.screen_status:
        sections.append(appui.Section([caption(state.screen_status)]))
    empty = [appui.ContentUnavailableView("暂无菜谱", system_image="book.closed",
                                         description="点击右上角 + 新增，或调整搜索与筛选条件。")]
    sections.append(appui.Section(f"菜谱 · {len(visible)}", [
        appui.ForEach(current, row_builder=recipe_row, key=record_key),
    ] if current else empty))
    list_view = (appui.List(sections).list_style("inset_grouped")
                 .searchable(text=state.query, on_change=change_query, prompt="搜索菜名、标签或食材")
                 .refreshable(action=load_recipes)
                 .toolbar([
                     toolbar_button("关闭", close_app, "xmark", leading=True, role="close"),
                     appui.ToolbarItem(placement="navigation_bar_trailing", content=appui.Button(
                         action=new_recipe, system_image="plus").disabled(not state.ready)
                         .accessibility_label("新增菜谱")),
                 ]))
    return appui.NavigationStack(
        appui.GeometryReader(content=list_view.safe_area_inset(edge="bottom", content=pager_row()),
                             on_change=remember_home_geometry)
        .navigation_destination(is_presented=state.show_detail, content=detail_page(), on_dismiss=close_detail)
    )


def task_section(title, texts):
    rows = []
    for index, text in enumerate(texts):
        key = f"{title}-{index}"
        checked = key in state.checked
        rows.append(appui.Button(
            appui.Label(text, system_image="checkmark.circle.fill" if checked else "circle").strikethrough(checked),
            action=toggle_task(key),
        ).button_style("plain"))
    return appui.Section(title, rows or [caption("暂无")])


def value_row(title, value):
    return appui.HStack([appui.Text(title), appui.Spacer(),
                         appui.Text(value).multiline_text_alignment("trailing")])


def open_video(url):
    def perform():
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            state.video_error = "该视频链接无法打开。"
            return
        try:
            shortcuts.open_url(url)
            state.batch_update(video_error="")
        except Exception as exc:
            state.video_error = "打开链接失败：" + str(exc)
    return perform


def video_row(url):
    """视频：点击用系统或对应 App 打开；不带图标，超长尾部省略。"""
    if not url:
        return value_row("视频", "暂无")
    link = appui.Button(appui.Text(url).line_limit(1).truncation_mode("tail"),
                        action=open_video(url)).button_style("borderless")
    return appui.HStack([appui.Text("视频"), appui.Spacer(), link])


def detail_page():
    raw = current_recipe()
    if raw is None:
        return appui.ContentUnavailableView("请选择菜谱", system_image="book.closed")
    recipe = normalize_recipe(raw)
    stars = [appui.Image(system_name="star.fill" if index < recipe["rating"] else "star")
             .foreground_color("systemOrange") for index in range(5)]
    notes = [appui.Text(f"{index + 1}. {text}") for index, text in enumerate(recipe["note_texts"])]
    # 评分只保留星标；评分在视频之前，与编辑页顺序一致
    basic = [
        value_row("分类", " · ".join(recipe["categories"]) or "未分类"),
        value_row("标签", " · ".join(recipe["tags"]) or "暂无"),
        appui.HStack([appui.Text("评分"), appui.Spacer()] + stars)
        .accessibility_label(f"{recipe['rating']} 分"),
        video_row(recipe.get("video_url", "")),
    ]
    if state.video_error:
        basic.append(caption(state.video_error).foreground_color("systemRed"))
    sections = [
        appui.Section("基本信息", basic),
        task_section("食材", lines(recipe["ingredient_text"])),
        task_section("备菜", recipe["prep"]),
        task_section("操作", recipe["operations"]),
        appui.Section("笔记", notes or [caption("暂无")]),
    ]
    # 菜名固定显示在页面顶端：导航栏 inline 标题常驻，不再在正文里重复一行
    return (appui.List(sections).list_style("inset_grouped").navigation_title(recipe["title"])
            .navigation_bar_title_display_mode("inline")
            .toolbar([toolbar_button("编辑", edit_recipe, "square.and.pencil")]))


def replace_rows(field, rows):
    rows = [dict(row) for row in rows]
    collections = dict(state.edit_rows)
    collections[field] = rows
    draft = dict(state.draft)
    draft[field] = "\n".join(row["text"] for row in rows)
    state.batch_update(edit_rows=collections, draft=draft, editor_error="")


def add_editor_row(field):
    def perform():
        row = dict(id=uuid.uuid4().hex, text="")
        replace_rows(field, list(state.edit_rows.get(field, [])) + [row])
        if field == "ingredients":
            open_ingredient(row["id"])()
    return perform


def delete_editor_row(field, row_id):
    def perform():
        replace_rows(field, [dict(row) for row in state.edit_rows.get(field, []) if row["id"] != row_id])
        state.edit_checked = [key for key in state.edit_checked if key != row_id]
        if state.active_ingredient == row_id:
            state.active_ingredient = ""
    return perform


def change_editor_text(field, row_id):
    def changed(value):
        rows = [dict(row) for row in state.edit_rows.get(field, [])]
        for row in rows:
            if row["id"] == row_id:
                row["text"] = value
        replace_rows(field, rows)
    return changed


def toggle_editor_task(row_id):
    def perform():
        checked = list(state.edit_checked)
        if row_id in checked:
            checked.remove(row_id)
        else:
            checked.append(row_id)
        state.edit_checked = checked
    return perform


def open_ingredient(row_id):
    """展开/收起某行的食材选择器；只定位到该行已有的选择，不自动写入。

    新加的食材行没有 ingredient，选择器落到目录首项仅供滚动起点，
    行内文字保持「请选择食材」，等用户真正滑动或搜索后才写入。
    """
    def perform():
        row = next((row for row in state.edit_rows.get("ingredients", []) if row["id"] == row_id), None)
        if row is None:
            return
        if state.active_ingredient == row_id:
            state.batch_update(active_ingredient="", ingredient_query="", editor_error="")
            return
        ingredient = row.get("ingredient", {})
        food_type, parent, variety = resolve_food_selection(
            ingredient.get("type", ""), ingredient.get("parent", ""), ingredient.get("variety", ""))
        state.batch_update(active_ingredient=row_id, food_type=food_type, food_parent=parent,
                           food_variety=variety, ingredient_query="", editor_error="")
    return perform


def select_ingredient(food_type, parent, variety, **extra):
    """选中食材并写进正在编辑的食材行：滑动/点选即生效，无需确认按钮。

    选择项由调用方显式传入（不读取刚写完的状态，避免时序差导致「点几次才生效」）；
    所有需要变更的字段合并成一次 batch_update，减少重建次数，保持列表滚动位置。
    extra 可带其它要一起写入的字段，例如 ingredient_query、active_ingredient。
    """
    updates = dict(extra)
    updates.update(food_type=food_type, food_parent=parent, food_variety=variety, editor_error="")
    name = ""
    if (state.active_ingredient and food_type in store.catalog
            and parent in store.catalog.get(food_type, {})):
        if not variety or variety in store.catalog[food_type][parent]:
            name = ingredient_name(food_type, parent, variety)
    if name:
        rows = [dict(row) for row in state.edit_rows.get("ingredients", [])]
        for row in rows:
            if row["id"] != state.active_ingredient:
                continue
            if row.get("ingredient", {}).get("name") != name:
                row["text"] = name
                row["ingredient"] = dict(id=row["id"], name=name, type=food_type, parent=parent,
                                         variety=variety, quantity=None, unit="",
                                         aisle=aisle_for(food_type))
                collections = dict(state.edit_rows)
                collections["ingredients"] = rows
                draft = dict(state.draft)
                draft["ingredients"] = "\n".join(item["text"] for item in rows)
                updates.update(edit_rows=collections, draft=draft)
            break
    state.batch_update(**updates)


def select_food_type(value):
    """切换一级分类：二级/三级落到该分类首项，并立即回写食材行。"""
    parents = catalog_parents(store.catalog, value)
    parent = parents[0] if parents else ""
    variety = ""
    if parent and has_third_level(value):
        varieties = catalog_varieties(store.catalog, value, parent)
        variety = varieties[0] if varieties else ""
    select_ingredient(value, parent, variety)


def select_food_parent(value):
    """切换二级分类：三级落到该二级首项，并立即回写食材行。"""
    variety = ""
    if has_third_level(state.food_type):
        varieties = catalog_varieties(store.catalog, state.food_type, value)
        variety = varieties[0] if varieties else ""
    select_ingredient(state.food_type, value, variety)


def select_food_variety(value):
    """切换三级品种：立即回写食材行。"""
    select_ingredient(state.food_type, state.food_parent, value)


def clear_ingredient_query():
    state.ingredient_query = ""


def search_food_options(query, limit=12):
    """按关键字搜三级食材目录，返回 (一级, 二级, 三级) 列表；一级/二级名也参与匹配。"""
    text = query.strip().casefold()
    if not text:
        return []
    found = []
    for food_type, parents in store.catalog.items():
        for parent, varieties in parents.items():
            for variety in varieties:
                name = ingredient_name(food_type, parent, variety)
                if (text in name.casefold() or text in food_type.casefold()
                        or text in parent.casefold()):
                    found.append((food_type, parent, variety))
                    if len(found) >= limit:
                        return found
    return found


def use_food_option(food_type, parent, variety):
    """搜索结果点选：收起搜索弹窗与该行的选择器，并把食材写进食材行。"""
    def perform():
        # 纯呈现字段单独赋值：收起弹窗不会重建列表内容，改动滚动位置
        state.show_editor_sheet = False
        # 一次内容更新写完全部变更（选中项 + 食材行 + 收起选择器），只重建一次
        select_ingredient(food_type, parent, variety, active_ingredient="", ingredient_query="")
    return perform


def open_food_search():
    """打开食材搜索弹窗。"""
    open_editor_sheet("food_search")


def open_food_add():
    """打开新增食材弹窗；层级默认三级（最常用）。"""
    state.new_food_level = "三级"
    open_editor_sheet("food_add")


def food_search_form():
    """食材搜索弹窗：列出匹配项，并显示各自所属的一/二/三级分类。"""
    query = state.ingredient_query
    sections = [appui.Section("搜索", [
        appui.HStack([
            appui.TextField("搜索食材", text=query, on_change=change_state("ingredient_query")),
            clear_icon(clear_ingredient_query, "清空搜索", bool(query)),
        ], spacing=6),
    ], footer="名称、二级、一级都可匹配；条目名称就是三级品种。")]
    results = search_food_options(query, limit=50)
    if query.strip():
        if not results:
            sections.append(appui.Section([caption("没有匹配的食材，可用滚轮下方的「新增」添加。")]))
        else:
            sections.append(appui.Section("结果 · %d" % len(results), [
                appui.Button(content=appui.HStack([
                    appui.Text(ingredient_name(food_type, parent, variety)),
                    appui.Spacer(),
                    caption("%s · %s" % (food_type, parent)),
                ]), action=use_food_option(food_type, parent, variety)).button_style("plain")
                for food_type, parent, variety in results]))
    return appui.NavigationStack(appui.Form(sections)
        .navigation_title("搜索食材")
        .toolbar([toolbar_button("关闭", close_editor_sheet, "xmark", leading=True)]))


def add_food_option():
    """写入新增食材选项（按所选层级），成功后设为当前选择并回写行内文字。"""
    def perform():
        level = state.new_food_level
        name = state.new_food_name.strip()
        if not name:
            state.editor_error = "请先填写名称。"
            return
        food_type, parent = state.food_type, state.food_parent
        catalog = clone_catalog(store.catalog)
        if level == "一级":
            catalog.setdefault(name, {})
        elif level == "二级":
            if food_type not in catalog:
                state.editor_error = "请先选择一级分类。"
                return
            catalog[food_type].setdefault(name, {})
        else:
            if food_type not in catalog or parent not in catalog[food_type]:
                state.editor_error = "请先选择一级与二级分类。"
                return
            if name not in catalog[food_type][parent]:
                catalog[food_type][parent].append(name)
        try:
            recipes = store.exchange(catalog=catalog)
        except Exception as exc:
            state.editor_error = str(exc)
            return
        set_recipes(recipes, editor_sheet="", show_editor_sheet=False,
                    new_food_name="", editor_error="")
        if level == "一级":
            select_food_type(name)
        elif level == "二级":
            select_food_parent(name)
        else:
            select_food_variety(name)
    return perform


def food_add_form():
    """新增食材弹窗：先选层级，再填名称；二级/三级挂在当前所选分类下。"""
    sections = [appui.Section("层级", [
        appui.Picker("新增到", selection=state.new_food_level, options=list(FOOD_LEVELS),
                     on_change=change_state("new_food_level")).picker_style("segmented"),
    ], footer="一级=新分类；二级=挂在「%s」下；三级=挂在「%s · %s」下。" % (
        state.food_type, state.food_type, state.food_parent)),
        appui.Section("名称", [
            appui.TextField("食材名称", text=state.new_food_name,
                            on_change=change_state("new_food_name"), on_submit=add_food_option()),
        ], footer="填写后点右上角「添加」。")]
    if state.editor_error:
        sections.append(appui.Section([appui.Text(state.editor_error).foreground_color("systemRed")]))
    return appui.NavigationStack(appui.Form(sections)
        .navigation_title("新增食材")
        .toolbar([toolbar_button("取消", close_editor_sheet, "xmark", leading=True),
                  toolbar_button("添加", add_food_option(), "checkmark")]))


def ingredient_picker():
    """横向一级选择 + 二级/三级滚轮，滚轮下方是「搜索」「新增」；滑动即写入食材行。"""
    parents = catalog_parents(store.catalog, state.food_type)
    varieties = catalog_varieties(store.catalog, state.food_type, state.food_parent)
    search_btn = appui.Button("搜索", action=open_food_search).button_style("bordered")
    add_btn = appui.Button("新增", action=open_food_add).button_style("bordered")
    wheel_2 = (appui.Picker("二级", selection=state.food_parent, options=parents,
                            on_change=select_food_parent).picker_style("wheel")
               .frame(height=160, max_width=appui.infinity).clipped())
    controls = [appui.Picker("一级", selection=state.food_type, options=catalog_types(store.catalog),
                             on_change=select_food_type).picker_style("segmented")]
    if has_third_level(state.food_type):
        wheel_3 = (appui.Picker("三级", selection=state.food_variety, options=varieties,
                                on_change=select_food_variety).picker_style("wheel")
                   .frame(height=160, max_width=appui.infinity).clipped())
        controls.append(appui.HStack([
            appui.VStack([wheel_2, search_btn], spacing=6),
            appui.VStack([wheel_3, add_btn], spacing=6),
        ], spacing=4))
    else:
        controls.append(appui.VStack([
            wheel_2,
            appui.HStack([search_btn, appui.Spacer(), add_btn], spacing=8),
        ], spacing=6))
    controls.append(caption("滑动滚轮即自动填入食材；「新增」可添加一级/二级/三级备选。"))
    return appui.VStack(controls, alignment="leading", spacing=8)


def editor_rows_section(title, field):
    def row_builder(row):
        remove = appui.Button(action=delete_editor_row(field, row["id"]), system_image="minus.circle.fill")
        remove = remove.button_style("borderless").foreground_color("systemRed").accessibility_label("删除" + title + "行")
        checked = row["id"] in state.edit_checked
        if field == "ingredients":
            label = appui.Text(row["text"] or "请选择食材")
            if checked:
                label = label.strikethrough(True).foreground_color("secondaryLabel")
            controls = [appui.HStack([
                appui.Button(action=toggle_editor_task(row["id"]),
                             system_image="checkmark.circle.fill" if checked else "circle")
                    .button_style("borderless"),
                appui.Button(label, action=open_ingredient(row["id"])).button_style("borderless"),
                appui.Spacer(),
                remove,
            ])]
            if state.active_ingredient == row["id"]:
                controls.append(ingredient_picker())
            return appui.VStack(controls, alignment="leading", spacing=8)
        if field == "notes":
            index = next(index + 1 for index, item in enumerate(state.edit_rows[field]) if item["id"] == row["id"])
            prefix = appui.Text(f"{index}.")
        else:
            prefix = appui.Button(action=toggle_editor_task(row["id"]),
                                  system_image="checkmark.circle.fill" if checked else "circle").button_style("borderless")
        return appui.HStack([
            prefix,
            appui.TextField(title + "内容", text=row["text"], on_change=change_editor_text(field, row["id"]))
                .strikethrough(checked and field != "notes"),
            remove,
        ])
    return appui.Section(title, [
        appui.ForEach(state.edit_rows.get(field, []), row_builder=row_builder, key=record_key),
        appui.Button("增加" + title, action=add_editor_row(field), system_image="plus").button_style("borderless"),
    ])


def editor_page():
    # 保存失败等提示统一走弹窗，页面内不再渲染错误文本
    sections = []
    title_field = (appui.TextField("菜名", text=state.draft.get("title", ""), on_change=update_draft("title"))
                   .multiline_text_alignment("trailing"))
    video = (appui.TextField("视频", text=state.draft.get("video_url", ""), on_change=update_draft("video_url"),
                             keyboard_type="url").multiline_text_alignment("trailing"))
    stars = [appui.Button(action=set_rating(index + 1),
                          system_image="star.fill" if index < state.draft.get("rating", 0) else "star")
             .button_style("borderless").accessibility_label(f"{index + 1} 分") for index in range(5)]
    # 基本信息：菜名、分类、标签、评分、视频同级排列
    basic = [appui.HStack([appui.Text("菜名"), appui.Spacer(), title_field])]
    basic.extend(editor_choice_rows())
    basic.append(appui.HStack(
        [appui.Text("评分"), appui.Spacer()] + stars
        + [clear_icon(set_rating(0), "清除评分", bool(state.draft.get("rating", 0)))], spacing=6))
    basic.append(appui.HStack([appui.Text("视频"), appui.Spacer(), video]))
    sections.append(appui.Section("基本信息", basic))
    sections.append(editor_rows_section("食材", "ingredients"))
    sections.append(editor_rows_section("备菜", "prep"))
    sections.append(editor_rows_section("操作", "operations"))
    sections.append(editor_rows_section("笔记", "notes"))
    # 修改已有菜谱时，页面最下方提供删除入口（新增页没有可删对象，不显示）
    if state.editing_id:
        sections.append(appui.Section([appui.HStack([
            appui.Spacer(),
            appui.Button("删除菜谱", action=ask_delete_recipe).tint("systemRed"),
            appui.Spacer(),
        ]).list_row_background("clear")]))
    # 只有一个确认控件：新增/修改靠滑动关闭或右上角「保存」
    content = (appui.List(sections).list_style("inset_grouped")
               .navigation_title("编辑菜谱" if state.editing_id else "新增菜谱")
               .toolbar([toolbar_button("保存", save_recipe, "checkmark")]))
    # 两个呈现修饰符都挂在编辑页的根视图上（与新增弹窗同一宿主，由渲染器按最近激活项仲裁），
    # 挂在内部 List 上会导致取消后把编辑页一起收掉、退回展示页。
    return appui.NavigationStack(content) \
        .sheet(is_presented=state.bind.show_editor_sheet, content=editor_sheet,
               on_dismiss=close_editor_sheet, detents=["medium", "large"]) \
        .confirmation_dialog("删除菜谱？", message=delete_message(),
                             is_presented=state.show_delete_confirm,
                             on_dismiss=close_delete_dialog,
                             actions=[appui.Button("删除", action=confirm_delete_recipe,
                                                  role="destructive")]) \
        .confirmation_dialog("保存失败", message=dialog_error_message(),
                             is_presented=state.show_error_dialog,
                             on_dismiss=close_editor_error,
                             actions=[appui.Button("好", action=close_editor_error)])


def settings_page():
    sections = []
    if state.data_note:
        sections.append(appui.Section([appui.Text(state.data_note).foreground_color("systemOrange")]))
    # 提示一律走弹窗，页面内不再渲染任何操作结果文本
    sections.append(appui.Section("数据", [
        appui.HStack([appui.Text("数据文件"), appui.Spacer(), caption(DB_PATH.name)]),
        appui.HStack([appui.Text("备份文件"), appui.Spacer(), caption(BACKUP_PATH.name)]),
        appui.Button("重载数据库", action=ask_reload_database),
    ], footer="所有读写都发生在工作库 " + DB_PATH.name + "；首次运行与重置数据库时由内置初始数据生成。"))
    sections.append(appui.Section("重置数据库", [
        caption("重置数据库将清除所有自定义数据（菜谱、分类、标签、食材），并重新生成初始数据库。"),
        appui.Button("重置数据库", action=ask_reset_database).tint("systemRed"),
    ], footer="重置数据库立即生效且无法撤销，请谨慎操作。"))
    sections.append(appui.Section("关于", [
        appui.HStack([appui.Spacer(),
                      appui.Text("烟火 · Hearth").font("footnote")
                      .foreground_color("secondaryLabel"),
                      appui.Spacer()]),
    ]))
    return appui.NavigationStack(appui.List(sections).list_style("inset_grouped")
        .toolbar([toolbar_button("关闭", close_app, "xmark", leading=True, role="close")])) \
        .alert(settings_alert_title(), message=settings_alert_message(),
               is_presented=bool(state.settings_alert), on_dismiss=close_settings_alert,
               actions=settings_alert_actions())


def empty_page():
    return appui.NavigationStack(appui.VStack([])
        .toolbar([toolbar_button("关闭", close_app, "xmark", leading=True, role="close")]))


def body():
    return (appui.TabView([
        appui.Tab(title="菜谱", system_image="book.closed", content=recipes_page(), tag=0),
        appui.Tab(title="餐单", system_image="calendar", content=empty_page(), tag=1),
        appui.Tab(title="采购", system_image="cart", content=empty_page(), tag=2),
        appui.Tab(title="设置", system_image="gearshape", content=settings_page(), tag=3),
    ], selection=state.tab, on_change=change_state("tab"))
        .tint("systemOrange")
        # 用双向 Binding：下滑关闭时由原生侧把 False 写回 state.show_editor。
        # 之前传的是普通布尔值，SwiftUI 收不回写，字段停在 True，
        # 第二次点「+」时 True→True 不产生新请求，表现为按钮失灵。
        .sheet(is_presented=state.bind.show_editor, content=editor_page, on_dismiss=close_editor,
               detents=["large"])
        .on_appear(action=appeared).on_disappear(action=screen_restore))


atexit.register(screen_restore)
appui.run(body, state=state, presentation="fullscreen")
