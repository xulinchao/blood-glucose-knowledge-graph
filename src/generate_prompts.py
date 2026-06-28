#!/usr/bin/env python3
"""
血糖知识图谱 · Prompt 生成器
===============================
从食物数据和知识主题数据出发，结合 Prompt 模板，
自动生成可用于 AI 图像生成工具（Midjourney / DALL·E / SD）的提示词。

使用方法:
    python src/generate_prompts.py                      # 生成全部 prompt
    python src/generate_prompts.py --type food          # 仅生成食物卡片
    python src/generate_prompts.py --type knowledge     # 仅生成知识卡片
    python src/generate_prompts.py --food-id food-001   # 仅生成指定食物
    python src/generate_prompts.py --format dalle       # 输出 DALL·E 格式
    python src/generate_prompts.py --format mj          # 输出 Midjourney 格式
    python src/generate_prompts.py --output md          # 输出 Markdown 文件
    python src/generate_prompts.py --output json        # 输出 JSON 文件
"""

import json
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---- 项目根目录 ----
ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_foods() -> list:
    """加载食物数据（统一使用 gi-database.json）"""
    data = load_json(ROOT / "data" / "foods" / "gi-database.json")
    foods = []
    for f in data.get("foods", []):
        foods.append({
            "id": f["id"],
            "name_zh": f["name_zh"],
            "name_en": f.get("name_en", f["name_zh"]),
            "gi": f["gi"],
            "gi_level": f.get("gi_level", ""),
            "calories_per_100g": f.get("calories_per_100g", ""),
            "blood_sugar_impact": f.get("blood_sugar_impact", ""),
            "serving_size": {"description": f.get("serving_desc", "适量")},
            "nutrition_per_100g": {
                "carbs": f.get("carbs_per_100g", ""),
                "protein": f.get("protein_per_100g", ""),
                "fat": f.get("fat_per_100g", ""),
                "fiber": f.get("fiber_per_100g", ""),
            },
            "tips": f.get("tips", []),
        })
    return foods


def load_topics() -> list:
    """加载知识主题"""
    data = load_json(ROOT / "data" / "knowledge" / "topics.json")
    return data.get("topics", [])


def load_templates() -> dict:
    """加载 Prompt 模板"""
    return load_json(ROOT / "src" / "templates" / "prompts.json")


def safe_str(val, default="") -> str:
    if val is None:
        return default
    return str(val)


def fill_template(template_str: str, variables: dict) -> str:
    """用变量填充模板字符串"""
    result = template_str
    for key, value in variables.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, safe_str(value))
    return result


# ---- 食物卡片 Prompt 生成 ----

def generate_food_card_prompt(food: dict, templates: dict, fmt: str = "mj") -> dict | None:
    """为单个食物生成食物卡片 prompt"""
    tpl = templates["templates"][0]  # tpl-food-card

    tips = food.get("tips", [])
    tip_str = tips[0] if tips else "适量食用"

    serving = food.get("serving_size", {})
    serving_str = serving.get("description", "适量")

    nutrition = food.get("nutrition_per_100g", {})

    variables = {
        "name_zh": food["name_zh"],
        "name_en": food.get("name_en", food["name_zh"]),
        "gi": safe_str(food["gi"]),
        "gi_level": food.get("gi_level", ""),
        "calories": safe_str(food["calories_per_100g"]),
        "carbs": safe_str(nutrition.get("carbs", "")),
        "blood_sugar_impact": food.get("blood_sugar_impact", ""),
        "serving": serving_str,
        "tips": tip_str,
    }

    if fmt == "dalle":
        prompt = fill_template(tpl["template_dalle"], variables)
        negative = templates["global_modifiers"]["negative_prompt"]
    else:
        prompt = fill_template(tpl["template"], variables)
        negative = templates["global_modifiers"]["negative_prompt"]

    return {
        "id": food["id"],
        "type": "food_card",
        "food_name": food["name_zh"],
        "platform": fmt,
        "prompt": prompt,
        "negative_prompt": negative if fmt != "mj" else None,
    }


