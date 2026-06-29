#!/usr/bin/env python3
"""
平台数据采集脚本 — 血糖知识图谱选题发现引擎
替代 Agent-Reach CLI 工具，直接调用平台公开 API

数据源:
- B站: api.bilibili.com (公开搜索 API，无需认证)
- B站热搜: s.search.bilibili.com (公开接口)

输出: data/discovered-topics.json (增量更新)

用法:
    python src/platform_scraper.py
"""

import json
import os
import re
import ssl
import urllib.request
import gzip
from datetime import datetime
from urllib.parse import quote

# ── 配置 ──────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
TOPICS_FILE = os.path.join(DATA_DIR, 'discovered-topics.json')

SEARCH_KEYWORDS = [
    '控糖', '血糖', '糖尿病', '低GI', '胰岛素抵抗',
    '餐后血糖', '糖化血红蛋白', '控糖饮食', '血糖仪'
]

# 选题分类规则（基于标题关键词匹配）
CATEGORY_RULES = [
    ('辟谣纠偏', ['误区', '谣言', '骗', '假', '真相', '其实', '不是', '别被', '打假']),
    ('饮食指南', ['吃', '食物', '水果', '主食', '零食', '饮食', '食谱', '早餐', '晚餐', '米饭', '碳水']),
    ('数字科普', ['多少', '数据', '研究', '比例', '%', '数值', '标准', '是什么']),
    ('实操方法', ['方法', '技巧', '步骤', '怎么做', '如何', '教你', '学会', '动作', '训练', '走']),
    ('症状预警', ['症状', '信号', '预警', '注意', '危险', '并发症', '风险', '警惕', '看']),
    ('工具测评', ['测评', '测试', '对比', '评测', '推荐', '仪器', '血糖仪', '动态', '选']),
    ('案例故事', ['经历', '故事', '历程', '逆转', '康复', '改变', '从', '到', '我']),
    ('避坑指南', ['坑', '陷阱', '不要', '避免', '错误', '踩雷', '教训', '误差']),
]

# ── HTTP 工具 ─────────────────────────────────────
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(url, headers=None, timeout=15):
    """通用 HTTP GET，自动处理 gzip"""
    h = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            return json.loads(raw.decode('utf-8'))
    except Exception as e:
        return {'_error': str(e)}


# ── B站采集 ───────────────────────────────────────
def search_bilibili(keyword, pagesize=10):
    """搜索 B站视频，返回结构化结果"""
    encoded_kw = quote(keyword)
    url = (
        f'https://api.bilibili.com/x/web-interface/search/type'
        f'?keyword={encoded_kw}&search_type=video&page=1&pagesize={pagesize}'
    )
    data = fetch(url, headers={'Referer': 'https://search.bilibili.com/'})
    if '_error' in data:
        return []
    results = data.get('data', {}).get('result', [])
    items = []
    for r in results:
        title = r.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
        title = re.sub(r'<[^>]+>', '', title)
        items.append({
            'platform': 'bili',
            'title': title,
            'author': r.get('author', ''),
            'play': r.get('play', 0) or 0,
            'danmaku': r.get('danmaku', 0) or 0,
            'link': f"https://www.bilibili.com/video/{r.get('bvid', '')}",
            'keyword': keyword,
        })
    return items


def get_bilibili_hot():
    """获取 B站热搜榜"""
    data = fetch('https://s.search.bilibili.com/main/hotword?limit=50')
    if '_error' in data or 'list' not in data:
        return []
    health_keywords = []
    for item in data['list']:
        kw = item.get('keyword', '')
        if any(x in kw for x in ['糖', '血糖', '控糖', '糖尿病', '健康', '减肥', '饮食', '运动', '低GI', '碳水', '胰岛']):
            health_keywords.append({
                'platform': 'bili',
                'keyword': kw,
                'heat_score': item.get('heat_score', 0),
            })
    return health_keywords


# ── 智能分类 ──────────────────────────────────────
def classify_topic(title):
    """根据标题关键词自动分类"""
    t = title.lower()
    for cat, keywords in CATEGORY_RULES:
        if any(k in t for k in keywords):
            return cat
    return '数字科普'


def estimate_heat(play_count):
    """根据播放量估算热度"""
    try:
        p = int(play_count)
    except (TypeError, ValueError):
        return 'steady'
    if p >= 500000:
        return 'hot'
    elif p >= 100000:
        return 'warm'
    return 'steady'


def estimate_duration(title, play_count):
    """估算适合的视频时长"""
    t = title.lower()
    if any(x in t for x in ['教程', '步骤', '方法', '教你怎么', '怎么做']):
        return '45-60s'
    if any(x in t for x in ['数据', '研究', '科普', '是什么', '为什么']):
        return '60-90s'
    if play_count and int(play_count) > 300000:
        return '30-45s'
    return '15-30s'


