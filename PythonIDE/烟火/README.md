# 烟火（Hearth）

本地菜谱 MiniApp（英文名 **Hearth**）：食材、标签、分类各自成表，菜谱与它们关联。

## 运行信息

- 入口：`main.py`
- 运行时：AppUI
- 数据文件：同目录 `database.db`（首次运行与重置时由内置初始数据生成；每次保存前自动备份为同目录 `backup.db`）
- 版本：1.0

## 数据表

- `ingredients` 食材目录（一级 / 二级 / 三级）
- `categories` 分类、`tags` 标签
- `recipes` 菜谱，`recipe_ingredients` / `recipe_categories` / `recipe_tags` 关联表

## 分享说明

分享完整应用时请导出 `.miniapp`，不要只发送入口脚本。