def generate_food_comparison_prompt(foods: list, templates: dict, fmt: str = "mj") -> dict | None:
    """生成高GI vs 低GI食物对比 prompt，自动匹配合适的食物对"""
    high_gi_foods = [f for f in foods if f["gi"] >= 70]
    low_gi_foods = [f for f in foods if f["gi"] <= 30]

    if not high_gi_foods or not low_gi_foods:
        return None

    high_food = high_gi_foods[0]
    low_food = low_gi_foods[0]
    tpl = templates["templates"][1]

    swap = f"用{low_food['name_zh']}替代{high_food['name_zh']}，GI从{high_food['gi']}降至{low_food['gi']}"

    variables = {
        "high_gi_food": high_food["name_zh"],
        "high_gi_value": safe_str(high_food["gi"]),
        "low_gi_food": low_food["name_zh"],
        "low_gi_value": safe_str(low_food["gi"]),
        "swap_advice": swap,
    }

    template_str = tpl.get("template_dalle" if fmt == "dalle" else "template", tpl.get("template", ""))
    prompt = fill_template(template_str, variables)

    return {
        "id": f"comparison-{high_food['id']}-{low_food['id']}",
        "type": "food_comparison",
        "foods": [high_food["name_zh"], low_food["name_zh"]],
        "platform": fmt,
        "prompt": prompt,
    }


# ---- 知识卡片 Prompt 生成 ----

def generate_knowledge_prompt(topic: dict, templates: dict, fmt: str = "mj") -> dict:
    """为知识主题生成 prompt"""
    tpl = templates["templates"][3]  # tpl-knowledge-info

    points = topic.get("key_points", [])
    while len(points) < 3:
        points.append("")

    variables = {
        "title": topic["title_zh"],
        "summary": topic["summary"],
        "key_point_1": points[0],
        "key_point_2": points[1],
        "key_point_3": points[2],
    }

    if fmt == "dalle":
        prompt = fill_template(tpl["template_dalle"], variables)
    else:
        prompt = fill_template(tpl["template"], variables)

    return {
        "id": topic["id"],
        "type": "knowledge_card",
        "topic": topic["title_zh"],
        "platform": fmt,
        "prompt": prompt,
        "negative_prompt": templates["global_modifiers"]["negative_prompt"],
    }


def generate_gi_gl_quadrant_prompt(templates: dict, fmt: str = "mj") -> dict:
    """生成 GI-GL 四象限图 prompt"""
    tpl = templates["templates"][4]

    variables = {
        "food_high_gi_low_gl": "西瓜（GI=72, GL=5）",
        "food_high_gi_high_gl": "白米饭大碗（GI=83, GL=36）",
        "food_low_gi_low_gl": "樱桃·鸡蛋·西兰花",
        "food_low_gi_high_gl": "大量全麦面包",
    }

    prompt = fill_template(tpl["template_dalle"], variables)

    return {
        "id": "quadrant-gi-gl",
        "type": "quadrant_chart",
        "topic": "GI vs GL 四象限图",
        "platform": fmt,
        "prompt": prompt,
    }


def generate_meal_plate_prompt(templates: dict, fmt: str = "mj") -> dict:
    """生成控糖餐盘 prompt"""
    tpl = templates["templates"][2]

    variables = {
        "protein": "煎三文鱼",
        "vegetables": "西兰花、菠菜、番茄",
        "carbs": "糙米饭",
        "fat_source": "橄榄油",
        "description": "理想控糖餐盘：蔬菜占一半，蛋白质和碳水各占四分之一",
    }

    prompt = fill_template(tpl["template_dalle"], variables)

    return {
        "id": "meal-plate-001",
        "type": "meal_plate",
        "topic": "控糖餐盘",
        "platform": fmt,
        "prompt": prompt,
    }


def generate_blood_sugar_curve_prompt(templates: dict, fmt: str = "mj") -> dict:
    """生成血糖曲线对比 prompt"""
    tpl = templates["templates"][5]

    variables = {
        "scenario_a": "先吃米饭→血糖快速升高",
        "scenario_b": "先吃菜和蛋白质→血糖平稳",
        "conclusion": "同样食物，改变进食顺序可降低餐后血糖峰值20-40%",
    }

    prompt = fill_template(tpl["template_dalle"], variables)

    return {
        "id": "bs-curve-001",
        "type": "chart",
        "topic": "血糖曲线对比",
        "platform": fmt,
        "prompt": prompt,
    }


def generate_daily_tips_prompt(templates: dict, fmt: str = "mj") -> dict:
    """生成每日控糖小贴士 prompt"""
    tpl = templates["templates"][7]

    variables = {
        "tip_title": "💡 今日控糖建议",
        "tip_content": "餐后散步15分钟，可以显著降低餐后血糖峰值",
        "action": "今天午饭后试试吧！",
    }

    prompt = fill_template(tpl["template_dalle"], variables)

    return {
        "id": "daily-tip-001",
        "type": "daily_tip",
        "topic": "每日控糖小贴士",
        "platform": fmt,
        "prompt": prompt,
    }


