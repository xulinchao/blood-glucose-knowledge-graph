#!/usr/bin/env python3
"""
2026-11-06 日报生成脚本
数据来源：WebSearch 补充（采集脚本超时）+ 最新精选日报结构参考
"""
import json
import os
import sys
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

TOPICS_FILE = os.path.join(PROJECT_ROOT, "data", "discovered-topics.json")

# ========== 1. 读取现有选题 ==========
with open(TOPICS_FILE, "r", encoding="utf-8") as f:
    topics_data = json.load(f)

topics = topics_data["topics"]
existing_ids = {t["id"] for t in topics}
existing_titles = {t["title"] for t in topics}

# 确定下一个 disc id
max_num = max(int(t["id"].split("-")[1]) for t in topics)

print(f"现有选题: {len(topics)}, 最大 disc: disc-{max_num:03d}")

# ========== 2. 检查候选选题是否已覆盖 ==========

def check_coverage(title_keywords, angle_keywords=None):
    """简单关键词查重"""
    title_keywords = [k.lower() for k in title_keywords]
    angle_keywords = [k.lower() for k in (angle_keywords or [])]
    
    for t in topics:
        text = (t["title"] + " " + t.get("angle", "")).lower()
        if all(k in text for k in title_keywords):
            return t["id"]
        if angle_keywords and all(k in text for k in angle_keywords):
            return t["id"]
    return None

# 候选选题 + 查重
candidates = [
    {
        "title": "胰岛β细胞不是坏死而是在「打盹」：新研究发现可唤醒机制",
        "angle": "Science Advances 2026-10 研究：部分糖尿病患者胰岛β细胞并未彻底坏死，而是在长期高压下进入「休眠/打盹」状态。给适宜环境或用对「唤醒剂」可恢复功能。与 Lancet 54% 缓解研究形成机制+结果双支撑，是糖尿病可缓解的科学底层。适合做「为什么有的人能缓解、有的人不能」的决策边界型口播。",
        "category": "数字科普",
        "platform": "dy,bili,xhs",
        "duration": "30-45s",
        "heat": "rising",
        "heat_source": "Science Advances 2026-10 期刊论文 + MedSci.cn 转述 + 头条健康 2026-11 热门文章",
        "source_urls": [
            "https://www.medsci.cn/department/details?module=article&s_id=6&t_id=216",
            "https://m.gmw.cn/2026-11/01/content_13045724.htm"
        ],
        "keywords": ["β细胞", "打盹", "胰岛", "唤醒"]
    },
    {
        "title": "土豆是控糖新主食？国家都喊你多吃点",
        "angle": "2026-10-22 搜狐健康/人民日报：土豆 GI 值低（蒸土豆 GI 66 低于白米饭 83），饱腹感强，被推荐为控糖替代主食。但需警惕加工方式——炸薯条 GI 飙升、加油后 GL 升高。主打「同样是主食，换一种选择血糖曲线就不一样」的轻科普。",
        "category": "饮食指南",
        "platform": "xhs,dy,bili",
        "duration": "15-30s",
        "heat": "steady",
        "heat_source": "搜狐健康 2026-10-22 热门文章 + 36kr 低GI主食赛道分析 + 淘宝 50+ 解馋不升糖土豆类产品",
        "source_urls": [
            "https://news.sohu.com/a/1091142007_121119347",
            "https://36kr.com/p/3943392340917383"
        ],
        "keywords": ["土豆", "主食", "控糖"]
    },
    {
        "title": "二甲双胍争议综述：50年神药的另一面",
        "angle": "Frontiers Pharmacol 2026 综述：二甲双胍胃肠道副作用（15-30% 发生率）、维生素 B12 缺乏（长期使用）、罕见乳酸酸中毒风险。但同时也有延寿、防癌、减脂等超适应症效应。主打「医生开了几十年的药，你可能只知道一半」的平衡视角，避免「神化」或「妖魔化」。",
        "category": "数字科普",
        "platform": "dy,bili",
        "duration": "30-45s",
        "heat": "steady",
        "heat_source": "Frontiers Pharmacol 2026 综述 + 国家医保局 2026 新药说明书收录 + 头条健康热门讨论",
        "source_urls": [
            "https://public-pages-files-2025.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2026.1799374/pdf",
            "https://www.nhsa.gov.cn/attach/Ypsn2026/YPSW202600608/YPSW202600608(ppt).pdf"
        ],
        "keywords": ["二甲双胍", "争议", "副作用"]
    }
]

# 过滤已存在的
new_topics = []
for i, cand in enumerate(candidates):
    coverage = check_coverage(cand["keywords"])
    if coverage:
        print(f"  跳过: disc-{coverage.split('-')[1]} 已覆盖 → {cand['title'][:40]}")
    else:
        max_num += 1
        new_id = f"disc-{max_num:03d}"
        new_topic = {
            "id": new_id,
            "title": cand["title"],
            "angle": cand["angle"],
            "category": cand["category"],
            "platform": cand["platform"],
            "duration": cand["duration"],
            "heat": cand["heat"],
            "heat_source": cand["heat_source"],
            "source_urls": cand["source_urls"],
            "status": "discovered",
            "script_status": "pending",
            "publish_status": "pending",
            "discovered_date": "2026-11-06",
            "harvest_meta": {
                "authenticity": {
                    "score": 78,
                    "label": "较高",
                    "reasons": [
                        "WebSearch 补充 · 期刊综述/权威媒体/官网原文",
                        "需回源核对关键数字和研究结论"
                    ],
                    "evidence_tier": "B",
                    "adversarial_flags": [],
                    "use_as": "verify_before_script",
                    "creator_note": "WebSearch 补充条目，证据层级 B，写稿前须二次回源"
                },
                "topic_score": 78,
                "platform": "web_search"
            }
        }
        topics.append(new_topic)
        new_topics.append(new_topic)
        print(f"  新增: {new_id} → {cand['title'][:50]}")

# ========== 3. 保存 ==========
topics_data["topics"] = topics
topics_data["updated"] = "2026-11-06"

with open(TOPICS_FILE, "w", encoding="utf-8") as f:
    json.dump(topics_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ 选题库更新: {len(topics)} → 新增 {len(new_topics)} 条 (disc-{max_num - len(new_topics) + 1:03d} ~ disc-{max_num:03d})")