# ── 主流程 ────────────────────────────────────────
def load_existing_topics():
    """加载现有选题，用于去重"""
    if not os.path.exists(TOPICS_FILE):
        return {'version': '1.0', 'updated': datetime.now().strftime('%Y-%m-%d'), 'topics': []}
    with open(TOPICS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_topics(topics_data):
    """保存选题到 JSON"""
    topics_data['updated'] = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOPICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(topics_data, f, ensure_ascii=False, indent=2)
    print(f"[保存] 已写入 {len(topics_data['topics'])} 条选题到 data/discovered-topics.json")


def generate_topic_id(existing_ids):
    """生成新的选题 ID，基于现有最大 ID 递增"""
    nums = []
    for tid in existing_ids:
        m = re.match(r'disc-(\d+)', tid)
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums, default=0) + 1
    return f'disc-{next_num:03d}'


def dedup_key(title):
    """生成去重键（核心语义关键词）"""
    words = re.findall(r'[\u4e00-\u9fa5]{2,}', title)
    return ''.join(words[:4])


def run_discovery():
    """执行选题发现流程"""
    print("=" * 50)
    print(f"[选题发现引擎] 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 加载现有数据
    data = load_existing_topics()
    existing_ids = {t['id'] for t in data['topics']}
    existing_keys = {dedup_key(t['title']) for t in data['topics']}
    new_topics = []

    # ── 1. B站热搜采集 ──
    print("\n[1/3] 采集 B站热搜...")
    bili_hot = get_bilibili_hot()
    if bili_hot:
        print(f"  发现 {len(bili_hot)} 条健康相关热搜")
        for item in bili_hot[:3]:
            print(f"    - {item['keyword']} (热度:{item['heat_score']})")
    else:
        print("  暂无健康相关热搜")

    # ── 2. B站视频搜索 ──
    print("\n[2/3] 搜索 B站视频...")
    all_bili_results = []
    for kw in SEARCH_KEYWORDS:
        results = search_bilibili(kw, pagesize=5)
        all_bili_results.extend(results)
        print(f"  '{kw}' -> {len(results)} 条结果")

    # 去重并按播放量排序
    seen_titles = set()
    unique_results = []
    for r in sorted(all_bili_results, key=lambda x: int(x.get('play') or 0), reverse=True):
        if r['title'] not in seen_titles:
            seen_titles.add(r['title'])
            unique_results.append(r)

    print(f"  去重后: {len(unique_results)} 条")

    # 筛选高播放量内容（>=5万）
    filtered = [r for r in unique_results if int(r.get('play') or 0) >= 50000]
    print(f"  播放量>=5万: {len(filtered)} 条")

    # 转换为选题格式
    for r in filtered[:15]:  # 最多取 15 条
        title = r['title']
        dk = dedup_key(title)
        if dk in existing_keys:
            continue

        topic = {
            'id': generate_topic_id(existing_ids),
            'title': title,
            'angle': f"B站热门视频，播放量 {r['play']}，UP主 {r['author']}。可提取核心知识点转化为口播选题。",
            'category': classify_topic(title),
            'platform': 'bili,dy,xhs',
            'duration': estimate_duration(title, r.get('play')),
            'heat': estimate_heat(r.get('play')),
            'heat_source': f"B站搜索'{r['keyword']}'，播放量 {r['play']}，弹幕 {r.get('danmaku', 0)}",
            'source_urls': [r['link']],
            'status': 'discovered',
            'script_status': 'pending',
            'publish_status': 'pending',
            'discovered_date': datetime.now().strftime('%Y-%m-%d'),
            'platform_data': {
                'bili_play': r.get('play'),
                'bili_danmaku': r.get('danmaku'),
                'bili_author': r.get('author'),
            }
        }
        new_topics.append(topic)
        existing_ids.add(topic['id'])
        existing_keys.add(dk)
        print(f"    [新增] {topic['id']}: {title[:45]}...")

    # ── 3. 汇总 ──
    print(f"\n[3/3] 汇总")
    print(f"  原有选题: {len(data['topics'])} 条")
    print(f"  新增选题: {len(new_topics)} 条")

    if new_topics:
        data['topics'].extend(new_topics)
        save_topics(data)
        print(f"\n[完成] 共 {len(data['topics'])} 条选题")
        return new_topics
    else:
        print("\n[完成] 无新增选题")
        return []


if __name__ == '__main__':
    new = run_discovery()
    if new:
        print("\n--- 新增选题预览 ---")
        for t in new[:5]:
            print(f"\n[{t['id']}] {t['title']}")
            print(f"  分类: {t['category']} | 热度: {t['heat']} | 平台: {t['platform']}")
            print(f"  来源: {t['heat_source']}")