# ---- 输出格式化 ----

def format_as_json(prompts: list, out_path: Path):
    """输出为 JSON"""
    output = {
        "_meta": {
            "generated_at": datetime.now().isoformat(),
            "total": len(prompts),
        },
        "prompts": prompts,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return out_path


def format_as_markdown(prompts: list, out_path: Path):
    """输出为 Markdown"""
    lines = [
        "# 🩸 血糖知识图谱 · AI 图像生成 Prompt 集合",
        f"",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 总计：{len(prompts)} 条 Prompt",
        f"",
        "---",
        "",
    ]

    type_labels = {
        "food_card": "🍎 食物GI卡片",
        "food_comparison": "⚖️ 食物对比",
        "knowledge_card": "📚 知识卡片",
        "quadrant_chart": "📊 象限图",
        "meal_plate": "🍽️ 控糖餐盘",
        "chart": "📈 数据图表",
        "daily_tip": "💡 每日贴士",
    }

    for i, p in enumerate(prompts, 1):
        label = type_labels.get(p.get("type", ""), "📌 其他")
        topic = p.get("topic") or p.get("food_name") or ""
        lines.append(f"## {i}. {label} — {topic}")
        lines.append(f"")
        lines.append(f"**平台**：{p.get('platform', 'mj').upper()}")
        lines.append(f"**ID**：`{p['id']}`")
        lines.append(f"")
        lines.append(f"```")
        lines.append(p["prompt"])
        lines.append(f"```")
        if p.get("negative_prompt"):
            lines.append(f"")
            lines.append(f"**负向提示词 (Negative Prompt)**：")
            lines.append(f"```")
            lines.append(p["negative_prompt"])
            lines.append(f"```")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


# ---- 主流程 ----

def main():
    parser = argparse.ArgumentParser(description="血糖知识图谱 Prompt 生成器")
    parser.add_argument("--type", choices=["food", "knowledge", "all"], default="all",
                        help="生成类型 (默认: all)")
    parser.add_argument("--food-id", type=str,
                        help="仅生成指定食物 ID 的 prompt")
    parser.add_argument("--format", choices=["mj", "dalle", "both"], default="both",
                        help="目标平台格式 (默认: both)")
    parser.add_argument("--output", choices=["json", "md", "both"], default="both",
                        help="输出格式 (默认: both)")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="输出目录 (默认: out/prompts/)")
    args = parser.parse_args()

    # 加载数据
    foods = load_foods()
    topics = load_topics()
    templates = load_templates()

    # 确定输出目录
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = ROOT / "out" / "prompts"

    # 确定目标平台格式
    formats = [args.format] if args.format != "both" else ["mj", "dalle"]

    # 收集所有生成的 prompt
    all_prompts = []

    # ---- 食物类 Prompt ----
    if args.type in ("food", "all"):
        target_foods = foods
        if args.food_id:
            target_foods = [f for f in foods if f["id"] == args.food_id]
            if not target_foods:
                print(f"⚠️ 未找到食物 ID: {args.food_id}")
                return

        for fmt in formats:
            for food in target_foods:
                result = generate_food_card_prompt(food, templates, fmt)
                if result:
                    all_prompts.append(result)

            # 食物对比（仅当生成全部时添加）
            if not args.food_id:
                comp = generate_food_comparison_prompt(foods, templates, fmt)
                if comp:
                    all_prompts.append(comp)

    # ---- 知识类 Prompt ----
    if args.type in ("knowledge", "all"):
        for fmt in formats:
            for topic in topics:
                result = generate_knowledge_prompt(topic, templates, fmt)
                all_prompts.append(result)

            # 特殊图表
            all_prompts.append(generate_gi_gl_quadrant_prompt(templates, fmt))
            all_prompts.append(generate_meal_plate_prompt(templates, fmt))
            all_prompts.append(generate_blood_sugar_curve_prompt(templates, fmt))
            all_prompts.append(generate_daily_tips_prompt(templates, fmt))

    print(f"✅ 共生成 {len(all_prompts)} 条 Prompt")

    # 输出
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.output in ("json", "both"):
        json_path = out_dir / f"prompts-{timestamp}.json"
        format_as_json(all_prompts, json_path)
        print(f"📄 JSON → {json_path}")

    if args.output in ("md", "both"):
        md_path = out_dir / f"prompts-{timestamp}.md"
        format_as_markdown(all_prompts, md_path)
        print(f"📝 Markdown → {md_path}")


if __name__ == "__main__":
    main()
