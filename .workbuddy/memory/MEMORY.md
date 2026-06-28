# 血糖知识图谱 · 项目记忆

## 项目定位
构建血糖相关知识数据库 + 自动生成 AI 图像 Prompt，用于制作血糖知识卡片/信息图。

## 关键约定
- Python 脚本使用 managed Python: `C:\Users\xulinchao\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 数据文件全部 JSON 格式，UTF-8 编码
- 食物 GI 数据基于悉尼大学 GI 数据库等权威来源，不可编造
- Prompt 模板变量占位符用 `{variable_name}` 格式
- 输出目录 `out/prompts/` 自动时间戳命名
- Doc 文档用中文，代码注释中英皆可
- 新增食物必须填写所有必填字段（id, name_zh, category, gi, calories_per_100g）
